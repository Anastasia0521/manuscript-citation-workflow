"""Journal-aware inline citation formatting."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from daocha.doi_budget import normalize_doi, sort_citations
from daocha.journals import style_for_journal

KEEP_DECISIONS = frozenset({"keep"})


def citation_paren_style(target_journal: str | None) -> tuple[str, str]:
    style = style_for_journal(target_journal)
    if style.paren == "fullwidth":
        return "（", "）"
    return "(", ")"


def author_label(entry: dict[str, Any]) -> str:
    rec = (entry.get("recommended") or "").strip()
    if "（" in rec:
        rec = rec.split("（", 1)[0].strip()
    if " + " in rec:
        rec = rec.split(" + ", 1)[0].strip()
    match = re.match(r"^(.+),\s*(\d{4})$", rec)
    if match:
        return match.group(1).strip()
    authors = (entry.get("authorsFormatted") or "").rstrip(",")
    if authors:
        names = [part.strip() for part in authors.split(",") if part.strip()]
        if len(names) >= 2:
            return f"{names[0]} et al." if len(names) > 2 else f"{names[0]} and {names[1]}"
        return names[0] if names else entry.get("id", "?")
    return rec or entry.get("id", "?")


def author_year(entry: dict[str, Any]) -> tuple[str, str]:
    rec = (entry.get("recommended") or "").strip()
    if "（" in rec:
        rec = rec.split("（", 1)[0].strip()
    year = str(entry.get("year") or "")
    match = re.match(r"^(.+),\s*(\d{4})$", rec)
    if match:
        return match.group(1).strip(), match.group(2)
    return author_label(entry), year


def is_body_citation(entry: dict[str, Any]) -> bool:
    decision = entry.get("userDecision") or ""
    if decision != "keep":
        return False
    return bool(normalize_doi(entry.get("doi")))


def is_reference_entry(entry: dict[str, Any]) -> bool:
    return is_body_citation(entry)


def assign_year_suffixes(citations: list[dict[str, Any]]) -> dict[str, str]:
    groups: dict[tuple[str, str], list[tuple[str, str, int]]] = defaultdict(list)
    for entry in sort_citations(citations):
        if not is_body_citation(entry):
            continue
        doi = normalize_doi(entry.get("doi"))
        if not doi:
            continue
        author, year = author_year(entry)
        groups[(author, year)].append(
            (entry["id"], doi, entry.get("markerIndex") or 0)
        )

    suffix_by_id: dict[str, str] = {}
    for items in groups.values():
        unique_dois: list[str] = []
        seen: set[str] = set()
        for _cid, doi, _idx in sorted(items, key=lambda item: item[2]):
            if doi not in seen:
                seen.add(doi)
                unique_dois.append(doi)
        if len(unique_dois) <= 1:
            for cid, _doi, _ in items:
                suffix_by_id[cid] = ""
            continue
        letters = "abcdefghijklmnopqrstuvwxyz"
        doi_to_suffix = {
            doi: letters[i] for i, doi in enumerate(unique_dois[: len(letters)])
        }
        for cid, doi, _ in items:
            suffix_by_id[cid] = doi_to_suffix.get(doi, "")
    return suffix_by_id


def format_short_cite(
    entry: dict[str, Any],
    *,
    open_p: str,
    close_p: str,
    year_suffix: str = "",
) -> str:
    label = author_label(entry)
    if label.startswith("—") or label in ("?", entry.get("marker", "")):
        return entry.get("marker", "")
    _author, year = author_year(entry)
    if not year:
        year = str(entry.get("year") or "")
    if year_suffix:
        year = f"{year}{year_suffix}"
    return f"{open_p}{label}, {year}{close_p}"


def merge_adjacent_citation_groups(text: str, open_p: str, close_p: str) -> str:
    inner = rf"[^{re.escape(close_p)}]+"
    single = rf"{re.escape(open_p)}({inner}){re.escape(close_p)}"
    run = re.compile(rf"(?:{single})(?:\s*{single})+")

    def repl(match: re.Match[str]) -> str:
        inners = re.findall(single, match.group(0))
        seen: list[str] = []
        for item in inners:
            if item not in seen:
                seen.append(item)
        if len(seen) <= 1:
            return f"{open_p}{seen[0]}{close_p}" if seen else match.group(0)
        return f"{open_p}{'; '.join(seen)}{close_p}"

    return run.sub(repl, text)


def apply_year_suffixes_to_registry(registry: dict[str, Any]) -> dict[str, str]:
    suffix_by_id = assign_year_suffixes(registry.get("citations", []))
    for entry in registry.get("citations", []):
        entry["yearSuffix"] = suffix_by_id.get(entry["id"], "")
    return suffix_by_id


def build_reference_entries(
    citations: list[dict[str, Any]],
    suffix_by_id: dict[str, str],
) -> list[dict[str, Any]]:
    seen: set[str] = set()
    rows: list[dict[str, Any]] = []
    for entry in sort_citations(citations):
        if not is_reference_entry(entry):
            continue
        doi = normalize_doi(entry.get("doi"))
        if not doi or doi in seen:
            continue
        seen.add(doi)
        rows.append(
            {
                "entry": entry,
                "doi": doi,
                "year_suffix": suffix_by_id.get(entry["id"], ""),
                "first_id": entry["id"],
            }
        )
    return rows


def build_doi_usage_map(
    citations: list[dict[str, Any]],
    suffix_by_id: dict[str, str],
    open_p: str,
    close_p: str,
) -> dict[str, dict[str, Any]]:
    usage: dict[str, dict[str, Any]] = {}
    for entry in sort_citations(citations):
        if not is_body_citation(entry):
            continue
        doi = normalize_doi(entry.get("doi"))
        if not doi:
            continue
        cid = entry["id"]
        short = format_short_cite(
            entry,
            open_p=open_p,
            close_p=close_p,
            year_suffix=suffix_by_id.get(cid, ""),
        )
        slot = {
            "id": cid,
            "marker": entry.get("marker", ""),
            "short_cite": short,
            "marker_index": entry.get("markerIndex") or 0,
        }
        if doi not in usage:
            usage[doi] = {
                "doi": doi,
                "label": short,
                "title": (entry.get("title") or "")[:80],
                "recommended": entry.get("recommended", ""),
                "occurrences": [],
            }
        usage[doi]["occurrences"].append(slot)

    for info in usage.values():
        info["occurrences"].sort(key=lambda item: item["marker_index"])
        info["count"] = len(info["occurrences"])
        info["first_id"] = info["occurrences"][0]["id"]
        info["slots_label"] = "；".join(
            f"{item['id']}{item['marker']}" for item in info["occurrences"]
        )
    return usage


def build_phase4_audit(registry: dict[str, Any]) -> dict[str, Any]:
    citations = registry.get("citations", [])
    suffix_by_id = assign_year_suffixes(citations)
    open_p, close_p = citation_paren_style(registry.get("meta", {}).get("targetJournal"))
    ref_rows = build_reference_entries(citations, suffix_by_id)
    ref_dois = {row["doi"] for row in ref_rows}
    doi_first_id = {row["doi"]: row["first_id"] for row in ref_rows}
    doi_usage = build_doi_usage_map(citations, suffix_by_id, open_p, close_p)
    repeated = sorted(
        [item for item in doi_usage.values() if item["count"] >= 2],
        key=lambda item: (-item["count"], item["first_id"]),
    )
    single = sorted(
        [item for item in doi_usage.values() if item["count"] == 1],
        key=lambda item: item["first_id"],
    )
    rows: list[dict[str, Any]] = []
    stats = {
        "total_markers": len(citations),
        "delete_marker": 0,
        "body_insertions": 0,
        "unique_dois": len(ref_dois),
        "reference_count": len(ref_rows),
        "reuse_count": 0,
        "repeated_doi_count": len(repeated),
        "single_cite_doi_count": len(single),
        "missing_from_refs": [],
        "doi_usage": doi_usage,
        "repeated_groups": repeated,
        "single_cite_groups": single,
    }
    doi_occurrence_index: dict[str, dict[str, int]] = defaultdict(dict)
    for doi, info in doi_usage.items():
        for i, occ in enumerate(info["occurrences"], start=1):
            doi_occurrence_index[doi][occ["id"]] = i

    for entry in sort_citations(citations):
        cid = entry["id"]
        decision = entry.get("userDecision") or ""
        doi = normalize_doi(entry.get("doi"))
        short = ""
        if decision == "delete_marker":
            stats["delete_marker"] += 1
            ref_status = "—"
            note = "delete_marker：正文保留【】，不进 References"
            cite_order = "—"
        elif not is_body_citation(entry):
            ref_status = "—"
            note = f"{decision or 'pending'}：未纳入正文引文"
            cite_order = "—"
        else:
            stats["body_insertions"] += 1
            short = format_short_cite(
                entry,
                open_p=open_p,
                close_p=close_p,
                year_suffix=suffix_by_id.get(cid, ""),
            )
            total = doi_usage.get(doi, {}).get("count", 1) if doi else 1
            idx = doi_occurrence_index.get(doi, {}).get(cid, 1) if doi else 1
            cite_order = f"{idx}/{total}" if total > 1 else "1/1"
            if not doi:
                ref_status = "缺失"
                note = "无 DOI，无法列入 References"
                stats["missing_from_refs"].append(cid)
            elif doi in ref_dois:
                first = doi_first_id[doi]
                ref_status = "✓ 已收录"
                if first == cid:
                    note = (
                        f"References 书目条目；该文献正文共引用 {total} 次"
                        if total > 1
                        else "References 书目条目；正文仅引用 1 次"
                    )
                else:
                    note = f"第 {idx}/{total} 次引用；与 {first} 同一 DOI"
                    stats["reuse_count"] += 1
            else:
                ref_status = "✗ 遗漏"
                note = "DOI 未出现在 References 列表"
                stats["missing_from_refs"].append(cid)
        rows.append(
            {
                "id": cid,
                "marker": entry.get("marker", ""),
                "decision": decision,
                "short_cite": short,
                "doi": doi,
                "ref_status": ref_status,
                "note": note,
                "cite_order": cite_order,
            }
        )
    stats["ok"] = not stats["missing_from_refs"]
    stats["rows"] = rows
    stats["ref_dois"] = ref_dois
    return stats
