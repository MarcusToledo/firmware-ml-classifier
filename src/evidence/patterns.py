"""Detectores de evidência de segurança sobre strings ASCII já extraídas.

Cada função aqui recebe uma ``list[str]`` de strings (como as retornadas por
``src.features.strings.extract_ascii_strings``). Nunca extrai strings novas
do firmware, só interpreta o que ``src/features/*`` já extraiu. Cada detector
expõe duas visões do mesmo match: uma função ``find_*`` retornando objetos
``SecurityFinding`` estruturados (para auditoria e avaliação de
precisão/revocação por detector), e uma função ``count_*``/``has_*``
retornando a contagem/flag achatada usada como feature do classificador.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Iterator

from src.evidence.findings import SecurityFinding

CONFIDENCE_HIGH = "high"
CONFIDENCE_MEDIUM = "medium"
CONFIDENCE_LOW = "low"

DETECTOR_HARDCODED_PASSWORDS = "hardcoded_passwords"
DETECTOR_CREDENTIAL_PAIRS = "credential_pairs"
DETECTOR_HARDCODED_IPS = "hardcoded_ips"
DETECTOR_PUBLIC_IPS = "public_ips"
DETECTOR_TELNETD = "telnetd"
DETECTOR_DEBUG_ACCOUNT = "debug_account"
DETECTOR_OUTDATED_LIBSSL = "outdated_libssl"
DETECTOR_OUTDATED_BUSYBOX = "outdated_busybox"
DETECTOR_OUTDATED_DROPBEAR = "outdated_dropbear"
DETECTOR_URLS = "urls"
DETECTOR_API_TOKENS = "api_tokens"

DETECTOR_VERSIONS: dict[str, str] = {
    DETECTOR_HARDCODED_PASSWORDS: "2.1",
    DETECTOR_CREDENTIAL_PAIRS: "1.1",
    DETECTOR_HARDCODED_IPS: "2.1",
    DETECTOR_PUBLIC_IPS: "2.1",
    DETECTOR_TELNETD: "1.1",
    DETECTOR_DEBUG_ACCOUNT: "2.1",
    DETECTOR_OUTDATED_LIBSSL: "1.1",
    DETECTOR_OUTDATED_BUSYBOX: "1.1",
    DETECTOR_OUTDATED_DROPBEAR: "2.1",
    DETECTOR_URLS: "1.1",
    DETECTOR_API_TOKENS: "2.1",
}

# ---------------------------------------------------------------------------
# Padrões de senha
# ---------------------------------------------------------------------------

_PASSWORD_KV_RE = re.compile(r"\b([A-Za-z][A-Za-z0-9_-]{0,40})\s*[=:]\s*([^\s&;]+)")
_CREDENTIAL_KEY_TOKENS: frozenset[str] = frozenset(
    {
        "password",
        "passwd",
        "pwd",
        "pass",
        "secret",
        "credential",
        "passphrase",
        "pswd",
        "psw",
        "userpass",
        "loginpass",
        "psk",
    }
)
_METADATA_KEY_TOKENS: frozenset[str] = frozenset(
    {"length", "len", "size", "hash", "algorithm", "algo", "policy", "timeout"}
)
_NULL_LITERALS: frozenset[str] = frozenset(
    {"null", "none", "nil", "undefined", "(null)"}
)
_VARIABLE_REF_RE = re.compile(r"^\$\{?\w+\}?$")
_TEMPLATE_RE = re.compile(r"^\{\{?\w+\}?\}$|^<\w+>$")
_CAMEL_BOUNDARY_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_AUTH_CONTEXT_TRIGGERS: frozenset[str] = frozenset(
    {
        "login",
        "user",
        "username",
        "account",
        "credential",
        "auth",
        "senha",
        "password",
        "passwd",
        "pwd",
        "default",
    }
)
_WORD_RE = re.compile(r"[A-Za-z0-9]+")

_DEFAULT_PASSWORDS: frozenset[str] = frozenset(
    {
        "admin",
        "password",
        "1234",
        "12345",
        "123456",
        "admin123",
        "root",
        "toor",
        "pass",
        "test",
        "1234567890",
        "guest",
        "default",
        "support",
        "supervisor",
        "service",
        "system",
        "ubnt",
        "huawei",
        "zte521",
        "telnet",
        "enable",
    }
)


def _key_tokens(key: str) -> list[str]:
    """Separa chaves compostas em tokens minúsculos."""
    spaced = _CAMEL_BOUNDARY_RE.sub("_", key)
    return [token.lower() for token in re.split(r"[_-]", spaced) if token]


def _is_credential_key(key: str) -> bool:
    """Reconhece chaves de credencial que não descrevem metadados."""
    tokens = set(_key_tokens(key))
    return not bool(tokens & _METADATA_KEY_TOKENS) and bool(
        tokens & _CREDENTIAL_KEY_TOKENS
    )


def _is_rejected_value(value: str) -> bool:
    """Rejeita especificadores de formato, variáveis, templates e nulos."""
    return (
        value.startswith("%")
        or bool(_VARIABLE_REF_RE.match(value))
        or bool(_TEMPLATE_RE.match(value))
        or value.strip("()").lower() in _NULL_LITERALS
    )


def _has_default_password_token(s: str) -> bool:
    """Reconhece senha padrão distinta de um gatilho de autenticação."""
    words = {word.lower() for word in _WORD_RE.findall(s)}
    return bool((words & _DEFAULT_PASSWORDS) - _AUTH_CONTEXT_TRIGGERS) and bool(
        words & _AUTH_CONTEXT_TRIGGERS
    )


def find_hardcoded_passwords(strings: list[str]) -> list[SecurityFinding]:
    """Encontra credenciais concretas ou senhas padrão com contexto de autenticação."""
    findings: list[SecurityFinding] = []
    for s in strings:
        match = next(
            (
                m
                for m in _PASSWORD_KV_RE.finditer(s)
                if _is_credential_key(m.group(1)) and not _is_rejected_value(m.group(2))
            ),
            None,
        )
        if match is not None:
            context = f"key=value assignment: {match.group(0)!r}"
            confidence = CONFIDENCE_HIGH
        elif _has_default_password_token(s):
            token = next(
                word
                for word in _WORD_RE.findall(s)
                if word.lower() in _DEFAULT_PASSWORDS - _AUTH_CONTEXT_TRIGGERS
            )
            context = f"default password token: {token!r}"
            confidence = CONFIDENCE_MEDIUM
        else:
            continue
        findings.append(
            SecurityFinding(
                type="credential_candidate",
                source=s,
                context=context,
                confidence=confidence,
                detector=DETECTOR_HARDCODED_PASSWORDS,
                detector_version=DETECTOR_VERSIONS[DETECTOR_HARDCODED_PASSWORDS],
            )
        )
    return findings


def count_hardcoded_passwords(strings: list[str]) -> int:
    """Conta strings que contêm credenciais hardcoded."""
    return len(find_hardcoded_passwords(strings))


# ---------------------------------------------------------------------------
# Pares de credenciais (user:pass onde ambos os lados são fracos/padrão)
# ---------------------------------------------------------------------------

_CRED_PAIR_RE = re.compile(r"\b([A-Za-z0-9]{1,20}):([A-Za-z0-9]{1,20})\b")
_CRED_PAIR_WEAK: frozenset[str] = frozenset(
    {
        "admin",
        "root",
        "guest",
        "test",
        "default",
        "user",
        "support",
        "supervisor",
        "service",
        "system",
        "ubnt",
        "huawei",
        "zte521",
        "password",
        "1234",
        "12345",
        "123456",
        "admin123",
        "toor",
        "pass",
        "enable",
        "telnet",
    }
)


def find_credential_pairs(strings: list[str]) -> list[SecurityFinding]:
    """Encontra strings com pares de credenciais fracas separados por dois-pontos.

    Casa padrões como ``admin:admin`` ou ``root:1234`` onde os dois lados
    estão no conjunto conhecido de valores fracos/padrão. No máximo um
    achado por string (uma string com múltiplos pares ainda conta uma vez),
    preservando a semântica de contagem original.
    """
    findings: list[SecurityFinding] = []
    for s in strings:
        for m in _CRED_PAIR_RE.finditer(s):
            if (
                m.group(1).lower() in _CRED_PAIR_WEAK
                and m.group(2).lower() in _CRED_PAIR_WEAK
            ):
                findings.append(
                    SecurityFinding(
                        type="credential_pair",
                        source=s,
                        context=f"weak user:pass pair: {m.group(0)!r}",
                        confidence=CONFIDENCE_HIGH,
                        detector=DETECTOR_CREDENTIAL_PAIRS,
                        detector_version=DETECTOR_VERSIONS[DETECTOR_CREDENTIAL_PAIRS],
                    )
                )
                break
    return findings


def count_credential_pairs(strings: list[str]) -> int:
    """Conta strings com pares de credenciais fracas separados por dois-pontos."""
    return len(find_credential_pairs(strings))


# ---------------------------------------------------------------------------
# Padrões de endereço IP
# ---------------------------------------------------------------------------

_MAX_IPV4_OCTET = 255
_UNSPECIFIED_FIRST_OCTET = 0
_LOOPBACK_FIRST_OCTET = 127
_PRIVATE_CLASS_A_FIRST_OCTET = 10
_PRIVATE_CLASS_B_FIRST_OCTET = 172
_PRIVATE_CLASS_B_SECOND_MIN = 16
_PRIVATE_CLASS_B_SECOND_MAX = 31
_PRIVATE_CLASS_C_FIRST_OCTET = 192
_PRIVATE_CLASS_C_SECOND_OCTET = 168
_LINK_LOCAL_FIRST_OCTET = 169
_LINK_LOCAL_SECOND_OCTET = 254
_MULTICAST_FIRST_MIN = 224
_MULTICAST_FIRST_MAX = 239
_RESERVED_FIRST_MIN = 240

_IPV4_RE = re.compile(
    r"(?<![-_A-Za-z0-9.])(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})(?![-_A-Za-z0-9]|\.\d)"
)
_VERSION_IP_PREFIX_RE = re.compile(r"(?:\bv|\bversion|\bLinux-)\s*$", re.IGNORECASE)
_NETWORK_CONTEXT_WORDS: frozenset[str] = frozenset(
    {
        "ip",
        "ipaddr",
        "host",
        "hostname",
        "server",
        "gateway",
        "gw",
        "dns",
        "ntp",
        "route",
        "addr",
        "address",
        "proxy",
        "remote",
        "peer",
        "connect",
        "bind",
        "listen",
    }
)


def _iter_contextual_ipv4(s: str) -> Iterator[tuple[int, int, int, int]]:
    """Produz IPv4 válidos quando a string oferece contexto de rede."""
    words = {word.lower() for word in _WORD_RE.findall(s)}
    for match in _IPV4_RE.finditer(s):
        octets = (
            int(match.group(1)),
            int(match.group(2)),
            int(match.group(3)),
            int(match.group(4)),
        )
        if any(octet > _MAX_IPV4_OCTET for octet in octets) or octets[0] in (
            _UNSPECIFIED_FIRST_OCTET,
            _LOOPBACK_FIRST_OCTET,
            _MAX_IPV4_OCTET,
        ):
            continue
        if _VERSION_IP_PREFIX_RE.search(s[: match.start()]):
            continue
        if not (
            words & _NETWORK_CONTEXT_WORDS
            or "http://" in s.lower()
            or "https://" in s.lower()
            or re.match(r":\d+", s[match.end() :])
        ):
            continue
        yield octets


def find_hardcoded_ips(strings: list[str]) -> list[SecurityFinding]:
    """Encontra strings que contêm endereços IPv4 válidos e não excluídos."""
    findings: list[SecurityFinding] = []
    for s in strings:
        for octets in _iter_contextual_ipv4(s):
            ip = ".".join(str(octet) for octet in octets)
            findings.append(
                SecurityFinding(
                    type="hardcoded_ip",
                    source=s,
                    context=f"IPv4 address: {ip}",
                    confidence=CONFIDENCE_LOW,
                    detector=DETECTOR_HARDCODED_IPS,
                    detector_version=DETECTOR_VERSIONS[DETECTOR_HARDCODED_IPS],
                )
            )
    return findings


def count_hardcoded_ips(strings: list[str]) -> int:
    """Conta strings que contêm endereços IPv4 válidos e não excluídos."""
    return len(find_hardcoded_ips(strings))


def find_public_ips(strings: list[str]) -> list[SecurityFinding]:
    """Encontra strings com IPv4 público hardcoded (fora do RFC-1918).

    Exclui loopback, link-local, ranges privados do RFC-1918, multicast e
    reservado/broadcast. IPs públicos hardcoded em firmware são indicadores
    de alta confiança de endpoints de C2 ou telemetria.
    """
    findings: list[SecurityFinding] = []
    for s in strings:
        for a, b, c, d in _iter_contextual_ipv4(s):
            ip = f"{a}.{b}.{c}.{d}"
            if a == _PRIVATE_CLASS_A_FIRST_OCTET:
                continue
            if a == _PRIVATE_CLASS_B_FIRST_OCTET and (
                _PRIVATE_CLASS_B_SECOND_MIN <= b <= _PRIVATE_CLASS_B_SECOND_MAX
            ):
                continue
            if a == _PRIVATE_CLASS_C_FIRST_OCTET and b == _PRIVATE_CLASS_C_SECOND_OCTET:
                continue
            if a == _LINK_LOCAL_FIRST_OCTET and b == _LINK_LOCAL_SECOND_OCTET:
                continue
            if _MULTICAST_FIRST_MIN <= a <= _MULTICAST_FIRST_MAX:
                continue
            if a >= _RESERVED_FIRST_MIN:
                continue
            findings.append(
                SecurityFinding(
                    type="public_ip",
                    source=s,
                    context=f"public (non-RFC-1918) IPv4 address: {ip}",
                    confidence=CONFIDENCE_HIGH,
                    detector=DETECTOR_PUBLIC_IPS,
                    detector_version=DETECTOR_VERSIONS[DETECTOR_PUBLIC_IPS],
                )
            )
    return findings


def count_public_ips(strings: list[str]) -> int:
    """Conta strings com IPv4 público hardcoded (fora do RFC-1918)."""
    return len(find_public_ips(strings))


# ---------------------------------------------------------------------------
# Padrões de serviço / conta
# ---------------------------------------------------------------------------

_TELNETD_SUBSTR = "telnetd"
_DEBUG_ACCOUNT_WORDS: frozenset[str] = frozenset({"debug", "guest", "test"})


def find_telnetd(strings: list[str]) -> list[SecurityFinding]:
    """Encontra strings que contêm a substring 'telnetd'."""
    return [
        SecurityFinding(
            type="exposed_service",
            source=s,
            context=f"{_TELNETD_SUBSTR!r} substring found",
            confidence=CONFIDENCE_HIGH,
            detector=DETECTOR_TELNETD,
            detector_version=DETECTOR_VERSIONS[DETECTOR_TELNETD],
        )
        for s in strings
        if _TELNETD_SUBSTR in s
    ]


def has_telnetd(strings: list[str]) -> bool:
    """Retorna True se alguma string contém a substring 'telnetd'."""
    return bool(find_telnetd(strings))


def find_debug_account(strings: list[str]) -> list[SecurityFinding]:
    """Encontra nome de conta de teste em contexto de autenticação."""
    findings: list[SecurityFinding] = []
    for s in strings:
        words = [word.lower() for word in _WORD_RE.findall(s)]
        if not set(words) & _AUTH_CONTEXT_TRIGGERS:
            continue
        name = next((word for word in words if word in _DEBUG_ACCOUNT_WORDS), None)
        if name is not None:
            findings.append(
                SecurityFinding(
                    type="debug_account",
                    source=s,
                    context=f"debug/guest/test keyword: {name!r}",
                    confidence=CONFIDENCE_LOW,
                    detector=DETECTOR_DEBUG_ACCOUNT,
                    detector_version=DETECTOR_VERSIONS[DETECTOR_DEBUG_ACCOUNT],
                )
            )
    return findings


def has_debug_account(strings: list[str]) -> bool:
    """Retorna True se alguma string contém nome de conta debug/guest/test."""
    return bool(find_debug_account(strings))


# ---------------------------------------------------------------------------
# Padrões de versão de biblioteca
# ---------------------------------------------------------------------------

_LIBSSL_RE = re.compile(r"OpenSSL[\s/]+([\d]+\.[\d]+\.[\d]+[a-z]?)", re.IGNORECASE)
_BUSYBOX_RE = re.compile(r"BusyBox[\s_]*v?([\d]+\.[\d]+\.[\d]+)", re.IGNORECASE)
_DROPBEAR_RE = re.compile(
    r"Dropbear\s+(?:SSH\s+)?v?(\d{4}\.\d+|0\.\d{2}(?:\.\d+)?)", re.IGNORECASE
)
_VERSION_THRESHOLDS: dict[str, tuple[int, ...]] = {
    "libssl": (1, 1, 1),  # < OpenSSL 1.1.1 → desatualizado
    "busybox": (1, 33, 0),  # < BusyBox 1.33.0 → desatualizado
    "dropbear": (2022, 82),  # < Dropbear 2022.82 → desatualizado
}


def _parse_version(v: str) -> tuple[int, ...]:
    """Converte uma string de versão com pontos em uma tupla de inteiros.

    Exemplos::

        _parse_version("1.1.1a") -> (1, 1, 1)
        _parse_version("2022.82") -> (2022, 82)
    """
    parts: list[int] = []
    for segment in re.split(r"[.\-_]", v):
        digits = re.match(r"(\d+)", segment)
        if digits:
            parts.append(int(digits.group(1)))
    return tuple(parts)


def _find_outdated_version(
    strings: list[str],
    pattern: re.Pattern[str],
    lib_name: str,
    detector: str,
) -> list[SecurityFinding]:
    """Varredura compartilhada pelos três detectores de lib desatualizada abaixo."""
    threshold = _VERSION_THRESHOLDS[lib_name]
    findings: list[SecurityFinding] = []
    for s in strings:
        m = pattern.search(s)
        if m:
            version = _parse_version(m.group(1))
            if version < threshold:
                findings.append(
                    SecurityFinding(
                        type="outdated_library",
                        source=s,
                        context=(
                            f"{lib_name} version {m.group(1)} "
                            f"below threshold {threshold}"
                        ),
                        confidence=CONFIDENCE_MEDIUM,
                        detector=detector,
                        detector_version=DETECTOR_VERSIONS[detector],
                    )
                )
    return findings


def find_outdated_libssl(strings: list[str]) -> list[SecurityFinding]:
    """Encontra strings com versão do OpenSSL abaixo do limiar."""
    return _find_outdated_version(
        strings, _LIBSSL_RE, "libssl", DETECTOR_OUTDATED_LIBSSL
    )


def has_outdated_libssl(strings: list[str]) -> bool:
    """Retorna True se uma versão do OpenSSL abaixo do limiar for encontrada."""
    return bool(find_outdated_libssl(strings))


def find_outdated_busybox(strings: list[str]) -> list[SecurityFinding]:
    """Encontra strings com versão do BusyBox abaixo do limiar."""
    return _find_outdated_version(
        strings, _BUSYBOX_RE, "busybox", DETECTOR_OUTDATED_BUSYBOX
    )


def has_outdated_busybox(strings: list[str]) -> bool:
    """Retorna True se uma versão do BusyBox abaixo do limiar for encontrada."""
    return bool(find_outdated_busybox(strings))


def find_outdated_dropbear(strings: list[str]) -> list[SecurityFinding]:
    """Encontra strings com versão do Dropbear abaixo do limiar."""
    return _find_outdated_version(
        strings, _DROPBEAR_RE, "dropbear", DETECTOR_OUTDATED_DROPBEAR
    )


def has_outdated_dropbear(strings: list[str]) -> bool:
    """Retorna True se uma versão do Dropbear abaixo do limiar for encontrada."""
    return bool(find_outdated_dropbear(strings))


# ---------------------------------------------------------------------------
# Padrões de URL e token
# ---------------------------------------------------------------------------

_URL_RE = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)
_API_TOKEN_RE = re.compile(
    r"(?<![A-Za-z0-9])(?:[0-9a-fA-F]{32,}|[A-Za-z0-9+/]{40,}={0,2})(?![A-Za-z0-9])"
)
_HEX_TOKEN_RE = re.compile(r"[0-9a-fA-F]{32,}\Z")
_API_TOKEN_MIN_ENTROPY = 4.3
_API_TOKEN_MAX_RUN = 5
_TOKEN_CONTEXT_LENGTH = 12


def _shannon_entropy_chars(s: str) -> float:
    """Calcula a entropia de Shannon por caractere."""
    frequencies = Counter(s)
    return -sum(
        (count / len(s)) * math.log2(count / len(s)) for count in frequencies.values()
    )


def _has_ascending_run(s: str, n: int) -> bool:
    """Detecta uma sequência crescente de códigos consecutivos."""
    run = 1
    for previous, current in zip(s, s[1:]):
        run = run + 1 if ord(current) == ord(previous) + 1 else 1
        if run >= n:
            return True
    return False


def find_urls(strings: list[str]) -> list[SecurityFinding]:
    """Encontra URLs HTTP/HTTPS em todas as strings."""
    findings: list[SecurityFinding] = []
    for s in strings:
        for m in _URL_RE.finditer(s):
            findings.append(
                SecurityFinding(
                    type="url",
                    source=s,
                    context=f"URL: {m.group(0)}",
                    confidence=CONFIDENCE_LOW,
                    detector=DETECTOR_URLS,
                    detector_version=DETECTOR_VERSIONS[DETECTOR_URLS],
                )
            )
    return findings


def count_urls(strings: list[str]) -> int:
    """Conta URLs HTTP/HTTPS encontradas em todas as strings."""
    return len(find_urls(strings))


def find_api_tokens(strings: list[str]) -> list[SecurityFinding]:
    """Encontra candidatos hexadecimais ou base64 de alta entropia."""
    findings: list[SecurityFinding] = []
    for s in strings:
        for match in _API_TOKEN_RE.finditer(s):
            candidate = match.group(0)
            if _has_ascending_run(candidate, _API_TOKEN_MAX_RUN):
                continue
            if not _HEX_TOKEN_RE.fullmatch(candidate) and not (
                re.search(r"[A-Z]", candidate)
                and re.search(r"[a-z]", candidate)
                and re.search(r"\d", candidate)
                and _shannon_entropy_chars(candidate) >= _API_TOKEN_MIN_ENTROPY
            ):
                continue
            findings.append(
                SecurityFinding(
                    type="api_token_candidate",
                    source=s,
                    context=f"long token: {candidate[:_TOKEN_CONTEXT_LENGTH]}…",
                    confidence=CONFIDENCE_LOW,
                    detector=DETECTOR_API_TOKENS,
                    detector_version=DETECTOR_VERSIONS[DETECTOR_API_TOKENS],
                )
            )
    return findings


def count_api_tokens(strings: list[str]) -> int:
    """Conta tokens longos hex ou base64-like (32+ chars) nas strings."""
    return len(find_api_tokens(strings))


# ---------------------------------------------------------------------------
# Varredura agregada: achados estruturados e contagens achatadas
# ---------------------------------------------------------------------------

_COUNT_DETECTORS: dict[str, str] = {
    DETECTOR_HARDCODED_PASSWORDS: "count_hardcoded_passwords",
    DETECTOR_CREDENTIAL_PAIRS: "count_credential_pairs",
    DETECTOR_HARDCODED_IPS: "count_hardcoded_ips",
    DETECTOR_PUBLIC_IPS: "count_public_ips",
    DETECTOR_URLS: "count_urls",
    DETECTOR_API_TOKENS: "count_api_tokens",
}

_BOOL_DETECTORS: dict[str, str] = {
    DETECTOR_TELNETD: "has_telnetd",
    DETECTOR_DEBUG_ACCOUNT: "has_debug_account",
    DETECTOR_OUTDATED_LIBSSL: "has_outdated_libssl",
    DETECTOR_OUTDATED_BUSYBOX: "has_outdated_busybox",
    DETECTOR_OUTDATED_DROPBEAR: "has_outdated_dropbear",
}


def scan_strings_findings(strings: list[str]) -> list[SecurityFinding]:
    """Roda todos os detectores sobre ``strings`` e retorna todos os achados.

    Esta é a saída auditável: cada match, com origem/contexto/confiança,
    para revisão manual e avaliação de precisão/revocação por detector.
    """
    findings: list[SecurityFinding] = []
    findings.extend(find_hardcoded_passwords(strings))
    findings.extend(find_credential_pairs(strings))
    findings.extend(find_hardcoded_ips(strings))
    findings.extend(find_public_ips(strings))
    findings.extend(find_telnetd(strings))
    findings.extend(find_debug_account(strings))
    findings.extend(find_outdated_libssl(strings))
    findings.extend(find_outdated_busybox(strings))
    findings.extend(find_outdated_dropbear(strings))
    findings.extend(find_urls(strings))
    findings.extend(find_api_tokens(strings))
    return findings


def findings_to_counts(findings: list[SecurityFinding]) -> dict[str, int | bool]:
    """Reduz achados estruturados às contagens/flags achatadas usadas como feature."""
    counts: dict[str, int | bool] = {key: 0 for key in _COUNT_DETECTORS.values()}
    counts.update({key: False for key in _BOOL_DETECTORS.values()})
    for finding in findings:
        if finding.detector in _COUNT_DETECTORS:
            key = _COUNT_DETECTORS[finding.detector]
            counts[key] = int(counts[key]) + 1
        elif finding.detector in _BOOL_DETECTORS:
            counts[_BOOL_DETECTORS[finding.detector]] = True
    return counts


def scan_strings(strings: list[str]) -> dict[str, int | bool]:
    """Roda todos os detectores e retorna um dicionário de features achatado.

    Visão compatível com versões anteriores sobre ``scan_strings_findings``
    + ``findings_to_counts``, com as mesmas chaves e semântica da
    implementação anterior à camada de evidências. Chaves retornadas:
        count_hardcoded_passwords, count_credential_pairs,
        count_hardcoded_ips, count_public_ips,
        has_telnetd, has_debug_account,
        has_outdated_libssl, has_outdated_busybox, has_outdated_dropbear,
        count_urls, count_api_tokens
    """
    return findings_to_counts(scan_strings_findings(strings))
