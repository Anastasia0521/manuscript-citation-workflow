"""Phase 3 / 4 markdown export."""

from __future__ import annotations

from datetime import date
from typing import Any

from citeverify.citation_format import (
    apply_year_suffixes_to_registry,
    build_phase4_audit,
    build_reference_entries,
    citation_paren_style,
)
from citeverify.doi_budget import assert_registry_valid, normalize_doi, sort_citations
from citeverify.manuscript import backfill_source_paragraphs, collect_cited_paragraphs
from citeverify.reference_format import format_reference_line, reference_sort_key


def format_inline_citation(
    entry: dict[str, Any],
    *,
    year_suffix: str = "",
    target_journal: str | None = None,
) -> str:
    return format_reference_line(
        entry, year_suffix=year_suffix, target_journal=target_journal
    )


def export_phase3_mapping_table(registry: dict[str, Any]) -> str:
    suffix_by_id = apply_year_suffixes_to_registry(registry)
    journal = registry.get("meta", {}).get("targetJournal")
    lines = [
        "# 阶段 3：【】→ 括号引文对照表",
        "",
        "每个【】对应一行。本表是完整书目，供核对。",
        "",
        "| ID | 【】 | 决定 | 完整引文 |",
        "|----|------|------|----------|",
    ]
    for entry in sort_citations(registry.get("citations", [])):
        decision = entry.get("userDecision") or "pending"
        if decision == "delete_marker":
            replacement = "保留【】，不插引文"
        elif decision in ("", "pending", "replace"):
            replacement = "待确认"
        elif not entry.get("doi"):
            replacement = "缺少 DOI"
        else:
            replacement = format_inline_citation(
                entry,
                year_suffix=suffix_by_id.get(entry["id"], ""),
                target_journal=journal,
            )
        lines.append(
            f"| {entry.get('id')} | {entry.get('marker')} | {decision} | {replacement} |"
        )
    return "\n".join(lines) + "\n"


def export_phase3_body_paragraphs(registry: dict[str, Any]) -> str:
    open_p, close_p = citation_paren_style(registry.get("meta", {}).get("targetJournal"))
    journal = registry.get("meta", {}).get("targetJournal") or "（未指定）"
    lines = [
        "",
        "---",
        "",
        "# 段内引文版正文（可粘贴）",
        "",
        f"目标期刊：{journal}。括号：`{open_p}Author, Year{close_p}`。",
        "`delete_marker` 处保留空【】。相邻多篇合并为一个括号。",
        "",
    ]
    current_section = None
    for block in collect_cited_paragraphs(registry):
        section = block.get("section") or "正文"
        if section != current_section:
            lines.extend([f"## {section}", ""])
            current_section = section
        lines.append(f"<!-- {'、'.join(block['markers'])} -->")
        lines.append(block["cited"])
        lines.append("")
    return "\n".join(lines)


def export_phase3(registry: dict[str, Any], manuscript_path=None) -> str:
    missing = [item["id"] for item in registry["citations"] if not item.get("sourceParagraph")]
    if missing and manuscript_path is not None:
        backfill_source_paragraphs(registry, manuscript_path)
    return export_phase3_mapping_table(registry) + export_phase3_body_paragraphs(registry)


def export_phase4_audit_section(audit: dict[str, Any]) -> str:
    if audit["ok"]:
        conclusion = (
            f"**结论：通过** — {audit['unique_dois']} 篇不同文献已列入 References；"
            f"{audit['repeated_doi_count']} 篇在正文重复引用。"
        )
    else:
        conclusion = " **结论：未通过** — 缺 DOI：" + ", ".join(audit["missing_from_refs"])
    lines = [
        "# 阶段 4：参考文献与正文核查",
        "",
        "## 核查摘要",
        "",
        f"- 引文位：{audit['total_markers']}",
        f"- 删除标记：{audit['delete_marker']}",
        f"- 正文插入：{audit['body_insertions']}",
        f"- 唯一文献：{audit['unique_dois']}",
        "",
        conclusion,
        "",
        "## 重复引用",
        "",
        "| 段内短引 | 次数 | DOI | 引文位 |",
        "|----------|------|-----|--------|",
    ]
    if audit["repeated_groups"]:
        for group in audit["repeated_groups"]:
            lines.append(
                f"| {group['label']} | {group['count']} | {group['doi']} | {group['slots_label']} |"
            )
    else:
        lines.append("| — | — | — | 无重复引用 |")
    lines.extend(["", "---", ""])
    return "\n".join(lines)


def export_phase4(registry: dict[str, Any]) -> str:
    journal = registry.get("meta", {}).get("targetJournal")
    suffix_by_id = apply_year_suffixes_to_registry(registry)
    audit = build_phase4_audit(registry)
    refs = [
        format_reference_line(
            row["entry"],
            year_suffix=row["year_suffix"],
            target_journal=journal,
        )
        for row in build_reference_entries(registry["citations"], suffix_by_id)
    ]
    refs.sort(key=reference_sort_key)
    if not audit["ok"]:
        raise ValueError("阶段 4 未通过：" + ", ".join(audit["missing_from_refs"]))
    body = export_phase4_audit_section(audit)
    body += "# References\n\n"
    body += "\n\n".join(refs) + "\n"
    return body


def run_export(
    registry: dict[str, Any],
    *,
    manuscript_path=None,
    require_locked: bool = False,
) -> tuple[str, str]:
    assert_registry_valid(registry, require_locked=require_locked)
    phase3 = export_phase3(registry, manuscript_path)
    phase4 = export_phase4(registry)
    registry.setdefault("meta", {})
    registry["meta"]["workflowPhase"] = 4
    registry["meta"]["phaseLabel"] = "正文与参考文献已导出"
    registry["meta"]["lastUpdated"] = date.today().isoformat()
    return phase3, phase4


def progress_stats(registry: dict[str, Any]) -> dict[str, int]:
    citations = registry.get("citations", [])
    locked = sum(1 for item in citations if item.get("status") == "locked")
    filled = sum(1 for item in citations if normalize_doi(item.get("doi")))
    deleted = sum(1 for item in citations if item.get("userDecision") == "delete_marker")
    return {
        "total": len(citations),
        "filled": filled,
        "locked": locked,
        "deleted": deleted,
        "pending": len(citations) - locked,
    }
