from __future__ import annotations

import re
from collections.abc import Iterable, Iterator

ASCII_MIN = 32
ASCII_MAX = 126

# Regex sobre bytes (executado em C via re) casando runs de ASCII imprimivel.
# Substitui o loop byte-a-byte em Python puro, que dominava o tempo de
# extracao em firmwares grandes (ver perfil em pipeline/feature_extraction.py).
_PRINTABLE_RUN_RE = re.compile(
    b"[" + bytes([ASCII_MIN]) + b"-" + bytes([ASCII_MAX]) + b"]+"
)


def extract_ascii_strings(
    data: bytes,
    min_len: int = 4,
    max_string_len: int = 1024,
) -> list[str]:
    """Extrai strings ASCII imprimiveis (32-126) de bytes.

    Ignora strings menores que min_len e trunca cada string em
    max_string_len. Retorna lista vazia para entrada vazia.
    """
    if not data:
        return []
    min_len = max(1, min_len)
    max_string_len = max(1, max_string_len)
    strings: list[str] = []
    for match in _PRINTABLE_RUN_RE.finditer(data):
        run = match.group()
        if len(run) >= min_len:
            strings.append(run[:max_string_len].decode("ascii"))
    return strings


def _finish_run(pending: bytearray, length: int, min_len: int) -> Iterator[str]:
    """Emite a sequência pendente quando atinge o mínimo e esvazia o buffer."""
    if length >= min_len:
        yield pending.decode("ascii")
    pending.clear()


def iter_ascii_strings(
    chunks: Iterable[bytes], min_len: int = 4, max_string_len: int = 1024
) -> Iterator[str]:
    """Preserva sequências ASCII entre blocos sem armazenar o arquivo.

    Entre blocos guarda só até ``max_string_len`` bytes da sequência pendente
    e o comprimento dela; o resultado é igual ao de ``extract_ascii_strings``
    sobre a concatenação dos blocos.
    """
    min_len = max(1, min_len)
    max_string_len = max(1, max_string_len)
    pending = bytearray()
    length = 0
    for chunk in chunks:
        matched = False
        for match in _PRINTABLE_RUN_RE.finditer(chunk):
            matched = True
            if match.start() > 0:
                yield from _finish_run(pending, length, min_len)
                length = 0
            run = match.group()
            length += len(run)
            pending.extend(run[: max(0, max_string_len - len(pending))])
            if match.end() < len(chunk):
                yield from _finish_run(pending, length, min_len)
                length = 0
        if chunk and not matched:
            yield from _finish_run(pending, length, min_len)
            length = 0
    yield from _finish_run(pending, length, min_len)


class DocumentBuilder:
    """Deduplica primeiras strings e limita documento sem limitar detectores.

    Só guarda as strings que entraram no documento, então a memória fica
    limitada por ``max_strings`` e ``max_doc_chars`` mesmo com milhões de
    strings únicas.
    """

    def __init__(self, max_strings: int, max_doc_chars: int) -> None:
        """Inicializa limites e o conjunto de strings incluídas."""
        self.max_strings = max_strings
        self.max_doc_chars = max_doc_chars
        self._seen: set[str] = set()
        self._parts: list[str] = []
        self._chars = 0
        self.truncated = False

    def add(self, value: str) -> None:
        """Acrescenta somente primeira ocorrência respeitando ambos os limites."""
        if value in self._seen:
            return
        separator = 1 if self._parts else 0
        available = self.max_doc_chars - self._chars - separator
        if len(self._parts) >= self.max_strings or available <= 0:
            self.truncated = True
            return
        self._seen.add(value)
        self._parts.append(value[:available])
        self._chars += separator + min(len(value), available)
        self.truncated |= len(value) > available

    def document(self) -> str:
        """Devolve as strings deduplicadas em ordem de primeira ocorrência."""
        return "\n".join(self._parts)


def limit_strings(strings: Iterable[str], max_strings: int) -> list[str]:
    """Limita a lista de strings a max_strings elementos.

    Retorna lista vazia se max_strings <= 0.
    """
    if max_strings <= 0:
        return []
    limited: list[str] = []
    for value in strings:
        limited.append(value)
        if len(limited) >= max_strings:
            break
    return limited


def strings_to_document(strings: Iterable[str], max_doc_chars: int) -> str:
    """Concatena strings com \n e trunca em max_doc_chars.

    Retorna string vazia se max_doc_chars <= 0.
    """
    if max_doc_chars <= 0:
        return ""
    doc = "\n".join(strings)
    return doc[:max_doc_chars]


def tokenize_document(doc: str) -> list[str]:
    """Divide documento por whitespace e remove tokens vazios."""
    return [token for token in doc.split() if token]
