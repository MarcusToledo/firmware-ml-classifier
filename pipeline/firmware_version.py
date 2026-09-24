"""Inferencia da versao do firmware a partir do nome do arquivo.

Cada fabricante nomeia o arquivo de um jeito, entao cada um tem a sua regra.
A saida e sempre uma string numerica com pontos (ex.: "3.0.0.4.384.45717"),
que e o formato que o rotulador de CVE consegue comparar com os intervalos das
CPEs. Quando o nome nao traz uma versao inequivoca, o retorno e None e o
firmware fica indeterminado, porque uma versao errada geraria um rotulo
falsamente determinado.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from urllib.parse import unquote

_EXTENSION_RE = re.compile(r"\.(bin|img|trx|chk|zip|rom)$", re.IGNORECASE)

_NETGEAR_V_RE = re.compile(r"[-_][Vv](\d+(?:\.\d+){2,3})(?=[_.\-]|$)")
_NETGEAR_DASH_RE = re.compile(r"-(\d+(?:\.\d+){3})(?=_|$)")
_NETGEAR_UNDERSCORE_RE = re.compile(r"_(\d+(?:_\d+){2,3})(?=_|$)")

# A versao completa inclui os grupos de build: 3.0.0.4_384_45717 e
# 3.0.0.4.384.45717. Truncar em 3.0.0.4 decidiria intervalos com versao
# incompleta.
_ASUS_RE = re.compile(
    r"_(\d+(?:\.\d+){2,5})((?:_\d{2,6}){0,2})(?:-g[0-9a-f]+)?(?:_combo)?"
    r"(?:\.[A-Z])?$"
)

_BELKIN_RE = re.compile(r"[_\-\s][vV]?(\d+\.\d+\.\d+)(?=$|[_.\-\s(])")

# Candidato numerico que nao e seguido de letra: "2.15.B01" e "1.04B58" trazem
# sufixo de build, que muda a versao, entao nao podem ser truncados.
_DLINK_CANDIDATE_RE = re.compile(
    r"(?<![\d.])(\d+(?:\.\d+){1,5})(?![\d])(?!\.?[A-Za-z])"
)
_DATE_RE = re.compile(r"\d{4}\.\d{1,2}\.\d{1,2}")

_TPLINK_UNDERSCORE_RE = re.compile(r"_(\d+(?:_\d+){2})(?=_up|_\d{6}R\d+)")
_TPLINK_DOTTED_RE = re.compile(r"_(\d+\.\d+\.\d+)_\[\d{8}-rel\d+\]")


def _netgear(stem: str) -> str | None:
    """Ex.: R6250-V1.0.1.80_1.0.75 vira 1.0.1.80 (o segundo numero e pacote)."""
    for pattern in (_NETGEAR_V_RE, _NETGEAR_DASH_RE):
        match = pattern.search(stem)
        if match:
            return match.group(1)
    match = _NETGEAR_UNDERSCORE_RE.search(stem)
    return match.group(1).replace("_", ".") if match else None


def _asus(stem: str) -> str | None:
    match = _ASUS_RE.search(stem)
    if match is None:
        return None
    return match.group(1) + match.group(2).replace("_", ".")


def _belkin(stem: str) -> str | None:
    match = _BELKIN_RE.search(stem)
    return match.group(1) if match else None


def _dlink(stem: str) -> str | None:
    """So aceita quando ha exatamente um candidato, depois de excluir datas."""
    candidates = {
        candidate
        for candidate in _DLINK_CANDIDATE_RE.findall(stem)
        if not _DATE_RE.fullmatch(candidate)
    }
    return candidates.pop() if len(candidates) == 1 else None


def _tplink(stem: str) -> str | None:
    """Nomes com dois numeros de versao possiveis (0.9.1_0.1) ficam sem versao."""
    match = _TPLINK_UNDERSCORE_RE.search(stem)
    if match:
        return match.group(1).replace("_", ".")
    match = _TPLINK_DOTTED_RE.search(stem)
    return match.group(1) if match else None


_RULES: dict[str, Callable[[str], str | None]] = {
    "netgear": _netgear,
    "asus": _asus,
    "belkin": _belkin,
    "dlink": _dlink,
    "tp_link": _tplink,
    "tplink": _tplink,
}


def infer_version_from_filename(brand: str, filename: str) -> str | None:
    """Extrai a versao do firmware do nome do arquivo, ou None se ambigua.

    Fabricante sem regra retorna None: nao ha um formato generico confiavel.
    """
    rule = _RULES.get(brand.strip().lower())
    if rule is None:
        return None
    stem = _EXTENSION_RE.sub("", unquote(filename))
    return rule(stem)
