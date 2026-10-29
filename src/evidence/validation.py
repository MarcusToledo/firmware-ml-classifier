"""Amostragem, validação das anotações e decisão por detector da T13-A (013).

O sorteio segue a clarificação de 2026-10-27 da spec 013: unidade
``firmware_id``, alocação igual entre fabricantes com redistribuição
alfabética, um achado por firmware e semente por detector. As anotações são
conferidas contra a rubrica congelada em ``configs/detector_validation.yaml``
antes de qualquer contagem.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import platform
import random
from collections import Counter, defaultdict
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from statistics import NormalDist
from typing import Any

import yaml

from src.evidence.binwalk_findings import DETECTOR_VERSIONS as BINWALK_VERSIONS
from src.evidence.patterns import DETECTOR_VERSIONS as PATTERN_VERSIONS
from src.run_metadata import code_commit, file_sha256

CLASS_TRUE = "verdadeiro_candidato"
CLASS_FALSE = "falso_positivo"
CLASS_INDETERMINATE = "indeterminado"
CRITERION_INDETERMINATE = "IND"
DECISION_KEEP = "manter"
DECISION_REFORMULATE = "reformular"
DECISION_REMOVE = "retirar"
ALL_DETECTORS = tuple(sorted({*PATTERN_VERSIONS, *BINWALK_VERSIONS}))
SENSITIVE_DETECTORS = frozenset(
    {"hardcoded_passwords", "credential_pairs", "api_tokens"}
)
SAMPLE_FILENAME = "amostra.csv"
MANIFEST_FILENAME = "manifesto.json"
ITEM_COLUMNS = (
    "item_id",
    "detector",
    "detector_version",
    "fabricante",
    "firmware_id",
    "path",
    "linha",
    "source_sha256",
    "source",
    "context",
    "rubrica_versao",
)
ANNOTATION_COLUMNS = (
    "classe",
    "criterio",
    "motivo_ind",
    "subtipo",
    "justificativa",
    "data",
)
_SOURCE_PREVIEW_CHARS = 160


@dataclass(frozen=True)
class DetectorRubric:
    """Contém o alvo declarado e os códigos de critério de um detector."""

    target: str
    true_codes: frozenset[str]
    false_codes: frozenset[str]
    subtypes: frozenset[str]
    refs: tuple[str, ...]


@dataclass(frozen=True)
class Rubric:
    """Contém a rubrica congelada: versão, data, motivos e critérios."""

    version: str
    frozen_at: date
    reasons: frozenset[str]
    general_false: dict[str, tuple[frozenset[str], frozenset[str]]]
    detectors: dict[str, DetectorRubric]

    def false_codes(self, detector: str) -> frozenset[str]:
        """Retorna os códigos de falso positivo válidos para o detector.

        Inclui os códigos gerais (R3, R7, R9) conforme suas listas de
        exclusão (primeiro elemento) e restrição (segundo elemento).
        """
        codes = set(self.detectors[detector].false_codes)
        for code, (exclude, only) in self.general_false.items():
            if detector in exclude or (only and detector not in only):
                continue
            codes.add(code)
        return frozenset(codes)


@dataclass(frozen=True)
class DecisionRule:
    """Contém os parâmetros pré-registrados da decisão por detector."""

    confidence: float
    cut: float
    min_determined: int
    max_indeterminate_fraction: float


@dataclass(frozen=True)
class ValidationConfig:
    """Contém caminhos, semente, regra de decisão, exclusões e rubrica."""

    source: Path
    findings: Path
    sample_dir: Path
    reports_dir: Path
    seed: int
    target: int
    decision: DecisionRule
    exclusions: dict[int, str]
    rubric: Rubric


def _field(mapping: Any, key: str, path: Path, kind: type) -> Any:
    """Retorna ``mapping[key]`` do tipo esperado ou falha citando a chave."""
    value = mapping.get(key) if isinstance(mapping, dict) else None
    if not isinstance(value, kind) or isinstance(value, bool) and kind is not bool:
        raise ValueError(f"Configuração inválida em {path}: {key}")
    return value


def _codes(mapping: dict[str, Any], key: str, path: Path) -> frozenset[str]:
    """Lê uma lista de códigos textuais, vazia quando ausente e opcional."""
    values = mapping.get(key, [])
    if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
        raise ValueError(f"Configuração inválida em {path}: {key}")
    return frozenset(values)


def _detector_rubric(raw: Any, name: str, path: Path) -> DetectorRubric:
    """Valida a entrada de um detector na rubrica."""
    if not isinstance(raw, dict):
        raise ValueError(f"Configuração inválida em {path}: rubric.detectors.{name}")
    true_codes = _codes(raw, "verdadeiro", path)
    false_codes = _codes(raw, "falso", path)
    if not true_codes or not false_codes or true_codes & false_codes:
        raise ValueError(
            f"Configuração inválida em {path}: rubric.detectors.{name} precisa de "
            "códigos verdadeiro e falso disjuntos"
        )
    return DetectorRubric(
        target=_field(raw, "target", path, str),
        true_codes=true_codes,
        false_codes=false_codes,
        subtypes=_codes(raw, "subtypes", path),
        refs=tuple(sorted(_codes(raw, "refs", path))),
    )


def _rubric(raw: Any, path: Path) -> Rubric:
    """Valida a rubrica congelada e seus detectores conhecidos."""
    detectors_raw = _field(raw, "detectors", path, dict)
    unknown = sorted(set(detectors_raw) - set(ALL_DETECTORS))
    if unknown:
        raise ValueError(f"Configuração inválida em {path}: detectores {unknown}")
    general = {
        code: (_codes(rule, "exclude", path), _codes(rule, "only", path))
        for code, rule in _field(raw, "general_false_positive", path, dict).items()
    }
    frozen_at = _field(raw, "frozen_at", path, str)
    return Rubric(
        version=_field(raw, "version", path, str),
        frozen_at=date.fromisoformat(frozen_at),
        reasons=_codes(raw, "indeterminate_reasons", path),
        general_false=general,
        detectors={
            name: _detector_rubric(entry, name, path)
            for name, entry in detectors_raw.items()
        },
    )


def _decision_rule(raw: Any, path: Path) -> DecisionRule:
    """Valida a regra de decisão (Wilson, corte e vetos)."""
    rule = DecisionRule(
        confidence=float(_field(raw, "confidence", path, (int, float))),
        cut=float(_field(raw, "cut", path, (int, float))),
        min_determined=_field(raw, "min_determined", path, int),
        max_indeterminate_fraction=float(
            _field(raw, "max_indeterminate_fraction", path, (int, float))
        ),
    )
    if not 0 < rule.confidence < 1 or not 0 < rule.cut < 1:
        raise ValueError(f"Configuração inválida em {path}: decision")
    if rule.min_determined < 1 or not 0 <= rule.max_indeterminate_fraction <= 1:
        raise ValueError(
            f"Configuração inválida em {path}: decision.min_determined ≥ 1 e "
            "decision.max_indeterminate_fraction em [0, 1]"
        )
    return rule


def _exclusions(raw: Any, path: Path) -> dict[int, str]:
    """Lê as exclusões do piloto como {linha: chave do achado}."""
    if not isinstance(raw, list):
        raise ValueError(f"Configuração inválida em {path}: pilot_exclusions")
    return {
        _field(item, "line", path, int): _field(item, "key", path, str) for item in raw
    }


def load_validation_config(path: Path) -> ValidationConfig:
    """Lê e valida o protocolo congelado da T13-A.

    Levanta FileNotFoundError sem o arquivo e ValueError para YAML ilegível
    ou campos fora do contrato.
    """
    if not path.is_file():
        raise FileNotFoundError(f"--config não encontrado: {path}")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"Configuração inválida em {path}: YAML ilegível") from exc
    sampling = _field(raw, "sampling", path, dict)
    return ValidationConfig(
        source=path,
        findings=Path(_field(raw, "findings", path, str)),
        sample_dir=Path(_field(raw, "sample_dir", path, str)),
        reports_dir=Path(_field(raw, "reports_dir", path, str)),
        seed=_field(sampling, "seed", path, int),
        target=_field(sampling, "target_per_detector", path, int),
        decision=_decision_rule(_field(raw, "decision", path, dict), path),
        exclusions=_exclusions(raw.get("pilot_exclusions"), path),
        rubric=_rubric(_field(raw, "rubric", path, dict), path),
    )


# ---------------------------------------------------------------------------
# População
# ---------------------------------------------------------------------------


def finding_key(record: dict[str, Any]) -> str:
    """Retorna a chave de um achado: SHA256 de detector, ID, source e context."""
    parts = (
        record["detector"],
        record["firmware_id"],
        record["source"],
        record["context"],
    )
    return hashlib.sha256("\0".join(parts).encode("utf-8")).hexdigest()


def _iter_findings(path: Path) -> Iterator[tuple[int, dict[str, Any]]]:
    """Produz (linha base 1, registro) do JSONL ou falha citando a linha."""
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"JSONL inválido em {path}:{line_no}") from exc
            yield line_no, record


@dataclass
class _PathStats:
    """Acumula, por detector, firmware e path, o multiconjunto de achados."""

    total: int = 0
    digest: int = 0
    kept: int = 0


@dataclass(frozen=True)
class Population:
    """Contém, por detector, fabricante e firmware, o path representante e N."""

    strata: dict[str, dict[str, dict[str, tuple[str, int]]]]
    excluded: int
    excluded_keys: frozenset[str]


def _accumulate(
    path: Path, exclusions: dict[int, str]
) -> tuple[dict[tuple[str, str, str], _PathStats], int, frozenset[str]]:
    """Lê o JSONL e acumula estatísticas por path, sem as cópias do piloto.

    A primeira passagem confere as linhas do piloto; a segunda conta.
    Retorna (estatísticas, achados excluídos, chaves excluídas).
    """
    keys = frozenset(exclusions.values())
    found: dict[int, str] = {}
    stats: dict[tuple[str, str, str], _PathStats] = defaultdict(_PathStats)
    excluded = 0
    for line_no, record in _iter_findings(path):
        key = finding_key(record)
        if line_no in exclusions:
            found[line_no] = key
        entry = stats[(record["detector"], record["firmware_id"], record["path"])]
        entry.total += 1
        entry.digest = (entry.digest + int(key, 16)) % (1 << 256)
        if key in keys:
            excluded += 1
            continue
        entry.kept += 1
    if found != exclusions:
        mismatched = sorted(set(exclusions.items()) - set(found.items()))
        raise ValueError(
            f"Exclusões do piloto não conferem com {path}: {mismatched[:5]}"
        )
    return stats, excluded, keys


def _check_aliases(stats: dict[tuple[str, str, str], _PathStats]) -> None:
    """Exige multiconjunto igual e fabricante único entre aliases de um ID."""
    groups: dict[tuple[str, str], list[tuple[str, _PathStats]]] = defaultdict(list)
    for (detector, firmware_id, path), entry in stats.items():
        groups[(detector, firmware_id)].append((path, entry))
    for (detector, firmware_id), entries in groups.items():
        vendors = {path.split("/", 1)[0] for path, _ in entries}
        signatures = {(entry.total, entry.digest) for _, entry in entries}
        if len(vendors) > 1 or len(signatures) > 1:
            raise ValueError(
                f"Aliases divergentes em {detector}/{firmware_id}: "
                f"{sorted(path for path, _ in entries)}"
            )


def build_population(path: Path, exclusions: dict[int, str]) -> Population:
    """Monta a população por detector, fabricante e firmware representante.

    O representante é o menor ``path`` do ``firmware_id``; o fabricante é o
    prefixo desse path. Firmwares sem achados após a exclusão saem.
    """
    stats, excluded, keys = _accumulate(path, exclusions)
    _check_aliases(stats)
    strata: dict[str, dict[str, dict[str, tuple[str, int]]]] = defaultdict(
        lambda: defaultdict(dict)
    )
    for (detector, firmware_id, firmware_path), entry in sorted(stats.items()):
        vendor_ids = strata[detector][firmware_path.split("/", 1)[0]]
        if firmware_id in vendor_ids or entry.kept == 0:
            continue
        vendor_ids[firmware_id] = (firmware_path, entry.kept)
    clean = {
        detector: {vendor: ids for vendor, ids in vendors.items() if ids}
        for detector, vendors in strata.items()
    }
    return Population({d: v for d, v in clean.items() if v}, excluded, keys)


# ---------------------------------------------------------------------------
# Sorteio
# ---------------------------------------------------------------------------


def allocate(capacity: dict[str, int], target: int) -> tuple[dict[str, int], list[str]]:
    """Divide o alvo igualmente entre fabricantes e redistribui a falta.

    A cota base é ``target // n``; o resto vai aos primeiros em ordem
    alfabética. A falta é redistribuída em rodadas alfabéticas, +1 por
    fabricante com capacidade restante, até o alvo ou o esgotamento.
    Retorna (alocação, fabricantes que receberam redistribuição, em ordem).
    """
    vendors = sorted(capacity)
    base, extra = divmod(target, len(vendors))
    allocation = {
        vendor: min(base + (1 if index < extra else 0), capacity[vendor])
        for index, vendor in enumerate(vendors)
    }
    received: list[str] = []
    while sum(allocation.values()) < target:
        spare = [vendor for vendor in vendors if allocation[vendor] < capacity[vendor]]
        if not spare:
            break
        for vendor in spare:
            if sum(allocation.values()) == target:
                break
            allocation[vendor] += 1
            received.append(vendor)
    return allocation, received


@dataclass(frozen=True)
class Pick:
    """Identifica o achado sorteado: posição entre os achados do path."""

    detector: str
    vendor: str
    firmware_id: str
    path: str
    index: int


@dataclass(frozen=True)
class DetectorDraw:
    """Contém alocação, redistribuição e achados sorteados de um detector."""

    allocation: dict[str, int]
    redistributed: list[str]
    picks: list[Pick]


def draw_detector(
    detector: str, strata: dict[str, dict[str, tuple[str, int]]], seed: int, target: int
) -> DetectorDraw:
    """Sorteia firmwares por fabricante e um achado por firmware.

    Usa ``random.Random(f"{seed}/{detector}")`` sobre IDs ordenados, para que
    um detector não altere o sorteio dos demais.
    """
    rng = random.Random(f"{seed}/{detector}")
    capacity = {vendor: len(ids) for vendor, ids in strata.items()}
    allocation, redistributed = allocate(capacity, target)
    picks: list[Pick] = []
    for vendor in sorted(strata):
        for firmware_id in rng.sample(sorted(strata[vendor]), allocation[vendor]):
            path, count = strata[vendor][firmware_id]
            picks.append(
                Pick(detector, vendor, firmware_id, path, rng.randrange(count))
            )
    return DetectorDraw(allocation, redistributed, picks)


def _check_rubric_coverage(population: Population, rubric: Rubric) -> None:
    """Exige critério na rubrica para todo detector presente na população."""
    missing = sorted(set(population.strata) - set(rubric.detectors))
    if missing:
        raise ValueError(f"Detectores presentes sem rubrica: {missing}")


def _fetch_picks(
    path: Path, picks: list[Pick], excluded_keys: frozenset[str]
) -> dict[Pick, tuple[int, dict[str, Any]]]:
    """Relê o JSONL e devolve (linha, registro) de cada achado sorteado."""
    wanted: dict[tuple[str, str, str], dict[int, Pick]] = defaultdict(dict)
    for pick in picks:
        wanted[(pick.detector, pick.firmware_id, pick.path)][pick.index] = pick
    seen: Counter[tuple[str, str, str]] = Counter()
    fetched: dict[Pick, tuple[int, dict[str, Any]]] = {}
    for line_no, record in _iter_findings(path):
        key = (record["detector"], record["firmware_id"], record["path"])
        if key not in wanted or finding_key(record) in excluded_keys:
            continue
        pick = wanted[key].get(seen[key])
        seen[key] += 1
        if pick is not None:
            fetched[pick] = (line_no, record)
    if len(fetched) != len(picks):
        raise RuntimeError(f"Achados sorteados não encontrados em {path}")
    return fetched


def _sample_rows(
    fetched: dict[Pick, tuple[int, dict[str, Any]]], seed: int, rubric_version: str
) -> list[dict[str, Any]]:
    """Embaralha os achados pela semente e monta as linhas da planilha."""
    ordered = sorted(fetched.items(), key=lambda item: item[1][0])
    random.Random(f"{seed}/ordem").shuffle(ordered)
    rows = []
    for number, (pick, (line_no, record)) in enumerate(ordered, start=1):
        rows.append(
            {
                "item_id": f"T13A-{number:03d}",
                "detector": pick.detector,
                "detector_version": record["detector_version"],
                "fabricante": pick.vendor,
                "firmware_id": pick.firmware_id,
                "path": pick.path,
                "linha": line_no,
                "source_sha256": hashlib.sha256(record["source"].encode()).hexdigest(),
                "source": record["source"],
                "context": record["context"],
                "rubrica_versao": rubric_version,
                **{column: "" for column in ANNOTATION_COLUMNS},
            }
        )
    return rows


@dataclass(frozen=True)
class SampleResult:
    """Contém as linhas da planilha e o manifesto do sorteio."""

    rows: list[dict[str, Any]]
    manifest: dict[str, Any]


def _population_summary(population: Population) -> dict[str, Any]:
    """Resume firmwares e achados por detector e fabricante."""
    return {
        detector: {
            vendor: {
                "firmwares": len(ids),
                "achados": sum(count for _, count in ids.values()),
            }
            for vendor, ids in sorted(vendors.items())
        }
        for detector, vendors in sorted(population.strata.items())
    }


def build_sample(config: ValidationConfig) -> SampleResult:
    """Monta população, sorteia cada detector e prepara planilha e manifesto."""
    population = build_population(config.findings, config.exclusions)
    _check_rubric_coverage(population, config.rubric)
    draws = {
        detector: draw_detector(detector, strata, config.seed, config.target)
        for detector, strata in sorted(population.strata.items())
    }
    picks = [pick for draw in draws.values() for pick in draw.picks]
    fetched = _fetch_picks(config.findings, picks, population.excluded_keys)
    rows = _sample_rows(fetched, config.seed, config.rubric.version)
    manifest = {
        "spec": "013-validacao-detectores",
        "findings": config.findings.as_posix(),
        "findings_sha256": file_sha256(config.findings),
        "config": config.source.as_posix(),
        "config_sha256": file_sha256(config.source),
        "code_commit": code_commit(),
        "python": platform.python_version(),
        "seed": config.seed,
        "target_per_detector": config.target,
        "rubric_version": config.rubric.version,
        "pilot_excluded_findings": population.excluded,
        "population": _population_summary(population),
        "allocation": {d: draw.allocation for d, draw in draws.items()},
        "redistributed": {d: draw.redistributed for d, draw in draws.items()},
        "items": [{c: row[c] for c in ITEM_COLUMNS if c != "source"} for row in rows],
    }
    return SampleResult(rows, manifest)


def write_sample(result: SampleResult, sample_dir: Path) -> dict[str, Path]:
    """Grava planilha e manifesto; recusa sobrescrever um sorteio existente.

    Levanta FileExistsError se a planilha já existir: refazer o sorteio
    depois de ver itens violaria o pré-registro (013/FR-002, FR-003).
    """
    paths = {
        "sample": sample_dir / SAMPLE_FILENAME,
        "manifest": sample_dir / MANIFEST_FILENAME,
    }
    if paths["sample"].exists() or paths["manifest"].exists():
        raise FileExistsError(f"Sorteio já existe em {sample_dir}; não sobrescrevo")
    sample_dir.mkdir(parents=True, exist_ok=True)
    with paths["sample"].open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=[*ITEM_COLUMNS, *ANNOTATION_COLUMNS])
        writer.writeheader()
        writer.writerows(result.rows)
    manifest = {
        **result.manifest,
        "sample_sha256": file_sha256(paths["sample"]),
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    paths["manifest"].write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return paths


# ---------------------------------------------------------------------------
# Anotações, contagens e decisão
# ---------------------------------------------------------------------------


def _annotation_errors(
    row: dict[str, str], rubric: Rubric, frozen_version: str
) -> list[str]:
    """Lista as violações da rubrica numa linha anotada."""
    detector, label, criterion = row["detector"], row["classe"], row["criterio"]
    entry = rubric.detectors[detector]
    allowed = {
        CLASS_TRUE: entry.true_codes,
        CLASS_FALSE: rubric.false_codes(detector),
        CLASS_INDETERMINATE: frozenset({CRITERION_INDETERMINATE}),
    }
    errors = []
    if label not in allowed:
        return [f"classe inválida {label!r}"]
    if criterion not in allowed[label]:
        errors.append(f"critério {criterion!r} não vale para {label} em {detector}")
    if (label == CLASS_INDETERMINATE) != bool(row["motivo_ind"]):
        errors.append("motivo_ind é obrigatório só para indeterminado")
    elif row["motivo_ind"] and row["motivo_ind"] not in rubric.reasons:
        errors.append(f"motivo_ind inválido {row['motivo_ind']!r}")
    needs_subtype = label == CLASS_TRUE and bool(entry.subtypes)
    if needs_subtype != bool(row["subtipo"]) or (
        row["subtipo"] and row["subtipo"] not in entry.subtypes
    ):
        errors.append(f"subtipo {row['subtipo']!r} inválido para {label} em {detector}")
    if not row["justificativa"].strip():
        errors.append("justificativa vazia")
    if row["rubrica_versao"] != frozen_version:
        errors.append(f"rubrica_versao {row['rubrica_versao']!r} ≠ {frozen_version!r}")
    return errors + _date_errors(row["data"], rubric.frozen_at)


def _date_errors(value: str, frozen_at: date) -> list[str]:
    """Exige data ISO da anotação igual ou posterior ao congelamento."""
    try:
        annotated = date.fromisoformat(value)
    except ValueError:
        return [f"data inválida {value!r}"]
    if annotated < frozen_at:
        return [f"data {value} anterior ao congelamento da rubrica"]
    return []


def _check_against_manifest(
    rows: list[dict[str, str]], manifest: dict[str, Any]
) -> None:
    """Exige os mesmos itens e campos imutáveis registrados no sorteio.

    Compara todas as colunas de ``ITEM_COLUMNS`` com o manifesto; o texto
    ``source``, ausente do manifesto, é conferido pelo SHA256 recalculado.
    """
    fields = [c for c in ITEM_COLUMNS if c != "source"]
    expected = {
        item["item_id"]: tuple(str(item[c]) for c in fields)
        for item in manifest["items"]
    }
    actual = {
        row["item_id"]: tuple(
            hashlib.sha256(row["source"].encode()).hexdigest()
            if c == "source_sha256"
            else row[c]
            for c in fields
        )
        for row in rows
    }
    if actual != expected or len(rows) != len(expected):
        changed = sorted(
            k
            for k in expected.keys() | actual.keys()
            if expected.get(k) != actual.get(k)
        )
        raise ValueError(f"Planilha diverge do manifesto do sorteio: {changed[:10]}")


def load_annotations(
    config: ValidationConfig,
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    """Lê a planilha anotada e o manifesto, conferindo integridade e rubrica.

    Levanta ValueError se a configuração mudou depois do sorteio, se a
    planilha não corresponde ao manifesto ou se alguma anotação viola a
    rubrica; a mensagem lista os itens com problema.
    """
    manifest_path = config.sample_dir / MANIFEST_FILENAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["config_sha256"] != file_sha256(config.source):
        raise ValueError(
            f"{config.source} mudou depois do sorteio; rubrica não congelada"
        )
    with (config.sample_dir / SAMPLE_FILENAME).open(encoding="utf-8", newline="") as h:
        rows = list(csv.DictReader(h))
    _check_against_manifest(rows, manifest)
    problems = {
        row["item_id"]: errors
        for row in rows
        if (errors := _annotation_errors(row, config.rubric, config.rubric.version))
    }
    if problems:
        listed = "; ".join(
            f"{k}: {', '.join(v)}" for k, v in sorted(problems.items())[:10]
        )
        raise ValueError(f"{len(problems)} anotações inválidas: {listed}")
    return rows, manifest


def wilson_interval(
    successes: int, trials: int, confidence: float
) -> tuple[float, float] | None:
    """Retorna o IC de Wilson bilateral, ou None quando não há tentativas."""
    if trials == 0:
        return None
    z = NormalDist().inv_cdf(1 - (1 - confidence) / 2)
    p = successes / trials
    denominator = 1 + z * z / trials
    center = (p + z * z / (2 * trials)) / denominator
    half = z / denominator * math.sqrt(p * (1 - p) / trials + z * z / (4 * trials**2))
    return max(0.0, center - half), min(1.0, center + half)


@dataclass(frozen=True)
class DetectorResult:
    """Contém contagens, intervalo e decisão de um detector."""

    detector: str
    n_true: int
    n_false: int
    n_indeterminate: int
    interval: tuple[float, float] | None
    decision: str | None
    reason: str
    by_vendor: dict[str, dict[str, int]]
    criteria: dict[str, int]

    @property
    def n_total(self) -> int:
        """Retorna o total de achados anotados do detector."""
        return self.n_true + self.n_false + self.n_indeterminate


def decide(
    n_true: int, n_false: int, n_indeterminate: int, rule: DecisionRule
) -> tuple[str, str, tuple[float, float] | None]:
    """Aplica a regra pré-registrada; retorna (decisão, motivo, intervalo)."""
    determined = n_true + n_false
    total = determined + n_indeterminate
    interval = wilson_interval(n_true, determined, rule.confidence)
    if n_indeterminate > total * rule.max_indeterminate_fraction:
        return DECISION_REFORMULATE, "indeterminados acima do limite", interval
    if determined < rule.min_determined:
        return DECISION_REFORMULATE, "casos determinados abaixo do mínimo", interval
    assert interval is not None
    if interval[0] >= rule.cut:
        return DECISION_KEEP, f"limite inferior ≥ {rule.cut}", interval
    if interval[1] < rule.cut:
        return DECISION_REMOVE, f"limite superior < {rule.cut}", interval
    return DECISION_REFORMULATE, f"intervalo contém {rule.cut}", interval


def summarize(rows: list[dict[str, str]], rule: DecisionRule) -> list[DetectorResult]:
    """Conta classes por detector e fabricante e aplica a decisão.

    Detectores sem itens (ausentes da população) ficam sem decisão e com
    estimativa não calculável, sem inferir precisão zero.
    """
    results = []
    for detector in ALL_DETECTORS:
        own = [row for row in rows if row["detector"] == detector]
        labels = Counter(row["classe"] for row in own)
        by_vendor: dict[str, dict[str, int]] = defaultdict(
            lambda: dict.fromkeys((CLASS_TRUE, CLASS_FALSE, CLASS_INDETERMINATE), 0)
        )
        for row in own:
            by_vendor[row["fabricante"]][row["classe"]] += 1
        counts = (labels[CLASS_TRUE], labels[CLASS_FALSE], labels[CLASS_INDETERMINATE])
        if own:
            decision, reason, interval = decide(*counts, rule)
        else:
            decision, reason, interval = None, "ausente na população", None
        criteria = Counter(row["criterio"] for row in own)
        results.append(
            DetectorResult(
                detector,
                *counts,
                interval,
                decision,
                reason,
                dict(sorted(by_vendor.items())),
                dict(sorted(criteria.items())),
            )
        )
    return results


# ---------------------------------------------------------------------------
# Relatório compartilhável (013/FR-007)
# ---------------------------------------------------------------------------

_LIMITATIONS = (
    "`verdadeiro candidato` indica que a string contém o alvo declarado do "
    "detector; não é vulnerabilidade confirmada nem CVE.",
    "A fração não ponderada descreve a composição dos casos determinados da "
    "amostra (um achado por firmware, alocação igual por fabricante), não a "
    "precisão global; o IC de Wilson é critério operacional aproximado, pois "
    "firmwares distintos podem compartilhar SDK ou família.",
    "Um único anotador (o pesquisador); não há medida de concordância.",
    "A rubrica não verifica bytes da imagem: assinaturas do Binwalk só são "
    "recusadas quando a própria descrição é implausível (R9).",
    "A T13-B (011/FR-005, ablação B2−D) mede utilidade preditiva "
    "separadamente e não valida esta rubrica.",
)


def redact_source(row: dict[str, str]) -> str:
    """Retorna o texto compartilhável do achado.

    Detectores de credencial e token trocam a string inteira por
    ``<redigido:len=N,sha256=xxxxxxxx>``; os demais são truncados.
    """
    source = row["source"]
    if row["detector"] in SENSITIVE_DETECTORS:
        digest = hashlib.sha256(source.encode()).hexdigest()[:8]
        return f"<redigido:len={len(source)},sha256={digest}>"
    if len(source) > _SOURCE_PREVIEW_CHARS:
        return source[:_SOURCE_PREVIEW_CHARS] + "…"
    return source


def _cell(text: str) -> str:
    """Escapa texto para uma célula de tabela Markdown."""
    return text.replace("|", "\\|").replace("\n", " ").replace("`", "'")


def _interval_text(interval: tuple[float, float] | None) -> str:
    """Formata o intervalo ou declara a indisponibilidade."""
    if interval is None:
        return "não calculável (denominador zero)"
    return f"[{interval[0]:.3f}; {interval[1]:.3f}]"


def _summary_lines(results: list[DetectorResult], rubric: Rubric) -> list[str]:
    """Monta a tabela de contagens, intervalos e decisões por detector."""
    lines = [
        "|Detector|VC|FP|IND|Total|Wilson 95%|Decisão|Motivo|Specs|",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for result in results:
        entry = rubric.detectors.get(result.detector)
        refs = ", ".join(entry.refs) if entry else "—"
        lines.append(
            f"|`{result.detector}`|{result.n_true}|{result.n_false}|"
            f"{result.n_indeterminate}|{result.n_total}|"
            f"{_interval_text(result.interval)}|{result.decision or '—'}|"
            f"{result.reason}|{refs}|"
        )
    return lines


def _detail_lines(results: list[DetectorResult]) -> list[str]:
    """Lista contagens por fabricante e critérios usados por detector."""
    lines = []
    for result in results:
        if not result.n_total:
            continue
        lines.append(f"### `{result.detector}`")
        lines.append("")
        for vendor, counts in result.by_vendor.items():
            lines.append(
                f"- {vendor}: VC {counts[CLASS_TRUE]}, FP {counts[CLASS_FALSE]}, "
                f"IND {counts[CLASS_INDETERMINATE]}"
            )
        criteria = ", ".join(f"{code} ×{n}" for code, n in result.criteria.items())
        lines.extend([f"- Critérios: {criteria}", ""])
    return lines


def _item_lines(rows: list[dict[str, str]]) -> list[str]:
    """Monta a tabela de anotações com o texto redigido."""
    lines = [
        "|Item|Detector|Fabricante|Classe|Critério|Texto (redigido)|Justificativa|",
        "|---|---|---|---|---|---|---|",
    ]
    for row in sorted(rows, key=lambda r: (r["detector"], r["item_id"])):
        label = row["classe"] + (f" ({row['motivo_ind']})" if row["motivo_ind"] else "")
        lines.append(
            f"|{row['item_id']}|`{row['detector']}`|{row['fabricante']}|{label}|"
            f"{row['criterio']}|`{_cell(redact_source(row))}`|"
            f"{_cell(row['justificativa'])}|"
        )
    return lines


def render_report(
    results: list[DetectorResult],
    rows: list[dict[str, str]],
    manifest: dict[str, Any],
    config: ValidationConfig,
    generated_at: str,
) -> str:
    """Gera o relatório Markdown compartilhável, sem texto sensível."""
    rule = config.decision
    header = [
        "# T13-A — validação semântica dos detectores (013)",
        "",
        f"- Gerado em: {generated_at}",
        f"- Sorteio: {manifest['created_at']}; semente {manifest['seed']}; "
        f"alvo {manifest['target_per_detector']} por detector",
        f"- Entrada: `{manifest['findings']}` (sha256 {manifest['findings_sha256']})",
        f"- Configuração: `{manifest['config']}` (sha256 {manifest['config_sha256']})",
        f"- Rubrica v{config.rubric.version}, congelada em {config.rubric.frozen_at}",
        f"- Código do sorteio: {manifest['code_commit']}; Python {manifest['python']}",
        f"- Achados do piloto excluídos (com cópias): "
        f"{manifest['pilot_excluded_findings']}",
        f"- Regra: Wilson {rule.confidence:.0%}; manter se inferior ≥ {rule.cut}; "
        f"retirar se superior < {rule.cut}; reformular nos demais casos, com "
        f"indeterminados > {rule.max_indeterminate_fraction:.0%} ou menos de "
        f"{rule.min_determined} determinados",
        "- Decisão anterior ao treino; nenhuma predição de teste foi consultada.",
        "",
        "## Decisões",
        "",
    ]
    body = [
        "",
        "## Contagens por fabricante",
        "",
        *_detail_lines(results),
        "## Limitações",
        "",
        *(f"- {text}" for text in _LIMITATIONS),
        "",
        "## Anotações",
        "",
        *_item_lines(rows),
    ]
    return "\n".join([*header, *_summary_lines(results, config.rubric), *body]) + "\n"


def _result_json(result: DetectorResult) -> dict[str, Any]:
    """Serializa o resultado de um detector para o JSON do relatório."""
    return {
        "detector": result.detector,
        "n_verdadeiro": result.n_true,
        "n_falso": result.n_false,
        "n_indeterminado": result.n_indeterminate,
        "n_total": result.n_total,
        "wilson": list(result.interval) if result.interval else None,
        "decisao": result.decision,
        "motivo": result.reason,
        "por_fabricante": result.by_vendor,
        "criterios": result.criteria,
    }


def write_report(
    results: list[DetectorResult],
    rows: list[dict[str, str]],
    manifest: dict[str, Any],
    config: ValidationConfig,
) -> Path:
    """Grava relatório Markdown e JSON em ``reports/t13a_<timestamp>/``."""
    now = datetime.now(timezone.utc)
    directory = config.reports_dir / f"t13a_{now.strftime('%Y%m%dT%H%M%SZ')}"
    directory.mkdir(parents=True, exist_ok=False)
    generated_at = now.isoformat(timespec="seconds")
    report = render_report(results, rows, manifest, config, generated_at)
    (directory / "relatorio.md").write_text(report, encoding="utf-8")
    payload = {
        "generated_at": generated_at,
        "sample_created_at": manifest["created_at"],
        "config_sha256": manifest["config_sha256"],
        "rubric_version": config.rubric.version,
        "detectores": [_result_json(result) for result in results],
    }
    (directory / "resultado.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return directory
