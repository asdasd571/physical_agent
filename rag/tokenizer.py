"""Kiwi-based sparse tokenizer with technical English token preservation."""

from __future__ import annotations

import re
import unicodedata


_DASHES = str.maketrans({"‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-", "−": "-"})
_TECHNICAL_TOKEN = re.compile(
    r"(?<![A-Za-z0-9])(?:"
    r"[A-Za-z]+(?:[A-Za-z0-9]*)(?:-[A-Za-z0-9]+)*"
    r"|\d+(?:\.\d+)?%?(?:-[A-Za-z0-9]+)*"
    r")(?![A-Za-z0-9])"
)
_CONTENT_POS_PREFIXES = ("N", "V", "MA", "MM", "XR", "SL", "SN")
_EXCLUDED_POS = {"VCP", "VCN"}


def normalize_search_text(text: str) -> str:
    """Normalize display variants without removing meaningful hyphens."""

    normalized = unicodedata.normalize("NFKC", text).translate(_DASHES).lower()
    return re.sub(r"\s+", " ", normalized).strip()


class KiwiTechnicalTokenizer:
    """Tokenize Korean with Kiwi and preserve English/numeric technical IDs."""

    def __init__(self) -> None:
        self._kiwi = None

    def _load(self):
        if self._kiwi is None:
            try:
                from kiwipiepy import Kiwi
            except ImportError as exc:
                raise RuntimeError(
                    "kiwipiepy is required for BM25; install requirements.txt"
                ) from exc
            self._kiwi = Kiwi()
        return self._kiwi

    def _tokenize_korean_segment(self, text: str) -> list[str]:
        if not text.strip():
            return []
        return [
            token.form.lower()
            for token in self._load().tokenize(text)
            if token.tag.startswith(_CONTENT_POS_PREFIXES) and token.tag not in _EXCLUDED_POS
        ]

    def tokenize(self, text: str) -> list[str]:
        normalized = normalize_search_text(text)
        if not normalized:
            return []

        tokens: list[str] = []
        cursor = 0
        for match in _TECHNICAL_TOKEN.finditer(normalized):
            tokens.extend(self._tokenize_korean_segment(normalized[cursor : match.start()]))
            tokens.append(match.group(0))
            cursor = match.end()
        tokens.extend(self._tokenize_korean_segment(normalized[cursor:]))
        return tokens
