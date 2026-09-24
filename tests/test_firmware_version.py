from __future__ import annotations

import pytest

from pipeline.firmware_version import infer_version_from_filename


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("WNDR4300-V1.0.1.30.img", "1.0.1.30"),
        # O segundo numero e pacote de idioma, a versao do firmware e o primeiro.
        ("R6250-V1.0.1.80_1.0.75.chk", "1.0.1.80"),
        ("R6350-V1.1.1.88_1.0.1.img", "1.1.1.88"),
        ("R6220_V1.1.0.50_1.0.1.img", "1.1.0.50"),
        ("R6800-1.2.0.24_1.0.1.img", "1.2.0.24"),
        ("wgt634u_1_4_1_13.img", "1.4.1.13"),
        ("wnr854t_1_4_31_ww.img", "1.4.31"),
        # v1014 nao diz onde ficam os pontos: sem chute.
        ("R6220_v1014_101.img", None),
    ],
)
def test_netgear(filename: str, expected: str | None) -> None:
    assert infer_version_from_filename("netgear", filename) == expected


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        # A versao completa inclui os grupos de build, nao so 3.0.0.4.
        ("RT-AC66U_B1_3.0.0.4_384_32738-gc9a116a.trx", "3.0.0.4.384.32738"),
        ("RT-AC68W_3.0.0.4_386_43137-gc42c548_combo.trx", "3.0.0.4.386.43137"),
        ("DSL-N16_1.1.2.3_502-g2bdb05b.trx", "1.1.2.3.502"),
        ("RT-N12E_2.0.0.39.trx", "2.0.0.39"),
        ("RT-N10+_2.1.1.1.92.trx", "2.1.1.1.92"),
        # O ".A" final e letra de regiao, nao faz parte da versao.
        ("WL-AM604g_2.0.3.4.A.trx", "2.0.3.4"),
        ("FW_RT_N10_1017.trx", None),
        ("ASUS_6338_COMBO_306064V00_cfe_fs_kernel", None),
    ],
)
def test_asus(filename: str, expected: str | None) -> None:
    assert infer_version_from_filename("asus", filename) == expected


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("f5d7230-4v7_us_9.01.07.bin", "9.01.07"),
        ("awgr54-firmware-v9.01.10.bin", "9.01.10"),
        ("F9K1106_WW_1.00.16.bin", "1.00.16"),
        ("f5d7231-4%20us%20v5.01.11.bin", "5.01.11"),
        ("20061222_belkin_f5d9230us4_4.01.09(mr).bin", "4.01.09"),
        ("f5d7230-4_ww_a.00.11.bin", None),
        ("v2.4-S3%20Legacy.img", None),
    ],
)
def test_belkin(filename: str, expected: str | None) -> None:
    assert infer_version_from_filename("belkin", filename) == expected


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("DSR-150_A1_A2_A3_FW2.11_WW", "2.11"),
        ("DSR-250N_REVA2_FW_2.11_WW", "2.11"),
        ("DSL-2760U-BN_1.12_11262013_cfe_fs_kernel", "1.12"),
        # A mesma versao repetida conta como um candidato so.
        ("FW1.14_V1.14.bin", "1.14"),
        # Sufixo de build (B01, B58) muda a versao: nao truncar.
        ("DIR-300_REVB5_FIRMWARE_2.15.B01_WW.BIN", None),
        ("DSR-500_FW1.04B58.04B58_WW", None),
        # 100 significaria 1.00, mas isso seria chute.
        ("DIR_1760_FW101B04.BIN", None),
        # Data e hora aparecem junto da versao: candidatos demais.
        ("2019.10.14-15.55_DIR_825AC_G1A_ISR_1.0.4_release.bin", None),
    ],
)
def test_dlink(filename: str, expected: str | None) -> None:
    assert infer_version_from_filename("dlink", filename) == expected


@pytest.mark.parametrize("brand", ["tp_link", "tplink"])
@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("ArcherC7v1_en_3_13_35_up_boot(140704).bin", "3.13.35"),
        ("er604wv1_en_1_0_0_up(130116).bin", "1.0.0"),
        ("TD-W8950Nv1_un_1_0_2_140106R38442.bin", "1.0.2"),
        ("TL-SG5412Fv1_en_1.0.4_[20140430-rel40858]_up.bin", "1.0.4"),
        # Dois numeros de versao possiveis (0.9.1 e 0.1): ambiguo.
        ("Archer_D9v1_0.9.1_0.1_up_boot(150826)_2015-08-26_11.47.46.bin", None),
        ("tl-wr710v1-webflash.bin", None),
        ("ras", None),
    ],
)
def test_tplink(brand: str, filename: str, expected: str | None) -> None:
    assert infer_version_from_filename(brand, filename) == expected


def test_unknown_brand_returns_none() -> None:
    assert infer_version_from_filename("zyxel", "NWA110AX_7.10.bin") is None


def test_extension_is_case_insensitive() -> None:
    assert infer_version_from_filename("netgear", "WNDR4300-V1.0.1.30.IMG") == (
        "1.0.1.30"
    )
