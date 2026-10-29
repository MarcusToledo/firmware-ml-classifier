"""Exercita a preparação da tabela e seus artefatos auditáveis."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
import yaml

from src.dataset.contract import TARGET_CLASSES, is_forbidden_column
from src.dataset.training_table import (
    PreparedDataset,
    build_training_table,
    load_dataset_config,
    write_artifacts,
)
from src.run_metadata import file_sha256
from tests.dataset_fixtures import (
    ONE_HOT_LISTS,
    feature_row,
    write_config,
    write_inputs,
)


def _prepared(
    directory: Path,
    extras: list[dict[str, Any]] | None = None,
    levels: dict[str | None, str] | None = None,
    **inputs_options: Any,
) -> PreparedDataset:
    rows = [
        feature_row("a", "alpha/router/a.bin"),
        feature_row("b", "beta/router/b.bin"),
        feature_row("c", "gamma/router/c.bin"),
        *(extras or []),
    ]
    labels = dict(zip("abc", TARGET_CLASSES))
    labels.update(levels or {})
    paths = write_inputs(directory, rows, labels, **inputs_options)
    config = load_dataset_config(write_config(directory, *paths, directory / "out"), {})
    return build_training_table(config)


def test_aliases_conservam_valores_sem_vazar_identidade(tmp_path: Path) -> None:
    alias = feature_row("a", "other/router/alias.bin", doc2vec_0=0.5)
    rows = [feature_row("a", "alpha/router/a.bin", doc2vec_0=0.5), alias]
    rows += [
        feature_row("b", "beta/router/b.bin"),
        feature_row("c", "gamma/router/c.bin"),
    ]
    features, labels = write_inputs(tmp_path, rows, dict(zip("abc", TARGET_CLASSES)))
    config = load_dataset_config(
        write_config(tmp_path, features, labels, tmp_path / "out"), {}
    )
    prepared = build_training_table(config)
    table = prepared.table
    assert table["firmware_id"].tolist() == ["a", "b", "c"]
    assert table["security_level"].tolist() == list(TARGET_CLASSES)
    assert table.loc[0, "entropy"] == 7.0
    assert table.loc[0, "unpacked_n_files"] == 10.0
    assert not any(
        is_forbidden_column(col) for col in prepared.metadata["columns_vector"]
    )
    assert prepared.metadata["column_changes"]["doc2vec_0"] == "doc2vec_t06_proposto"
    assert prepared.metadata["column_changes"]["fs_type"] == "texto_one_hot"
    assert prepared.metadata["columns_input"].index("doc2vec_0") > 0
    assert "has_telnetd" in prepared.metadata["constant_columns"]
    assert "has_telnetd" in table
    assert [row["firmware_id"] for row in prepared.provenance] == ["a", "b", "c"]
    assert prepared.provenance[0]["aliases"] == [
        {"meta_path": "alpha/router/a.bin", "vendor": "alpha", "model": "router"},
        {"meta_path": "other/router/alias.bin", "vendor": "other", "model": "router"},
    ]
    assert prepared.metadata["counts"]["input_rows"] == 4


def test_detectores_excluidos_pela_t13a_saem_do_vetor(tmp_path: Path) -> None:
    extras = {
        "count_urls": 3,
        "count_api_tokens": 9,
        "count_public_ips": 2,
        "has_debug_account": True,
        "n_crypto_signatures": 1,
    }
    features, labels = write_inputs(
        tmp_path,
        [
            feature_row(fid, f"{vendor}/router/{fid}.bin", **extras)
            for fid, vendor in zip("abc", ("alpha", "beta", "gamma"))
        ],
        dict(zip("abc", TARGET_CLASSES)),
    )
    config = load_dataset_config(
        write_config(tmp_path, features, labels, tmp_path / "out"), {}
    )

    prepared = build_training_table(config)

    vector = prepared.metadata["columns_vector"]
    changes = prepared.metadata["column_changes"]
    assert "count_urls" in vector and "has_telnetd" in vector
    for column in ("count_api_tokens", "count_public_ips", "has_debug_account"):
        assert column not in prepared.table
        assert column not in vector
    assert changes["count_api_tokens"] == "t13a_retirar"
    assert changes["has_debug_account"] == "t13a_reformular"
    assert changes["n_crypto_signatures"] == "t13a_reformular"


@pytest.mark.parametrize(
    "field,value,fragment",
    [
        ("meta_binwalk_status", "erro", "falha_extracao"),
        ("meta_unpack_status", "falha", "falha_extracao"),
        ("meta_fs_status", "erro", "falha_extracao"),
        ("meta_third_party", "dd-wrt", "terceiros"),
    ],
)
def test_exclusao_por_alias_registra_motivo(
    tmp_path: Path, field: str, value: str, fragment: str
) -> None:
    extra = feature_row("a", "zeta/router/a.bin", fs_type="yaffs2", **{field: value})
    prepared = _prepared(
        tmp_path,
        [extra, feature_row("d", "delta/router/d.bin")],
        {"d": TARGET_CLASSES[0]},
    )
    assert prepared.table["firmware_id"].tolist() == ["b", "c", "d"]
    assert prepared.exclusions.loc[0, "reasons"] == fragment
    assert prepared.exclusions.loc[0, "vendors"] == "alpha;zeta"
    counts = prepared.metadata["counts"]
    assert counts["excluded_by_vendor"]["alpha"] == 1
    assert counts["excluded_by_vendor"]["zeta"] == 1
    assert counts["multi_vendor_firmware_ids"] == 1
    assert counts["table_rows"] + counts["excluded_firmware_ids"] == 4


def test_multiplos_motivos_e_indeterminado_por_fabricante(tmp_path: Path) -> None:
    prepared = _prepared(
        tmp_path,
        [
            feature_row(
                "d",
                "beta/router/d.bin",
                meta_unpack_status="falha",
                meta_third_party="dd-wrt",
            )
        ],
        {"d": "indeterminado"},
    )
    row = prepared.exclusions.iloc[0]
    assert row["firmware_id"] == "d"
    assert row["reasons"] == "falha_extracao;terceiros;indeterminado"
    counts = prepared.metadata["counts"]
    assert all(
        counts["excluded_by_reason"][reason] == 1
        for reason in row["reasons"].split(";")
    )
    assert counts["excluded_by_vendor_reason"]["beta"]["indeterminado"] == 1
    assert counts["indeterminate_by_vendor"]["beta"] == {
        "indeterminado": 1,
        "total": 2,
        "proporcao": 0.5,
    }
    assert set(prepared.table.firmware_id).isdisjoint(
        set(prepared.exclusions.firmware_id)
    )
    assert {entry["firmware_id"] for entry in prepared.provenance} == set("abcd")
    assert not prepared.provenance[-1]["in_table"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("meta_binwalk_status", "timeout"),
        ("meta_binwalk_status", "nao_executado"),
        ("meta_unpack_status", "limite_tempo"),
        ("meta_unpack_status", "nao_executado"),
    ],
)
def test_falha_transitoria_exige_reextracao(
    tmp_path: Path, field: str, value: str
) -> None:
    with pytest.raises(ValueError, match="extraia as features de novo") as exc:
        _prepared(
            tmp_path, [feature_row("a", "alpha/router/bad.bin", **{field: value})]
        )
    assert "alpha/router/bad.bin" in str(exc.value)
    assert f"{field}={value}" in str(exc.value)
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("value", ["desconhecido", None])
def test_estado_desconhecido_nao_exclui_silenciosamente(
    tmp_path: Path, value: str | None
) -> None:
    with pytest.raises(ValueError, match="estado desconhecido.*meta_fs_status"):
        _prepared(
            tmp_path, [feature_row("a", "alpha/router/bad.bin", meta_fs_status=value)]
        )


@pytest.mark.parametrize(
    "value", ["criptografado", "sem_filesystem", "limite_tamanho", "limite_arquivos"]
)
def test_limites_do_dado_ficam_na_tabela(tmp_path: Path, value: str) -> None:
    prepared = _prepared(
        tmp_path,
        [feature_row("d", "delta/router/d.bin", meta_unpack_status=value)],
        {"d": TARGET_CLASSES[0]},
    )
    assert "d" in set(prepared.table.firmware_id)
    assert prepared.exclusions.empty


def test_one_hot_fixa_fora_da_lista_ausente_e_valores_originais(tmp_path: Path) -> None:
    rows = [
        feature_row("a", "alpha/router/a", fs_type="yaffs2", entropy=3.25),
        feature_row("b", "beta/router/b", fs_type=None, compression_type=None),
        feature_row("c", "gamma/router/c", fs_type="", compression_type="gzip"),
    ]
    features, labels = write_inputs(tmp_path, rows, dict(zip("abc", TARGET_CLASSES)))
    config = load_dataset_config(
        write_config(tmp_path, features, labels, tmp_path / "out"), {}
    )
    table = build_training_table(config).table.set_index("firmware_id")
    assert table.loc["a", "entropy"] == 3.25
    assert table.loc["a", "fs_type__outro"] == 1
    assert table.loc["b", "fs_type__ausente"] == 1
    assert table.loc["b", "compression_type__ausente"] == 1
    assert table.loc["c", "fs_type__outro"] == 1
    assert table.loc["c", "compression_type__gzip"] == 1
    for source, categories in ONE_HOT_LISTS.items():
        columns = [f"{source}__{name}" for name in [*categories, "outro", "ausente"]]
        assert table[columns].sum(axis=1).tolist() == [1, 1, 1]
        assert all(table[col].dtype == "int8" for col in columns)
    assert table.columns[table.columns.get_loc("entropy") + 1] == "byte_mean"
    assert "fs_type" not in table and "compression_type" not in table


def test_alias_divergente_e_rotulo_divergente_falham(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="a: n_filesystems"):
        _prepared(
            tmp_path / "features",
            [feature_row("a", "alpha/router/other", n_filesystems=2)],
        )
    with pytest.raises(ValueError, match="security_level divergente.*a"):
        _prepared(
            tmp_path / "labels",
            [feature_row("a", "alpha/router/other")],
            level_by_path={"alpha/router/other": TARGET_CLASSES[1]},
        )


def test_id_nulo_sem_par_e_hash_invalido_falham(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="extraia as features de novo") as exc:
        _prepared(
            tmp_path / "null",
            [feature_row(None, "alpha/router/null")],
            {None: TARGET_CLASSES[0]},
        )
    assert "alpha/router/null" in str(exc.value)
    with pytest.raises(ValueError, match="registrado errado, atual"):
        _prepared(tmp_path / "hash", features_sha256="errado")
    rows = [
        feature_row("a", "alpha/router/a"),
        feature_row("b", "beta/router/b"),
        feature_row("c", "gamma/router/c"),
    ]
    features, labels = write_inputs(
        tmp_path / "pair", rows, dict(zip("abc", TARGET_CLASSES))
    )
    data = pd.read_csv(labels)
    data.loc[2, "firmware_id"] = "d"
    data.to_csv(labels, index=False)
    config = load_dataset_config(
        write_config(tmp_path / "pair", features, labels, tmp_path / "pair/out"), {}
    )
    with pytest.raises(ValueError, match="sem par.*c.*d"):
        build_training_table(config)


@pytest.mark.parametrize(
    "field",
    ["meta_binwalk_status", "meta_unpack_status", "meta_third_party", "meta_fs_status"],
)
def test_coluna_obrigatoria_ausente_rejeitada(tmp_path: Path, field: str) -> None:
    rows = [feature_row(id_, f"brand/router/{id_}") for id_ in "abc"]
    for row in rows:
        del row[field]
    features, labels = write_inputs(tmp_path, rows, dict(zip("abc", TARGET_CLASSES)))
    config = load_dataset_config(
        write_config(tmp_path, features, labels, tmp_path / "out"), {}
    )
    with pytest.raises(ValueError, match=field):
        build_training_table(config)


@pytest.mark.parametrize(
    "missing", ["features_v2.parquet", "labels_v2.csv", "labels_v2.meta.json"]
)
def test_entrada_ausente_cita_o_caminho(tmp_path: Path, missing: str) -> None:
    rows = [feature_row(id_, f"brand/router/{id_}") for id_ in "abc"]
    features, labels = write_inputs(tmp_path, rows, dict(zip("abc", TARGET_CLASSES)))
    config = load_dataset_config(
        write_config(tmp_path, features, labels, tmp_path / "out"), {}
    )
    (tmp_path / missing).unlink()
    with pytest.raises(FileNotFoundError, match=missing):
        build_training_table(config)
    assert not (tmp_path / "out").exists()


def test_config_ausente_falha(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="dataset.yaml"):
        load_dataset_config(tmp_path / "dataset.yaml", {})


@pytest.mark.parametrize("field", ["cve_total", "cve_count_critical", "vendor"])
def test_vazamento_na_tabela_de_features_e_erro(tmp_path: Path, field: str) -> None:
    with pytest.raises(ValueError, match=field):
        _prepared(tmp_path, [feature_row("a", "alpha/router/alias", **{field: 9})])


def test_texto_nao_codificado_nao_entra_no_vetor(tmp_path: Path) -> None:
    rows = [feature_row(id_, f"brand/router/{id_}", note="texto") for id_ in "abc"]
    features, labels = write_inputs(tmp_path, rows, dict(zip("abc", TARGET_CLASSES)))
    config = load_dataset_config(
        write_config(tmp_path, features, labels, tmp_path / "out"), {}
    )
    with pytest.raises(ValueError, match="coluna de texto no vetor.*note"):
        build_training_table(config)


@pytest.mark.parametrize("level", ["indeterminado", TARGET_CLASSES[0]])
def test_tabela_vazia_ou_classe_ausente_falha(tmp_path: Path, level: str) -> None:
    with pytest.raises(ValueError, match="classe sem exemplo"):
        _prepared(tmp_path, levels={"b": level, "c": level})


def test_todas_as_linhas_excluidas_nao_produzem_artefato(tmp_path: Path) -> None:
    extras = [
        feature_row(id_, f"brand/router/{id_}-third", meta_third_party="dd-wrt")
        for id_ in "abc"
    ]
    with pytest.raises(ValueError, match="Tabela vazia.*0"):
        _prepared(tmp_path, extras)
    assert not (tmp_path / "out").exists()


def test_rotulo_invalido_identifica_firmware(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="security_level inválido.*b"):
        _prepared(tmp_path, levels={"b": "inesperado"})


@pytest.mark.parametrize("invalid", [["outro"], ["lzma", "lzma"], [""], "lzma"])
def test_config_one_hot_invalida(tmp_path: Path, invalid: object) -> None:
    config_path = write_config(
        tmp_path, Path("features.parquet"), Path("labels.csv"), tmp_path
    )
    data = yaml.safe_load(config_path.read_text())
    data["one_hot"]["compression_type"] = invalid
    config_path.write_text(yaml.safe_dump(data))
    with pytest.raises(ValueError, match="one_hot.compression_type"):
        load_dataset_config(config_path, {})
    data["one_hot"]["compression_type"] = ONE_HOT_LISTS["compression_type"]
    config_path.write_text(yaml.safe_dump(data))
    with pytest.raises(ValueError, match="one_hot.fs_type"):
        load_dataset_config(config_path, {"one_hot.fs_type": "squashfs"})


def test_artefatos_estaveis_e_metadados_com_hashes(tmp_path: Path) -> None:
    prepared = _prepared(tmp_path / "input")
    first = write_artifacts(prepared, tmp_path / "run1")
    second = write_artifacts(prepared, tmp_path / "run2")
    for name in ("table", "exclusions", "provenance"):
        assert first[name].read_bytes() == second[name].read_bytes()
    meta = json.loads(first["meta"].read_text())
    assert list(prepared.metadata) == [
        "inputs",
        "commit",
        "config",
        "columns_input",
        "columns_vector",
        "column_changes",
        "constant_columns",
        "counts",
    ]
    for name in ("table", "exclusions", "provenance"):
        assert meta["outputs"][name]["sha256"] == file_sha256(first[name])
    assert pd.read_parquet(first["table"]).equals(prepared.table)
