import numpy as np
import pytest

from src.features.doc2vec import (
    Doc2VecConfig,
    build_corpus,
    infer_embedding,
    load_doc2vec,
    save_doc2vec,
    train_doc2vec,
)


@pytest.fixture()
def cfg_ok() -> Doc2VecConfig:
    return Doc2VecConfig(
        vector_size=20,
        window=3,
        epochs=5,
        min_count=1,
        seed=42,
        workers=1,
        dm=1,
        alpha=0.025,
        min_alpha=0.0001,
    )


@pytest.fixture()
def docs_realistic() -> list[tuple[str, list[str]]]:
    return [
        (
            "sha256:3f2a1c9b8e7d4a11c0f2d9a6b1c3e5f7",
            [
                "/bin/busybox",
                "/etc/init.d/rcS",
                "/etc/passwd",
                "/etc/shadow",
                "init",
                "mount",
                "mdev",
                "udhcpc",
                "ifconfig",
                "iptables",
                "dropbear",
                "telnetd",
                "nvram",
                "squashfs",
                "mips",
                "uclibc",
            ],
        ),
        (
            "sha256:a9d18b2c4e6f7890d1c2b3a4f5e6d7c8",
            [
                "/www/index.asp",
                "/www/login.asp",
                "httpd",
                "cgi-bin",
                "boa",
                "upnp",
                "dnsmasq",
                "hostapd",
                "wpa_supplicant",
                "pppoe",
                "TR-069",
                "soap",
                "firmware_upgrade",
                "admin",
                "root",
            ],
        ),
    ]


def test_build_corpus_preserves_doc_ids_and_tokens(
    docs_realistic: list[tuple[str, list[str]]],
) -> None:
    corpus = build_corpus(docs_realistic)

    assert len(corpus) == 2
    assert corpus[0].tags == [docs_realistic[0][0]]
    assert corpus[0].words == docs_realistic[0][1]
    assert corpus[1].tags == [docs_realistic[1][0]]
    assert corpus[1].words == docs_realistic[1][1]


def test_train_doc2vec_enforces_workers_one(cfg_ok: Doc2VecConfig) -> None:
    corpus = build_corpus([("sha256:one", ["busybox"])])
    config = Doc2VecConfig(**{**cfg_ok.__dict__, "workers": 2})

    with pytest.raises(ValueError, match="workers"):
        train_doc2vec(corpus, config)


def test_train_doc2vec_model_has_expected_vector_size_and_docvecs(
    cfg_ok: Doc2VecConfig,
    docs_realistic: list[tuple[str, list[str]]],
) -> None:
    corpus = build_corpus(docs_realistic)
    model = train_doc2vec(corpus, cfg_ok)

    assert model.vector_size == cfg_ok.vector_size
    assert len(model.dv) == 2
    assert model.dv[docs_realistic[0][0]].shape == (cfg_ok.vector_size,)


def test_infer_embedding_empty_tokens_returns_zero_finite_vector(
    cfg_ok: Doc2VecConfig,
) -> None:
    model = train_doc2vec(build_corpus([("sha256:one", ["busybox"])]), cfg_ok)

    vec = infer_embedding(model, [], cfg_ok)

    assert vec.shape == (cfg_ok.vector_size,)
    assert np.allclose(vec, 0.0)
    assert np.isfinite(vec).all()
    assert np.issubdtype(vec.dtype, np.floating)


def test_infer_embedding_deterministic_same_seed_changes_with_different_seed(
    cfg_ok: Doc2VecConfig,
    docs_realistic: list[tuple[str, list[str]]],
) -> None:
    corpus = build_corpus(docs_realistic)
    model = train_doc2vec(corpus, cfg_ok)

    vec1 = infer_embedding(model, docs_realistic[0][1], cfg_ok)
    vec2 = infer_embedding(model, docs_realistic[0][1], cfg_ok)
    assert np.allclose(vec1, vec2, atol=1e-4)

    cfg_diff = Doc2VecConfig(**{**cfg_ok.__dict__, "seed": 43})
    vec3 = infer_embedding(model, docs_realistic[0][1], cfg_diff)

    assert np.linalg.norm(vec1 - vec3) > 1e-6
    assert np.isfinite(vec3).all()


def test_save_load_roundtrip_preserves_config_and_infer_behavior(
    tmp_path: pytest.TempPathFactory,
    cfg_ok: Doc2VecConfig,
    docs_realistic: list[tuple[str, list[str]]],
) -> None:
    corpus = build_corpus(docs_realistic)
    model = train_doc2vec(corpus, cfg_ok)
    model_path = tmp_path / "doc2vec.model"

    save_doc2vec(model, str(model_path))
    loaded = load_doc2vec(str(model_path))

    assert loaded.vector_size == cfg_ok.vector_size
    assert loaded.dm == cfg_ok.dm

    vec1 = infer_embedding(loaded, docs_realistic[0][1], cfg_ok)
    vec2 = infer_embedding(loaded, docs_realistic[0][1], cfg_ok)

    assert np.allclose(vec1, vec2, atol=1e-4)
    assert vec1.shape == (cfg_ok.vector_size,)
    assert np.isfinite(vec1).all()


def test_infer_embedding_oov_tokens_finite(cfg_ok: Doc2VecConfig) -> None:
    corpus = build_corpus([("sha256:one", ["busybox"])])
    model = train_doc2vec(corpus, cfg_ok)
    tokens = [
        "/usr/sbin/nonexistent_daemon",
        "CVE-2021-XXXXX",
        "unknown_vendor_marker",
    ]

    vec = infer_embedding(model, tokens, cfg_ok)

    assert vec.shape == (cfg_ok.vector_size,)
    assert np.isfinite(vec).all()
