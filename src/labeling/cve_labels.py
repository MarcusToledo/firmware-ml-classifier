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


@dataclass(frozen=True)
class CveLabelThresholds:
    """Limiar CVSS para a classe de CVE crítica."""

    critical_cvss: float = 9.0

    def __post_init__(self) -> None:
        if not isinstance(self.critical_cvss, (int, float)) or isinstance(
            self.critical_cvss, bool
        ):
            raise ValueError("critical_cvss deve ser um número entre 0 e 10")
        if not math.isfinite(self.critical_cvss) or not 0 <= self.critical_cvss <= 10:
            raise ValueError("critical_cvss deve ser um número entre 0 e 10")


_DEFAULT_THRESHOLDS = CveLabelThresholds()


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
    if not isinstance(cvss_max, (int, float)) or isinstance(cvss_max, bool):
        raise ValueError("cvss_max deve ser um número entre 0 e 10")
    if not math.isfinite(cvss_max) or not 0 <= cvss_max <= 10:
        raise ValueError("cvss_max deve ser um número entre 0 e 10")

    if cve_total == 0:
        return LABEL_NO_KNOWN_CVE
    if cvss_max >= thresholds.critical_cvss:
        return LABEL_CRITICAL_CVE
    return LABEL_KNOWN_CVE


