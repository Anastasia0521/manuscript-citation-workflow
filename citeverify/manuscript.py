"""Read source sentences and splice short citations back into the body."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from citeverify.citation_format import (
    apply_year_suffixes_to_registry,
    citation_paren_style,
    format_short_cite,
    merge_adjacent_citation_groups,
)
from citeverify.extract import (
    MARKER_RE,
    is_slot_token,
    normalize_manuscript_text,
    read_manuscript_text,
)

CJK_RE = re.compile(r"[\u4e00-\u9fff]")
LATIN_WORD_RE = re.compile(r"[A-Za-z]{3,}")
# Chinese stops, or English . ! ? that look like sentence ends
SENTENCE_BREAK_RE = re.compile(
    r"[。！？]|】\.(?=\s|$)|(?<=[A-Za-z0-9\"”')])\.(?=\s|$)|(?<=[A-Za-z0-9])[!?]+(?=\s|$)"
)


def inject_canonical_markers(text: str, registry_markers: list[str]) -> str:
    text = normalize_manuscript_text(text)
    parts: list[str] = []
    last = 0
    found = list(MARKER_RE.finditer(text))
    slots = [match for match in found if is_slot_token(match.group(0))]
    if len(slots) != len(registry_markers):
        raise ValueError(
            "稿件里的【】数量和登记表不一致："
            f"稿件 {len(slots)} 处，登记 {len(registry_markers)} 处。"
            "请不要增删【】后再导出；必要时用原稿重新建项目。"
        )
    for i, match in enumerate(slots):
        parts.append(text[last : match.start()])
        parts.append(registry_markers[i])
        last = match.end()
    parts.append(text[last:])
    return "".join(parts)


def _rfind_break(text: str, end: int) -> int:
    chunk = text[:end]
    last = -1
    for match in SENTENCE_BREAK_RE.finditer(chunk):
        last = match.end()
    # also treat punctuation immediately before the search window
    return last if last >= 0 else 0


def sentence_span(text: str, marker: str) -> tuple[int, int]:
    pos = text.find(marker)
    if pos < 0:
        raise ValueError(f"未找到标记：{marker}")
    start = _rfind_break(text, pos)
    while start < pos and text[start] in " \t\n\r　":
        start += 1

    after = pos + len(marker)
    if after < len(text) and text[after] in ".。!！?？":
        return start, after + 1

    rest = text[after:]
    end_match = SENTENCE_BREAK_RE.search(rest)
    if end_match:
        return start, after + end_match.end()
    para = text.find("\n\n", after)
    end = para if para >= 0 else min(len(text), after + 500)
    return start, end


def normalize_sentence(text: str) -> str:
    """Keep English word spaces; collapse CJK-only runs of whitespace."""
    if CJK_RE.search(text) and not LATIN_WORD_RE.search(text):
        return re.sub(r"\s+", "", text)
    return re.sub(r"[ \t\r\n　]+", " ", text).strip()


def extract_source_paragraph(text: str, marker: str) -> str:
    start, end = sentence_span(text, marker)
    return normalize_sentence(text[start:end])


def backfill_source_paragraphs(
    registry: dict[str, Any],
    manuscript_path: Path | str,
) -> dict[str, str]:
    text = read_manuscript_text(manuscript_path)
    markers = [item["marker"] for item in registry["citations"]]
    canonical = inject_canonical_markers(text, markers)
    updates: dict[str, str] = {}
    for entry in registry["citations"]:
        para = extract_source_paragraph(canonical, entry["marker"])
        if entry.get("sourceParagraph") != para:
            entry["sourceParagraph"] = para
            updates[entry["id"]] = para
    return updates


def apply_inline_citations(
    paragraph: str,
    entries_by_marker: dict[str, dict],
    *,
    open_p: str,
    close_p: str,
    suffix_by_id: dict[str, str],
) -> str:
    markers = sorted(entries_by_marker.keys(), key=len, reverse=True)
    out = paragraph
    for marker in markers:
        entry = entries_by_marker[marker]
        decision = entry.get("userDecision") or ""
        if decision == "delete_marker":
            out = out.replace(marker, "【】")
            continue
        if decision != "keep" or not entry.get("doi"):
            continue
        out = out.replace(
            marker,
            format_short_cite(
                entry,
                open_p=open_p,
                close_p=close_p,
                year_suffix=suffix_by_id.get(entry["id"], ""),
            ),
        )
    return merge_adjacent_citation_groups(out, open_p, close_p)


def collect_cited_paragraphs(registry: dict[str, Any]) -> list[dict[str, Any]]:
    suffix_by_id = apply_year_suffixes_to_registry(registry)
    open_p, close_p = citation_paren_style(registry.get("meta", {}).get("targetJournal"))
    by_marker = {item["marker"]: item for item in registry["citations"]}
    seen: set[str] = set()
    blocks: list[dict[str, Any]] = []
    for entry in sorted(registry["citations"], key=lambda item: item.get("markerIndex", 0)):
        raw = entry.get("sourceParagraph") or ""
        if not raw or raw in seen:
            continue
        seen.add(raw)
        markers_in_para = [marker for marker in by_marker if marker in raw]
        cited = apply_inline_citations(
            raw,
            {marker: by_marker[marker] for marker in markers_in_para},
            open_p=open_p,
            close_p=close_p,
            suffix_by_id=suffix_by_id,
        )
        blocks.append(
            {
                "section": entry.get("section") or "",
                "markers": markers_in_para,
                "raw": raw,
                "cited": cited,
            }
        )
    return blocks
