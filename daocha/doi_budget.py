"""DOI reuse budget and one-to-one marker checks."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

EXEMPT_DECISIONS = frozenset({"delete_marker"})

_MERGED_MARKER_RE = re.compile(r"–|—|/|【[^】]+】【|【\d+[a-z]?–]")


def validate_one_to_one_markers(registry: dict[str, Any]) -> dict[str, Any]:
    expected = registry.get("meta", {}).get("pdfMarkerCount")
    citations = registry.get("citations", [])
    issues: list[str] = []

    if expected is not None and len(citations) != expected:
        issues.append(
            f"entry count {len(citations)} != meta.pdfMarkerCount {expected}"
        )

    seen_markers: set[str] = set()
    for entry in citations:
        marker = entry.get("marker", "")
        cid = entry.get("id", "?")
        if marker.count("【") != 1 or not marker.endswith("】"):
            issues.append(f"{cid}: merged or multi-marker field {marker!r}")
        elif _MERGED_MARKER_RE.search(marker):
            issues.append(f"{cid}: range/slash marker {marker!r}")
        elif marker in seen_markers:
            issues.append(f"{cid}: duplicate marker {marker!r}")
        else:
            seen_markers.add(marker)

    return {
        "ok": not issues,
        "issues": issues,
        "entryCount": len(citations),
        "expectedCount": expected,
    }


def format_marker_report(report: dict[str, Any]) -> str:
    lines = [
        "一对一标记检查",
        f"条目：{report['entryCount']}（期望 {report['expectedCount']}）",
    ]
    if report["ok"]:
        lines.append("通过：每一行对应一个独立【】。")
        return "\n".join(lines)
    lines.append(f"未通过 — {len(report['issues'])} 个问题：")
    lines.extend(f"  {issue}" for issue in report["issues"])
    return "\n".join(lines)


def normalize_doi(raw: str | None) -> str:
    return re.sub(r"^https?://(dx\.)?doi\.org/", "", (raw or "").strip(), flags=re.I)


def _entry_sort_key(entry: dict[str, Any]) -> tuple:
    match = re.match(r"C(\d+)", entry.get("id", ""))
    return (int(match.group(1)) if match else 9999, entry.get("id", ""))


def active_citations(citations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for citation in citations:
        if citation.get("userDecision") in EXEMPT_DECISIONS:
            continue
        doi = normalize_doi(citation.get("doi"))
        if not doi:
            continue
        out.append(citation)
    return sorted(out, key=_entry_sort_key)


def audit_doi_budget(
    registry: dict[str, Any],
    *,
    max_same: int | None = None,
) -> dict[str, Any]:
    max_same = max_same or registry.get("meta", {}).get("constraints", {}).get(
        "maxSameSource", 2
    )
    counts: dict[str, int] = defaultdict(int)
    by_doi: dict[str, list[str]] = defaultdict(list)
    violations: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    for entry in active_citations(registry.get("citations", [])):
        doi = normalize_doi(entry.get("doi"))
        cid = entry["id"]
        counts[doi] += 1
        by_doi[doi].append(cid)
        if counts[doi] > max_same:
            violations.append(
                {
                    "id": cid,
                    "doi": doi,
                    "count": counts[doi],
                    "max": max_same,
                    "prior_ids": by_doi[doi][:-1],
                    "recommended": entry.get("recommended", ""),
                    "claim": entry.get("claim", ""),
                }
            )

    for doi, ids in sorted(by_doi.items(), key=lambda item: (-len(item[1]), item[0])):
        if len(ids) > max_same:
            warnings.append(
                {
                    "doi": doi,
                    "count": len(ids),
                    "ids": ids,
                    "excess": len(ids) - max_same,
                }
            )

    return {
        "maxSameSource": max_same,
        "total_active": sum(len(v) for v in by_doi.values()),
        "unique_dois": len(by_doi),
        "by_doi": dict(by_doi),
        "violations": violations,
        "warnings": warnings,
        "ok": not violations,
    }


def format_audit_report(audit: dict[str, Any]) -> str:
    lines = [
        f"DOI 预算检查（同一 DOI 最多 {audit['maxSameSource']} 次）",
        f"已填 DOI 的有效引文：{audit['total_active']}",
    ]
    if audit["ok"]:
        lines.append("通过：没有超出预算的条目。")
        return "\n".join(lines)

    lines.append(f"未通过 — {len(audit['violations'])} 处超限：")
    for item in audit["violations"]:
        lines.append(
            f"  {item['id']}: DOI {item['doi']} 已是第 {item['count']} 次"
            f"（上限 {item['max']}）；先前：{', '.join(item['prior_ids'])}"
        )
    return "\n".join(lines)


def assert_registry_valid(
    registry: dict[str, Any],
    *,
    require_locked: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    marker_report = validate_one_to_one_markers(registry)
    if not marker_report["ok"]:
        raise ValueError(format_marker_report(marker_report))
    audit = audit_doi_budget(registry)
    if not audit["ok"]:
        raise ValueError(format_audit_report(audit))
    if require_locked:
        pending = [
            citation["id"]
            for citation in registry.get("citations", [])
            if citation.get("status") != "locked"
        ]
        if pending:
            raise ValueError("尚未锁定的条目：" + ", ".join(pending))
        unfinished = [
            citation["id"]
            for citation in registry.get("citations", [])
            if citation.get("userDecision") not in ("keep", "delete_marker")
        ]
        if unfinished:
            raise ValueError(
                "尚未完成的条目（请改成保留或删除【】）：" + ", ".join(unfinished)
            )
    missing_doi = [
        citation["id"]
        for citation in registry.get("citations", [])
        if citation.get("userDecision") == "keep" and not normalize_doi(citation.get("doi"))
    ]
    if missing_doi:
        raise ValueError("选了保留但没有 DOI，请换一篇：" + ", ".join(missing_doi))
    return marker_report, audit


def load_registry(path: Path | str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sort_citations(citations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def key(citation: dict[str, Any]) -> tuple:
        idx = citation.get("markerIndex")
        if idx is not None:
            return (idx, citation.get("id", ""))
        return _entry_sort_key(citation)

    return sorted(citations, key=key)


def check_doi_available(
    registry: dict[str, Any],
    doi: str,
    *,
    entry_id: str | None = None,
    max_same: int | None = None,
) -> tuple[bool, list[str]]:
    doi = normalize_doi(doi)
    max_same = max_same or registry.get("meta", {}).get("constraints", {}).get(
        "maxSameSource", 2
    )
    prior: list[str] = []
    for entry in active_citations(registry.get("citations", [])):
        if entry_id and entry["id"] == entry_id:
            break
        if normalize_doi(entry.get("doi")) == doi:
            prior.append(entry["id"])
    return len(prior) < max_same, prior