def _canonical(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _target_parts(entry: dict[str, Any]) -> tuple[str, str] | None:
    name = entry.get("cpe_name")
    if isinstance(name, str):
        parts = name.split(":")
        if len(parts) == 13:
            return _canonical(parts[3]), _canonical(parts[4]).removesuffix("firmware")
    vendor, model = entry.get("vendor"), entry.get("model")
    if isinstance(vendor, str) and isinstance(model, str):
        return _canonical(vendor), _canonical(model).removesuffix("firmware")
    return None


def _product_of(criteria: object) -> tuple[str, str, str, str] | None:
    """(tipo, vendor, produto, versao) de uma CPE 2.3, ou None se ilegivel."""
    parts = criteria.split(":") if isinstance(criteria, str) else []
    if len(parts) != 13 or parts[:2] != ["cpe", "2.3"]:
        return None
    return (
        parts[2],
        _canonical(parts[3]),
        _canonical(parts[4]).removesuffix("firmware"),
        parts[5],
    )


def _iter_matches(node: dict[str, Any]) -> Iterator[dict[str, Any]]:
    yield from node.get("cpeMatch", [])
    for child in node.get("children", []):
        yield from _iter_matches(child)


def _is_other_product(config: dict[str, Any], target: tuple[str, str] | None) -> bool:
    """True se toda CPE da config e legivel e nenhuma cita o produto-alvo.

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
    """Condicao `vulnerable=false`: plataforma em que o firmware roda.

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
    update_specific = False
    criteria = match.get("criteria")
    if criteria is not None:
        parts = criteria.split(":") if isinstance(criteria, str) else []
        if len(parts) != 13 or parts[:2] != ["cpe", "2.3"]:
            return None
        if target is None:
            return None
        actual = _canonical(parts[3]), _canonical(parts[4]).removesuffix("firmware")
        if actual != target:
            return None if unknown_if_unrelated else False
        exact_version = parts[5]
        # O campo `update` (hotfix, beta, build datado) restringe a CVE a um
        # build que o nome do arquivo nao informa; versao casando vira None.
        update_specific = parts[6] not in {"*", "-"}
        if exact_version not in {"*", "-"}:
            if exact_version.casefold() == version_raw.casefold():
                pass
            else:
                normalized, package_removed = _normalize_cpe_version(
                    exact_version, target[0]
                )
                parsed = parse_version(normalized)
                if parsed is None:
                    return None
                if package_removed and versions_equal(version, parsed):
                    return None
                if (
                    _NUMERIC_VERSION_RE.fullmatch(version_raw)
                    and _NUMERIC_VERSION_RE.fullmatch(normalized)
                    and version_in_range(
                        version,
                        VersionRange(
                            start_including=parsed,
                            end_including=parsed,
                        ),
                    )
                ):
                    pass
                elif _NUMERIC_VERSION_RE.fullmatch(
                    normalized
                ) is None and versions_equal(version, parsed):
                    # Sufixos (build Bxx, beta ou variante regional) mudam a
                    # release, e a NVD os embute em version. Sem build no
                    # firmware, nao da para excluir a CVE; com outro build
                    # conhecido, o resultado deve ser False.
                    if _NUMERIC_VERSION_RE.fullmatch(version_raw) is not None:
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
                elif (
                    _NUMERIC_VERSION_RE.fullmatch(normalized)
                    and _NUMERIC_VERSION_RE.fullmatch(version_raw) is None
                    and versions_equal(version, parsed)
                ):
                    return None
                else:
                    return False
        elif exact_version == "-":
            return None

    bounds: dict[str, tuple[int, ...]] = {}
    vendor = target[0] if target is not None else None
    for key in _BOUND_KEYS:
        if key not in match:
            continue
        value = match[key]
        if not isinstance(value, str):
            return None
        normalized, package_removed = _normalize_cpe_version(value, vendor)
        parsed = parse_version(normalized)
        if parsed is None or _NUMERIC_VERSION_RE.fullmatch(normalized.strip()) is None:
            return None
        if package_removed and versions_equal(version, parsed):
            return None
        bounds[key] = parsed
    if bounds and _NUMERIC_VERSION_RE.fullmatch(version_raw) is None:
        return None
    matched = version_in_range(
        version,
        VersionRange(
            start_including=bounds.get("versionStartIncluding"),
            start_excluding=bounds.get("versionStartExcluding"),
            end_including=bounds.get("versionEndIncluding"),
            end_excluding=bounds.get("versionEndExcluding"),
        ),
    )
    if matched and update_specific:
        return None
    return matched


def _combine(results: list[bool | None], operator: str) -> bool | None:
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


def _evaluate_cve(
    cve: dict[str, Any],
    version_raw: str,
    version: tuple[int, ...],
    target: tuple[str, str] | None,
) -> bool | None:
    configurations = cve.get("configurations", [])
    if not configurations:
        return True
    configurations = [c for c in configurations if not _is_other_product(c, target)]
    if not configurations:
        return False
    config_results = [
        _combine(
            [
                _evaluate_node(
                    node,
                    version_raw,
                    version,
                    target,
                    config.get("operator", "OR") == "AND",
                )
                for node in config.get("nodes", [])
            ],
            config.get("operator", "OR"),
        )
        for config in configurations
    ]
    return _combine(config_results, "OR")


def _cites_only_other_products(
    cve: dict[str, Any], target: tuple[str, str] | None
) -> bool:
    configurations = cve.get("configurations", [])
    return bool(configurations) and all(
        _is_other_product(c, target) for c in configurations
    )


def applicable_cves_for_version(
    version_raw: str | None,
    cache_entry: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Retorna CVEs aplicaveis e indeterminadas, na ordem do cache."""
    cves = list(cache_entry.get("cves", []))
    target = _target_parts(cache_entry)
    if not isinstance(version_raw, str) or not version_raw.strip():
        return [], [cve for cve in cves if not _cites_only_other_products(cve, target)]
    version_raw = version_raw.strip()
    version = parse_version(version_raw)
    if version is None:
        return [], [cve for cve in cves if not _cites_only_other_products(cve, target)]

    applicable: list[dict[str, Any]] = []
    indeterminate: list[dict[str, Any]] = []
    for cve in cves:
        verdict = _evaluate_cve(cve, version_raw, version, target)
        if verdict is None:
            indeterminate.append(cve)
        elif verdict:
            applicable.append(cve)
    return applicable, indeterminate
