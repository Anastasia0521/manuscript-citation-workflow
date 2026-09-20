from daocha.manuscript import extract_source_paragraph, normalize_sentence


def test_english_sentence_keeps_spaces() -> None:
    text = "Remote sensing can monitor vegetation cover【1】. The next sentence."
    para = extract_source_paragraph(text, "【1】")
    assert "Remote sensing can monitor" in para
    assert "The next sentence" not in para
    assert " " in para


def test_chinese_sentence_without_latin_drops_spaces() -> None:
    text = "遥感可以监测植被覆盖【1】。下一句。"
    para = extract_source_paragraph(text, "【1】")
    assert "【1】" in para
    assert " " not in para


def test_mixed_sentence_keeps_english_spaces() -> None:
    text = "遥感监测 vegetation cover 的变化【1】。下一句。"
    para = extract_source_paragraph(text, "【1】")
    assert "vegetation cover" in para


def test_normalize_english() -> None:
    assert normalize_sentence("  Hello   world \n") == "Hello world"
