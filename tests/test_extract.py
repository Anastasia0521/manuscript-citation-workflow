from pathlib import Path

import pytest

from daocha.doi_budget import assert_registry_valid
from daocha.export import run_export
from daocha.extract import MarkerExtractError, analyze_markers, build_registry, extract_markers
from daocha.manuscript import backfill_source_paragraphs
from daocha.storage import create_project


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


def test_create_project_does_not_require_user_numbers(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("daocha.storage.projects_root", lambda: tmp_path / "projects")
    source = tmp_path / "manuscript.txt"
    source.write_text(
        "补偿政策改变了牧户决策【】。遥感可以监测植被覆盖【】。",
        encoding="utf-8",
    )
    registry = create_project(
        title="empty-slots",
        manuscript=source,
        target_journal="通用英文作者—年份",
    )
    citations = registry["citations"]
    assert [item["id"] for item in citations] == ["C001", "C002"]
    assert [item["marker"] for item in citations] == ["【1】", "【2】"]
    assert "补偿政策" in citations[0]["sourceParagraph"]
    assert "【1】" in citations[0]["sourceParagraph"]
    assert "遥感" in citations[1]["sourceParagraph"]
    copied = tmp_path / "projects" / registry["meta"]["projectId"] / "manuscript.txt"
    original = copied.read_text(encoding="utf-8")
    assert "【】" in original
    assert "【1】" not in original

    for index, item in enumerate(citations, start=1):
        item["userDecision"] = "keep"
        item["status"] = "locked"
        item["doi"] = f"10.1000/empty-{index}"
        item["year"] = 2020 + index
        item["title"] = f"English journal article {index}"
        item["journal"] = "Journal of Environmental Management"
        item["recommended"] = f"Smith, {2020 + index}"
        item["authorsFormatted"] = "Smith, A."
        item["url"] = f"https://doi.org/{item['doi']}"

    assert_registry_valid(registry, require_locked=True)
    phase3, _phase4 = run_export(registry, manuscript_path=copied, require_locked=True)
    assert "(Smith, 2021)" in phase3
    assert "(Smith, 2022)" in phase3
