from pathlib import Path

import pytest

from daocha.extract import MarkerExtractError, analyze_markers, extract_markers
from daocha.manuscript import backfill_source_paragraphs
from daocha.extract import build_registry


def test_extract_markers_from_text(tmp_path: Path) -> None:
    source = tmp_path / "manuscript.txt"
    source.write_text(
        "Grassland compensation changes herder decisions【1】. Remote sensing monitors vegetation【2】.",
        encoding="utf-8",
    )
    markers = extract_markers(source)
    assert [item["marker"] for item in markers] == ["【1】", "【2】"]


def test_empty_brackets_are_numbered_in_order(tmp_path: Path) -> None:
    source = tmp_path / "manuscript.txt"
    source.write_text(
        "第一处主张【】。第二处主张【】。第三处【 】。",
        encoding="utf-8",
    )
    markers = extract_markers(source)
    assert [item["marker"] for item in markers] == ["【1】", "【2】", "【3】"]


def test_spaced_and_fullwidth_digits_normalized(tmp_path: Path) -> None:
    source = tmp_path / "manuscript.txt"
    source.write_text("Claim one【 1 】. Claim two【２】.", encoding="utf-8")
    markers = extract_markers(source)
    assert [item["marker"] for item in markers] == ["【1】", "【2】"]


def test_duplicate_marker_fails(tmp_path: Path) -> None:
    source = tmp_path / "manuscript.txt"
    source.write_text("First【1】. Later again【1】.", encoding="utf-8")
    with pytest.raises(MarkerExtractError) as exc:
        extract_markers(source)
    assert "同一个号" in str(exc.value)


def test_range_marker_fails(tmp_path: Path) -> None:
    source = tmp_path / "manuscript.txt"
    source.write_text("Bundle【1-3】.", encoding="utf-8")
    with pytest.raises(MarkerExtractError):
        extract_markers(source)


def test_mixed_empty_and_numbered_fails() -> None:
    report = analyze_markers("Empty【】 and numbered【1】 together.")
    assert any(issue["type"] == "mixed" for issue in report["issues"])


def test_backfill_numbers_empty_slots(tmp_path: Path) -> None:
    source = tmp_path / "manuscript.txt"
    source.write_text("第一句主张【】。第二句主张【】。", encoding="utf-8")
    markers = extract_markers(source)
    registry = build_registry(
        markers,
        project_id="demo",
        manuscript_name="manuscript.txt",
        title="demo",
    )
    backfill_source_paragraphs(registry, source)
    first, second = registry["citations"]
    assert "【1】" in first["sourceParagraph"]
    assert "第一句" in first["sourceParagraph"]
    assert "【2】" in second["sourceParagraph"]
    assert "第二句" in second["sourceParagraph"]
