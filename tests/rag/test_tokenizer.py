from __future__ import annotations

from rag.tokenizer import KiwiTechnicalTokenizer, normalize_search_text


def test_normalize_search_text_unifies_case_width_and_hyphen() -> None:
    assert normalize_search_text("ＢＧＥ－M3  ROBOT—HAND") == "bge-m3 robot-hand"


def test_kiwi_tokenizer_preserves_technical_english_and_numbers() -> None:
    tokenizer = KiwiTechnicalTokenizer()
    tokens = tokenizer.tokenize(
        "VLA 기반 vision-language-action 로봇핸드의 3-finger 성공률은 12.8%이다."
    )

    assert "vla" in tokens
    assert "vision-language-action" in tokens
    assert "3-finger" in tokens
    assert "12.8%" in tokens
    assert any(token.startswith("로봇") or token == "로봇핸드" for token in tokens)


def test_empty_text_returns_no_tokens() -> None:
    assert KiwiTechnicalTokenizer().tokenize("   ") == []
