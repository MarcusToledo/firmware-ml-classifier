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

import re

from src.evidence.findings import SecurityFinding

_DETECTOR_VERSION = "1.0"

# ---------------------------------------------------------------------------
# Padrões de senha
# ---------------------------------------------------------------------------

_PASSWORD_KV_RE = re.compile(
    r"\b(?:password|passwd|pass|pwd|secret|credential)\s*[=:]\s*(\S+)",
    re.IGNORECASE,
)

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


def find_hardcoded_passwords(strings: list[str]) -> list[SecurityFinding]:
    """Encontra strings que contêm credenciais hardcoded.

    Casa tanto padrões key=value (``password=admin``, confiança alta)
    quanto ocorrências avulsas de senhas padrão conhecidas (confiança
    média). No máximo um achado por string, preservando a semântica de
    contagem original.
    """
    findings: list[SecurityFinding] = []
    for s in strings:
        m = _PASSWORD_KV_RE.search(s)
        if m:
            findings.append(
                SecurityFinding(
                    type="credential_candidate",
                    source=s,
                    context=f"key=value assignment: {m.group(0)!r}",
                    confidence="high",
                    detector="hardcoded_passwords",
                    detector_version=_DETECTOR_VERSION,
                )
            )
            continue
        tokens = s.split()
        matched = next((t for t in tokens if t.lower() in _DEFAULT_PASSWORDS), None)
        if matched is not None:
            findings.append(
                SecurityFinding(
                    type="credential_candidate",
                    source=s,
                    context=f"default password token: {matched!r}",
                    confidence="medium",
                    detector="hardcoded_passwords",
                    detector_version=_DETECTOR_VERSION,
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
                        confidence="high",
                        detector="credential_pairs",
                        detector_version=_DETECTOR_VERSION,
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

_IPV4_RE = re.compile(r"\b(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})\b")
_IP_EXCLUDES: frozenset[str] = frozenset({"0.0.0.0", "255.255.255.255"})


def find_hardcoded_ips(strings: list[str]) -> list[SecurityFinding]:
    """Encontra strings que contêm endereços IPv4 válidos e não excluídos."""
    findings: list[SecurityFinding] = []
    for s in strings:
        for m in _IPV4_RE.finditer(s):
            octets = tuple(int(g) for g in m.groups())
            if any(o > 255 for o in octets):
                continue
            ip = ".".join(str(o) for o in octets)
            if ip in _IP_EXCLUDES:
                continue
            if octets[0] == 127:
                continue
            findings.append(
                SecurityFinding(
                    type="hardcoded_ip",
                    source=s,
                    context=f"IPv4 address: {ip}",
                    confidence="low",
                    detector="hardcoded_ips",
                    detector_version=_DETECTOR_VERSION,
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
        for m in _IPV4_RE.finditer(s):
            a, b, c, d = (int(g) for g in m.groups())
            if any(o > 255 for o in (a, b, c, d)):
                continue
            ip = f"{a}.{b}.{c}.{d}"
            if ip in _IP_EXCLUDES:
                continue
            if a == 127:
                continue
            if a == 10:
                continue
            if a == 172 and 16 <= b <= 31:
                continue
            if a == 192 and b == 168:
                continue
            if a == 169 and b == 254:
                continue
            if 224 <= a <= 239:
                continue
            if a >= 240:
                continue
            findings.append(
                SecurityFinding(
                    type="public_ip",
                    source=s,
                    context=f"public (non-RFC-1918) IPv4 address: {ip}",
                    confidence="high",
                    detector="public_ips",
                    detector_version=_DETECTOR_VERSION,
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
_DEBUG_ACCOUNT_RE = re.compile(r"\b(?:debug|guest|test)\b", re.IGNORECASE)


def find_telnetd(strings: list[str]) -> list[SecurityFinding]:
    """Encontra strings que contêm a substring 'telnetd'."""
    return [
        SecurityFinding(
            type="exposed_service",
            source=s,
            context=f"{_TELNETD_SUBSTR!r} substring found",
            confidence="high",
            detector="telnetd",
            detector_version=_DETECTOR_VERSION,
        )
        for s in strings
        if _TELNETD_SUBSTR in s
    ]


def has_telnetd(strings: list[str]) -> bool:
    """Retorna True se alguma string contém a substring 'telnetd'."""
    return bool(find_telnetd(strings))


def find_debug_account(strings: list[str]) -> list[SecurityFinding]:
    """Encontra strings com palavra-chave de conta debug/guest/test."""
    findings: list[SecurityFinding] = []
    for s in strings:
        m = _DEBUG_ACCOUNT_RE.search(s)
        if m:
            findings.append(
                SecurityFinding(
                    type="debug_account",
                    source=s,
                    context=f"debug/guest/test keyword: {m.group(0)!r}",
                    confidence="low",
                    detector="debug_account",
                    detector_version=_DETECTOR_VERSION,
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
_DROPBEAR_RE = re.compile(r"Dropbear\s+(?:SSH\s+)?v?([\d]{4}\.[\d]+)", re.IGNORECASE)
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
                        confidence="medium",
                        detector=detector,
                        detector_version=_DETECTOR_VERSION,
                    )
                )
    return findings


def find_outdated_libssl(strings: list[str]) -> list[SecurityFinding]:
    """Encontra strings com versão do OpenSSL abaixo do limiar."""
    return _find_outdated_version(strings, _LIBSSL_RE, "libssl", "outdated_libssl")


def has_outdated_libssl(strings: list[str]) -> bool:
    """Retorna True se uma versão do OpenSSL abaixo do limiar for encontrada."""
    return bool(find_outdated_libssl(strings))


def find_outdated_busybox(strings: list[str]) -> list[SecurityFinding]:
    """Encontra strings com versão do BusyBox abaixo do limiar."""
    return _find_outdated_version(strings, _BUSYBOX_RE, "busybox", "outdated_busybox")


def has_outdated_busybox(strings: list[str]) -> bool:
    """Retorna True se uma versão do BusyBox abaixo do limiar for encontrada."""
    return bool(find_outdated_busybox(strings))


def find_outdated_dropbear(strings: list[str]) -> list[SecurityFinding]:
    """Encontra strings com versão do Dropbear abaixo do limiar."""
    return _find_outdated_version(
        strings, _DROPBEAR_RE, "dropbear", "outdated_dropbear"
    )


def has_outdated_dropbear(strings: list[str]) -> bool:
    """Retorna True se uma versão do Dropbear abaixo do limiar for encontrada."""
    return bool(find_outdated_dropbear(strings))


# ---------------------------------------------------------------------------
# Padrões de URL e token
# ---------------------------------------------------------------------------

_URL_RE = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)
_API_TOKEN_RE = re.compile(
    r"(?<![A-Za-z0-9])(?:[0-9a-fA-F]{32,}|[A-Za-z0-9+/=_\-]{32,})(?![A-Za-z0-9])"
)


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
                    confidence="low",
                    detector="urls",
                    detector_version=_DETECTOR_VERSION,
                )
            )
    return findings


def count_urls(strings: list[str]) -> int:
    """Conta URLs HTTP/HTTPS encontradas em todas as strings."""
    return len(find_urls(strings))


def find_api_tokens(strings: list[str]) -> list[SecurityFinding]:
    """Encontra tokens longos hex ou base64-like (32+ chars) nas strings."""
    findings: list[SecurityFinding] = []
    for s in strings:
        for m in _API_TOKEN_RE.finditer(s):
            findings.append(
                SecurityFinding(
                    type="api_token_candidate",
                    source=s,
                    context=f"long token: {m.group(0)[:12]}…",
                    confidence="low",
                    detector="api_tokens",
                    detector_version=_DETECTOR_VERSION,
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
    "hardcoded_passwords": "count_hardcoded_passwords",
    "credential_pairs": "count_credential_pairs",
    "hardcoded_ips": "count_hardcoded_ips",
    "public_ips": "count_public_ips",
    "urls": "count_urls",
    "api_tokens": "count_api_tokens",
}

_BOOL_DETECTORS: dict[str, str] = {
    "telnetd": "has_telnetd",
    "debug_account": "has_debug_account",
    "outdated_libssl": "has_outdated_libssl",
    "outdated_busybox": "has_outdated_busybox",
    "outdated_dropbear": "has_outdated_dropbear",
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
