"""Exercita agrupamento, integridade e cobertura da partição 009."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
import yaml

from src.dataset import contract as c
from src.dataset.partition import (
    FOLDS_FILENAME,
    PartitionConfig,
    build_groups,
    build_partition,
    check_no_crossing,
    grouped_folds,
    load_folds,
    load_partition_config,
    load_training_inputs,
    model_key,
    write_folds,
)
from src.run_metadata import file_sha256


def make_inputs(directory: Path, count: int = 40, rare: bool = False) -> pd.DataFrame:
    """Grava artefatos 008 sintéticos com três classes e hashes reais."""
    directory.mkdir(parents=True, exist_ok=True)
    rows = [
        {
            "firmware_id": f"id-{index:03}",
            "security_level": c.TARGET_CLASSES[0 if rare and index > 1 else index % 3],
            "feature": index,
        }
        for index in range(count)
    ]
    table = pd.DataFrame(rows)
    table.to_parquet(directory / c.TABLE_FILENAME, index=False)
    with (directory / c.PROVENANCE_FILENAME).open("w", encoding="utf-8") as output:
        for index, row in enumerate(rows):
            aliases = [
                {
                    "meta_path": f"asus/m{index}/file.bin",
                    "vendor": "asus",
                    "model": f"m{index}",
                }
            ]
            if index == 0:
                aliases.append(
                    {
                        "meta_path": "other/m0/file.bin",
                        "vendor": "other",
                        "model": "other0",
                    }
                )
            output.write(
                json.dumps(
                    {
                        "firmware_id": row["firmware_id"],
                        "in_table": True,
                        "aliases": aliases,
                    }
                )
                + "\n"
            )
    meta = {
        "outputs": {
            key: {"sha256": file_sha256(directory / name)}
            for key, name in (
                ("table", c.TABLE_FILENAME),
                ("provenance", c.PROVENANCE_FILENAME),
            )
        }
    }
    (directory / c.META_FILENAME).write_text(json.dumps(meta), encoding="utf-8")
    return table


def _aliases(*rows: tuple[str, str, str]) -> pd.DataFrame:
    """Constrói aliases no formato expandido da proveniência."""
    return pd.DataFrame(
        [
            {
                "firmware_id": identifier,
                "meta_path": f"{identifier}/{index}",
                "vendor": vendor,
                "model": model,
            }
            for index, (identifier, vendor, model) in enumerate(rows)
        ]
    )


def test_transitive_groups_ignore_input_order() -> None:
    """Une aliases transitivos e mantém rótulos estáveis após permutação."""
    aliases = _aliases(
        ("b", "asus", "B"),
        ("a", "asus", "A"),
        ("a", "asus", "B"),
        ("c", "asus", "C"),
    )
    assert build_groups(aliases) == {"a": "g:a", "b": "g:a", "c": "g:c"}
    assert build_groups(aliases.sample(frac=1, random_state=31)) == build_groups(
        aliases
    )


def test_model_normalization_keeps_revisions() -> None:
    """Iguala pontuação e caixa, sem confundir revisões distintas."""
    assert model_key("asus", "rt-n13u") == model_key("ASUS", "RT_N13U ")
    assert model_key("tp_link", "tl_er604w") == model_key("tp_link", "tl-er604w")
    assert model_key("asus", "rt-b1") != model_key("asus", "rt-c1")


def test_excluded_alias_does_not_join_groups(tmp_path: Path) -> None:
    """Ignora alias pertencente a linha explicitamente fora da tabela."""
    make_inputs(tmp_path, count=2)
    provenance_path = tmp_path / c.PROVENANCE_FILENAME
    with provenance_path.open("a", encoding="utf-8") as output:
        output.write(
            json.dumps(
                {
                    "firmware_id": "excluded",
                    "in_table": False,
                    "aliases": [
                        {"meta_path": "excluded", "vendor": "asus", "model": "m0"}
                    ],
                }
            )
            + "\n"
        )
    meta_path = tmp_path / c.META_FILENAME
    meta = json.loads(meta_path.read_text())
    meta["outputs"]["provenance"]["sha256"] = file_sha256(provenance_path)
    meta_path.write_text(json.dumps(meta))
    inputs = load_training_inputs(tmp_path)
    assert set(inputs.provenance["firmware_id"]) == {"id-000", "id-001"}
    assert "excluded" not in build_groups(inputs.provenance)


def test_crossing_guard_rejects_id_and_model() -> None:
    """Rejeita tanto ID duplicado quanto modelo compartilhado entre lados."""
    aliases = _aliases(("a", "asus", "rt-n13u"), ("b", "ASUS", "RT_N13U "))
    for train, test, fragment in (("a", "a", "firmware_id"), ("a", "b", "modelo")):
        folds = pd.DataFrame(
            [
                {"repeat": 0, "fold": 0, "firmware_id": train, "role": "train"},
                {"repeat": 0, "fold": 0, "firmware_id": test, "role": "test"},
            ]
        )
        with pytest.raises(ValueError, match=f"cruzamento treino/teste.*{fragment}"):
            check_no_crossing(folds, aliases)


def test_real_folds_have_one_test_per_id_and_no_crossing(tmp_path: Path) -> None:
    """Distribui os 40 IDs em cinco testes únicos sem vazamento."""
    table = make_inputs(tmp_path)
    aliases = load_training_inputs(tmp_path).provenance
    folds = grouped_folds(
        table.sample(frac=1, random_state=9), build_groups(aliases), 5, 7
    )
    check_no_crossing(folds, aliases)
    assert set(folds["seed"]) == {7}
    test_counts = folds.groupby("firmware_id")["role"].apply(
        lambda roles: (roles == "test").sum()
    )
    assert test_counts.eq(1).all()
    assert folds.groupby("firmware_id").size().eq(5).all()
    assert list(folds.columns) == [
        "repeat",
        "seed",
        "fold",
        "firmware_id",
        "role",
        "group",
    ]
    assert folds.equals(grouped_folds(table, build_groups(aliases), 5, 7))


@pytest.mark.parametrize(
    "filename,key",
    [(c.TABLE_FILENAME, "table"), (c.PROVENANCE_FILENAME, "provenance")],
)
def test_training_inputs_reject_tampering(
    tmp_path: Path, filename: str, key: str
) -> None:
    """Rejeita os dois tipos de entrada adulterada exibindo ambos SHA256."""
    make_inputs(tmp_path)
    meta = json.loads((tmp_path / c.META_FILENAME).read_text())
    registered = meta["outputs"][key]["sha256"]
    target = tmp_path / filename
    target.write_bytes(target.read_bytes() + b"x")
    with pytest.raises(ValueError) as error:
        load_training_inputs(tmp_path)
    assert registered in str(error.value)
    assert file_sha256(target) in str(error.value)


@pytest.mark.parametrize(
    "filename", [c.TABLE_FILENAME, c.PROVENANCE_FILENAME, FOLDS_FILENAME]
)
def test_load_folds_rejects_tampered_artifact(tmp_path: Path, filename: str) -> None:
    """Rejeita cópias adulteradas da tabela, proveniência ou folds."""
    make_inputs(tmp_path)
    write_folds(build_partition(PartitionConfig(5, (0,), tmp_path)), tmp_path)
    target = tmp_path / filename
    target.write_bytes(target.read_bytes() + b"x")
    with pytest.raises(ValueError, match="SHA256 divergente.*registrado .*atual"):
        load_folds(tmp_path)


def test_load_folds_returns_original_table_and_rejects_random(tmp_path: Path) -> None:
    """Entrega a tabela íntegra aos consumidores e recusa esquema proposto."""
    table = make_inputs(tmp_path)
    write_folds(build_partition(PartitionConfig(5, (0,), tmp_path)), tmp_path)
    result = load_folds(tmp_path)
    pd.testing.assert_frame_equal(result.table, table)
    assert result.meta["seeds"] == [0]
    with pytest.raises(ValueError, match="esquema não suportado: random"):
        load_folds(tmp_path, "random")


@pytest.mark.parametrize(
    "change,message",
    [
        (lambda meta: meta.update(scheme="random"), "esquema registrado"),
        (lambda meta: meta.pop("folds_sha256"), "metadado sem folds_sha256"),
    ],
)
def test_load_folds_rejects_metadata_of_other_scheme_or_incomplete(
    tmp_path: Path, change: Any, message: str
) -> None:
    """Recusa metadado de outro esquema ou sem hash, mesmo com arquivos íntegros."""
    make_inputs(tmp_path)
    paths = write_folds(build_partition(PartitionConfig(5, (0,), tmp_path)), tmp_path)
    meta = json.loads(paths["meta"].read_text())
    change(meta)
    paths["meta"].write_text(json.dumps(meta))
    with pytest.raises(ValueError, match=message):
        load_folds(tmp_path)


def test_config_accepts_single_seed_override_and_rejects_multiple(
    tmp_path: Path,
) -> None:
    """Converte override YAML e recusa várias sementes, folds ≠ 5 e YAML ilegível."""
    config = tmp_path / "config.yaml"
    config.write_text(
        yaml.safe_dump(
            {
                "output_dir": str(tmp_path),
                "partition": {"n_splits": 5, "seeds": [0, 1]},
            }
        )
    )
    with pytest.raises(ValueError, match="partition.seeds"):
        load_partition_config(config, {}, None)
    assert load_partition_config(config, {"partition.seeds": "[3]"}, None).seeds == (3,)
    for override in ({"partition.n_splits": "2"}, {"partition.seeds": "[3"}):
        with pytest.raises(ValueError, match="Configuração inválida"):
            load_partition_config(config, {"partition.seeds": "[0]", **override}, None)


def test_training_inputs_reconcile_ids_and_validate_alias_identity(
    tmp_path: Path,
) -> None:
    """Rejeita ID sem alias, alias externo e identidade vazia com seu caminho."""
    make_inputs(tmp_path, count=2)
    provenance_path = tmp_path / c.PROVENANCE_FILENAME
    meta_path = tmp_path / c.META_FILENAME
    original = [json.loads(line) for line in provenance_path.read_text().splitlines()]
    cases = [
        ([original[0]], "id-001"),
        (
            original
            + [
                {
                    "firmware_id": "outside",
                    "in_table": True,
                    "aliases": [
                        {"meta_path": "outside.bin", "vendor": "asus", "model": "m5"}
                    ],
                }
            ],
            "outside",
        ),
        (
            [{**original[0], "aliases": [{**original[0]["aliases"][0], "model": " "}]}]
            + original[1:],
            "asus/m0/file.bin",
        ),
    ]
    for rows, expected in cases:
        provenance_path.write_text(
            "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
        )
        meta = json.loads(meta_path.read_text())
        meta["outputs"]["provenance"]["sha256"] = file_sha256(provenance_path)
        meta_path.write_text(json.dumps(meta), encoding="utf-8")
        with pytest.raises(ValueError, match=expected):
            load_training_inputs(tmp_path)


def test_crossing_guard_requires_every_id_in_one_test_fold() -> None:
    """Recusa ID da proveniência sem qualquer atribuição ao teste."""
    aliases = _aliases(("a", "asus", "a"), ("b", "asus", "b"))
    folds = pd.DataFrame(
        [
            {"repeat": 0, "fold": 0, "firmware_id": "a", "role": "test"},
            {"repeat": 0, "fold": 0, "firmware_id": "b", "role": "train"},
        ]
    )
    with pytest.raises(ValueError, match="id sem teste único"):
        check_no_crossing(folds, aliases)
