"""Mapeia estatísticas de CVE para classes de vulnerabilidade conhecida.

Os campos de CVE definem somente o rótulo; nunca entram no vetor de features.
Ausência de CVE conhecida não significa que o firmware seja seguro.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from src.labeling.version_match import (
    VersionRange,
    parse_version,
    version_in_range,
    versions_equal,
)

LABEL_NO_KNOWN_CVE = "sem_cve_conhecida"
LABEL_KNOWN_CVE = "cve_conhecida"
LABEL_CRITICAL_CVE = "cve_critica"
LABEL_INDETERMINATE = "indeterminado"

_NUMERIC_VERSION_RE = re.compile(r"^\d+(?:\.\d+)*$")
_NETGEAR_PACKAGE_RE = re.compile(r"^(\d+(?:\.\d+){2,3})_\d+(?:\.\d+)*$")
_BOUND_KEYS = (
    "versionStartIncluding",
    "versionStartExcluding",
    "versionEndIncluding",
    "versionEndExcluding",
)


def _validate_cvss(value: object, field: str) -> None:
    """Garante que o valor é número finito entre 0 e 10.

    Levanta ValueError com a mensagem "<field> deve ser um número entre 0 e 10".
    """
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"{field} deve ser um número entre 0 e 10")
    if not math.isfinite(value) or not 0 <= value <= 10:
        raise ValueError(f"{field} deve ser um número entre 0 e 10")


@dataclass(frozen=True)
class CveLabelThresholds:
    """Limiar CVSS para a classe de CVE crítica."""

    critical_cvss: float = 9.0

    def __post_init__(self) -> None:
        """Valida critical_cvss."""
        _validate_cvss(self.critical_cvss, "critical_cvss")


_DEFAULT_THRESHOLDS = CveLabelThresholds()


def severity_bucket(severity: str) -> str:
    """Normaliza a severidade para o bucket em maiúsculas; vazio vira NONE."""
    return severity.upper() if severity else "NONE"


def aggregate_cve_scores(scores: list[tuple[float, str]]) -> dict[str, Any]:
    """Resume pares (cvss, severidade) em cvss_max, contagem por severidade e total."""
    if not scores:
        return {
            "cvss_max": 0.0,
            "cve_count_critical": 0,
            "cve_count_high": 0,
            "cve_count_medium": 0,
            "cve_count_low": 0,
            "cve_total": 0,
        }

    counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    max_score = 0.0

    for score, sev in scores:
        max_score = max(max_score, score)
        bucket = severity_bucket(sev)
        if bucket in counts:
            counts[bucket] += 1

    return {
        "cvss_max": max_score,
        "cve_count_critical": counts["CRITICAL"],
        "cve_count_high": counts["HIGH"],
        "cve_count_medium": counts["MEDIUM"],
        "cve_count_low": counts["LOW"],
        "cve_total": len(scores),
    }


def label_from_cve_stats(
    cve_stats: dict[str, Any],
    thresholds: CveLabelThresholds = _DEFAULT_THRESHOLDS,
) -> str:
    """Rotula estatísticas agregadas de uma consulta CVE concluída.

    Um dicionário vazio representa uma consulta sem resultados nesta API.
    O chamador deve distinguir isso de uma consulta ausente ou com erro.
    """
    cve_total = cve_stats.get("cve_total", 0)
    if not isinstance(cve_total, int) or isinstance(cve_total, bool) or cve_total < 0:
        raise ValueError("cve_total deve ser um inteiro não negativo")

    cvss_max = cve_stats.get("cvss_max", 0.0)
    _validate_cvss(cvss_max, "cvss_max")

    if cve_total == 0:
        return LABEL_NO_KNOWN_CVE
    if cvss_max >= thresholds.critical_cvss:
        return LABEL_CRITICAL_CVE
    return LABEL_KNOWN_CVE


def _canonical(value: str) -> str:
    """Reduz o texto a minúsculas e dígitos para comparar nomes de CPE."""
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _canonical_product(vendor: str, product: str) -> tuple[str, str]:
    """Canoniza vendor e produto de CPE, removendo o sufixo "firmware" do produto."""
    return _canonical(vendor), _canonical(product).removesuffix("firmware")


def _is_numeric_version(value: str) -> bool:
    """Indica se a versão é só números separados por ponto."""
    return _NUMERIC_VERSION_RE.fullmatch(value) is not None


def _target_parts(entry: dict[str, Any]) -> tuple[str, str] | None:
    """Retorna (vendor, produto) canônicos do alvo pela CPE ou por vendor/model.

    Retorna None quando a entrada não traz nenhum dos dois.
    """
    name = entry.get("cpe_name")
    if isinstance(name, str):
        parts = name.split(":")
        if len(parts) == 13:
            return _canonical_product(parts[3], parts[4])
    vendor, model = entry.get("vendor"), entry.get("model")
    if isinstance(vendor, str) and isinstance(model, str):
        return _canonical_product(vendor, model)
    return None


def _product_of(criteria: object) -> tuple[str, str, str, str] | None:
    """Retorna (tipo, vendor, produto, versao) de uma CPE 2.3, ou None se ilegivel."""
    parts = criteria.split(":") if isinstance(criteria, str) else []
    if len(parts) != 13 or parts[:2] != ["cpe", "2.3"]:
        return None
    return (parts[2], *_canonical_product(parts[3], parts[4]), parts[5])


def _iter_matches(node: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """Percorre os cpeMatch do nó e de seus filhos, em profundidade."""
    yield from node.get("cpeMatch", [])
    for child in node.get("children", []):
        yield from _iter_matches(child)


def _is_other_product(config: dict[str, Any], target: tuple[str, str] | None) -> bool:
    """Indica se toda CPE da config e legivel e nenhuma cita o produto-alvo.

    Uma CVE listada para varios modelos traz uma config por modelo; as dos
    outros modelos nao se aplicam ao alvo. CPE ilegivel mantem a config em
    avaliacao, porque nao da para afirmar que ela e de outro produto.
    """
    if target is None:
        return False
    criteria = [
        match["criteria"]
        for node in config.get("nodes", [])
        for match in _iter_matches(node)
        if match.get("criteria") is not None
    ]
    if not criteria:
        return False
    for item in criteria:
        product = _product_of(item)
        if product is None or product[1:3] == target:
            return False
    return True


def _match_platform(
    match: dict[str, Any], target: tuple[str, str] | None
) -> bool | None:
    """Avalia a condicao `vulnerable=false`: plataforma em que o firmware roda.

    O cache e por vendor/model, entao o hardware do proprio modelo-alvo sem
    revisao (`-` ou `*`) e satisfeito por construcao. Qualquer outra condicao
    (outro produto, revisao especifica) nao da para afirmar.
    """
    product = _product_of(match.get("criteria"))
    if product is None or target is None:
        return None
    kind, vendor, name, version = product
    if kind == "h" and (vendor, name) == target and version in {"-", "*"}:
        return True
    return None


def _normalize_cpe_version(value: str, vendor: str | None) -> tuple[str, bool]:
    """Normaliza uma versao CPE e indica pacote Netgear removido."""
    normalized = re.sub(r"^[vV](?=\d)", "", value)
    if vendor == "asus":
        return normalized.replace("_", "."), False
    if vendor == "netgear":
        package_match = _NETGEAR_PACKAGE_RE.fullmatch(normalized)
        if package_match is not None:
            return package_match.group(1), True
    return normalized, False


def _match_version(
    version_raw: str,
    version: tuple[int, ...],
    match: dict[str, Any],
    target: tuple[str, str] | None,
    unknown_if_unrelated: bool = False,
) -> bool | None:
    """Avalia se uma CPE vulnerável cobre a versão do firmware.

    Retorna True (cobre), False (não cobre) ou None (indeterminada). Primeiro
    confere produto e versão exata da CPE; depois os limites
    versionStart*/versionEnd*. CPE com campo update específico nunca vira True.
    """
    update_specific = False
    criteria = match.get("criteria")
    if criteria is not None:
        criteria_verdict, update_specific = _match_criteria(
            version_raw, version, criteria, target, unknown_if_unrelated
        )
        if criteria_verdict is not True:
            return criteria_verdict
    matched = _match_bounds(version_raw, version, match, target)
    if matched and update_specific:
        return None
    return matched


def _match_criteria(
    version_raw: str,
    version: tuple[int, ...],
    criteria: object,
    target: tuple[str, str] | None,
    unknown_if_unrelated: bool,
) -> tuple[bool | None, bool]:
    """Confere produto-alvo, versão exata e campo update de uma CPE.

    Retorna (veredito, update_específico). Veredito True significa CPE
    compatível e a avaliação segue para os limites; False ou None encerram a
    avaliação com esse valor.
    """
    parts = criteria.split(":") if isinstance(criteria, str) else []
    if len(parts) != 13 or parts[:2] != ["cpe", "2.3"]:
        return None, False
    if target is None:
        return None, False
    if _canonical_product(parts[3], parts[4]) != target:
        return (None if unknown_if_unrelated else False), False
    # O campo `update` (hotfix, beta, build datado) restringe a CVE a um
    # build que o nome do arquivo nao informa; versao casando vira None.
    update_specific = parts[6] not in {"*", "-"}
    verdict = _match_exact_version(version_raw, version, parts[5], target[0])
    return verdict, update_specific


def _match_exact_version(
    version_raw: str,
    version: tuple[int, ...],
    exact_version: str,
    vendor: str,
) -> bool | None:
    """Compara a versão do firmware com o campo version da CPE.

    True: compatível ou curinga "*"; None: "-", versão ilegível ou pacote
    Netgear que coincide; False: versão diferente.
    """
    if exact_version == "-":
        return None
    if exact_version == "*" or exact_version.casefold() == version_raw.casefold():
        return True
    normalized, package_removed = _normalize_cpe_version(exact_version, vendor)
    parsed = parse_version(normalized)
    if parsed is None:
        return None
    if package_removed and versions_equal(version, parsed):
        return None
    return _compare_exact_version(version_raw, version, normalized, parsed)


def _compare_exact_version(
    version_raw: str,
    version: tuple[int, ...],
    normalized: str,
    parsed: tuple[int, ...],
) -> bool | None:
    """Decide a CPE exata conforme firmware e CPE sejam numéricos ou tenham sufixo."""
    firmware_numeric = _is_numeric_version(version_raw)
    cpe_numeric = _is_numeric_version(normalized)
    if (
        firmware_numeric
        and cpe_numeric
        and version_in_range(
            version, VersionRange(start_including=parsed, end_including=parsed)
        )
    ):
        return True
    if not cpe_numeric and versions_equal(version, parsed):
        return _match_suffixed_cpe_version(version_raw, normalized)
    if cpe_numeric and not firmware_numeric and versions_equal(version, parsed):
        return None
    return False


def _match_suffixed_cpe_version(version_raw: str, normalized: str) -> bool | None:
    """Trata CPE com sufixo (build, beta, variante) de mesma base que o firmware."""
    # Sufixos (build Bxx, beta ou variante regional) mudam a
    # release, e a NVD os embute em version. Sem build no
    # firmware, nao da para excluir a CVE; com outro build
    # conhecido, o resultado deve ser False.
    if _is_numeric_version(version_raw):
        return None
    normalized_casefold = normalized.casefold()
    version_casefold = version_raw.casefold()
    suffix_index = len(version_casefold)
    if (
        normalized_casefold.startswith(version_casefold)
        and len(normalized_casefold) > suffix_index
        and not normalized_casefold[suffix_index].isalnum()
    ):
        return None
    return False


def _match_bounds(
    version_raw: str,
    version: tuple[int, ...],
    match: dict[str, Any],
    target: tuple[str, str] | None,
) -> bool | None:
    """Avalia os limites versionStart*/versionEnd* da CPE contra a versão do firmware.

    None quando um limite é ilegível ou não numérico, ou quando há limite e o
    firmware não é numérico.
    """
    bounds: dict[str, tuple[int, ...]] = {}
    vendor = target[0] if target is not None else None
    for key in _BOUND_KEYS:
        if key not in match:
            continue
        parsed = _parse_bound(match[key], vendor, version)
        if parsed is None:
            return None
        bounds[key] = parsed
    if bounds and not _is_numeric_version(version_raw):
        return None
    return version_in_range(
        version,
        VersionRange(
            start_including=bounds.get("versionStartIncluding"),
            start_excluding=bounds.get("versionStartExcluding"),
            end_including=bounds.get("versionEndIncluding"),
            end_excluding=bounds.get("versionEndExcluding"),
        ),
    )


def _parse_bound(
    value: object, vendor: str | None, version: tuple[int, ...]
) -> tuple[int, ...] | None:
    """Converte um limite de versão da CPE em tupla numérica.

    Retorna None quando o limite não é string numérica ou é pacote Netgear
    que coincide com o firmware.
    """
    if not isinstance(value, str):
        return None
    normalized, package_removed = _normalize_cpe_version(value, vendor)
    parsed = parse_version(normalized)
    if parsed is None or not _is_numeric_version(normalized.strip()):
        return None
    if package_removed and versions_equal(version, parsed):
        return None
    return parsed


def _combine(results: list[bool | None], operator: str) -> bool | None:
    """Combina vereditos True/False/None por AND ou OR em lógica de três valores."""
    if not results:
        return None
    if operator == "AND":
        if False in results:
            return False
        return None if None in results else True
    if True in results:
        return True
    return None if None in results else False


def _evaluate_node(
    node: dict[str, Any],
    version_raw: str,
    version: tuple[int, ...],
    target: tuple[str, str] | None,
    unknown_if_unrelated: bool = False,
) -> bool | None:
    """Avalia um nó de configuração NVD, com filhos e negação.

    Dentro de AND, CPE de outro produto vira indeterminada em vez de False.
    """
    operator = node.get("operator", "OR")
    unknown_if_unrelated = unknown_if_unrelated or operator == "AND"
    results: list[bool | None] = []
    for match in node.get("cpeMatch", []):
        if not match.get("vulnerable", False):
            results.append(_match_platform(match, target))
        else:
            results.append(
                _match_version(
                    version_raw, version, match, target, unknown_if_unrelated
                )
            )
    for child in node.get("children", []):
        results.append(
            _evaluate_node(child, version_raw, version, target, unknown_if_unrelated)
        )
    result = _combine(results, operator)
    if node.get("negate") and result is not None:
        return not result
    return result


def _evaluate_configuration(
    config: dict[str, Any],
    version_raw: str,
    version: tuple[int, ...],
    target: tuple[str, str] | None,
) -> bool | None:
    """Combina os nós de uma configuração NVD pelo operador dela."""
    operator = config.get("operator", "OR")
    return _combine(
        [
            _evaluate_node(node, version_raw, version, target, operator == "AND")
            for node in config.get("nodes", [])
        ],
        operator,
    )


def _evaluate_cve(
    cve: dict[str, Any],
    version_raw: str,
    version: tuple[int, ...],
    target: tuple[str, str] | None,
) -> bool | None:
    """Avalia se a CVE se aplica à versão do firmware.

    CVE sem configurations é aplicável; configurações só de outros produtos são
    descartadas.
    """
    configurations = cve.get("configurations", [])
    if not configurations:
        return True
    configurations = [c for c in configurations if not _is_other_product(c, target)]
    if not configurations:
        return False
    return _combine(
        [
            _evaluate_configuration(config, version_raw, version, target)
            for config in configurations
        ],
        "OR",
    )


def _cites_only_other_products(
    cve: dict[str, Any], target: tuple[str, str] | None
) -> bool:
    """Indica se a CVE tem configurações e todas citam só produtos fora do alvo."""
    configurations = cve.get("configurations", [])
    return bool(configurations) and all(
        _is_other_product(c, target) for c in configurations
    )


def _indeterminate_without_version(
    cves: list[dict[str, Any]], target: tuple[str, str] | None
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Classifica as CVEs de um firmware sem versão legível.

    Retorna (aplicáveis, indeterminadas): nenhuma é aplicável; são
    indeterminadas as que não citam só outros produtos.
    """
    return [], [cve for cve in cves if not _cites_only_other_products(cve, target)]


def applicable_cves_for_version(
    version_raw: str | None,
    cache_entry: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Retorna CVEs aplicaveis e indeterminadas, na ordem do cache."""
    cves = list(cache_entry.get("cves", []))
    target = _target_parts(cache_entry)
    if not isinstance(version_raw, str) or not version_raw.strip():
        return _indeterminate_without_version(cves, target)
    version_raw = version_raw.strip()
    version = parse_version(version_raw)
    if version is None:
        return _indeterminate_without_version(cves, target)

    applicable: list[dict[str, Any]] = []
    indeterminate: list[dict[str, Any]] = []
    for cve in cves:
        verdict = _evaluate_cve(cve, version_raw, version, target)
        if verdict is None:
            indeterminate.append(cve)
        elif verdict:
            applicable.append(cve)
    return applicable, indeterminate
