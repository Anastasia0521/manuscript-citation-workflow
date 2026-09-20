from pathlib import Path

import pytest

from daocha.extract import MarkerExtractError, analyze_markers, extract_markers


def test_extract_markers_from_text(tmp_path: Path) -> None:
    source = tmp_path / "manuscript.txt"
    source.write_text(
        "Grassland compensation changes herder decisions【1】. Remote sensing monitors vegetation【2】.",
        encoding="utf-8",
    )
    markers = extract_markers(source)
    assert [item["marker"] for item in markers] == ["【1】", "【2】"]


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


def test_empty_marker_fails() -> None:
    report = analyze_markers("Broken PDF placeholder【】 here.")
    assert any(issue["type"] == "empty" for issue in report["issues"])
