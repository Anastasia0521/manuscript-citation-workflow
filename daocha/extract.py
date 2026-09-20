"""Extract 【n】 markers from PDF or Word body text."""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

# Manuscript slots are empty 【】; the app numbers them 【1】【2】… in document order.
VALID_INNER_RE = re.compile(r"^\d+$")
ANY_MARKER_RE = re.compile(r"【[^】]*】")
SPACED_NUMBER_RE = re.compile(r"【\s*(\d+)\s*】")
EMPTY_SLOT_RE = re.compile(r"【[\s\ufffd]*】")
RANGE_INNER_RE = re.compile(r"[-–—,/]|到|至")
FULLWIDTH_DIGITS = str.maketrans("０１２３４５６７８９", "0123456789")
EMPTY_INNER_CHARS = frozenset(" \t\r\n\u3000\ufffd")

# Re-exported name used by manuscript.py
MARKER_RE = ANY_MARKER_RE


class MarkerExtractError(ValueError):
    def __init__(self, report: dict[str, Any]):
        self.report = report
        super().__init__(format_extract_report(report))


def is_empty_slot_inner(inner: str) -> bool:
    return (not inner.strip()) or all(char in EMPTY_INNER_CHARS for char in inner)


def is_slot_token(raw: str) -> bool:
    if not (raw.startswith("【") and raw.endswith("】") and len(raw) >= 2):
        return False
    inner = raw[1:-1]
    if is_empty_slot_inner(inner):
        return True
    return bool(VALID_INNER_RE.fullmatch(inner.strip()))


def normalize_manuscript_text(text: str) -> str:
    """Unify digits, collapse empty 【 】, and close up 【 12 】 → 【12】."""
    text = text.translate(FULLWIDTH_DIGITS)
    text = EMPTY_SLOT_RE.sub("【】", text)
    return SPACED_NUMBER_RE.sub(lambda m: f"【{m.group(1)}】", text)


def read_manuscript_text(path: Path | str) -> str:
    return "\n".join(chunk for _loc, chunk in iter_text_chunks(path))


def iter_text_chunks(path: Path | str) -> list[tuple[str, str]]:
    source = Path(path)
    suffix = source.suffix.lower()
    if suffix == ".doc":
        raise ValueError("不支持旧版 .doc，请另存为 .docx 或 PDF。")
    if suffix == ".pdf":
        import fitz

        doc = fitz.open(source)
        chunks: list[tuple[str, str]] = []
        for index, page in enumerate(doc, start=1):
            chunks.append((f"第 {index} 页", page.get_text("text") or ""))
        doc.close()
        return chunks
    if suffix == ".docx":
        from docx import Document

        document = Document(str(source))
        chunks = []
        for index, para in enumerate(document.paragraphs, start=1):
            if para.text.strip():
                chunks.append((f"正文第 {index} 段", para.text))
        for t_i, table in enumerate(document.tables, start=1):
            for r_i, row in enumerate(table.rows, start=1):
                cell_text = " ".join(cell.text for cell in row.cells if cell.text.strip())
                if cell_text:
                    chunks.append((f"表格 {t_i} 第 {r_i} 行", cell_text))
        return chunks
    if suffix in {".txt", ".md"}:
        return [("全文", source.read_text(encoding="utf-8"))]
    raise ValueError(f"请使用 PDF、.docx、.txt 或 .md（当前是 {suffix or source.name}）")


def _snippet(text: str, start: int, end: int, radius: int = 40) -> str:
    a = max(0, start - radius)
    b = min(len(text), end + radius)
    return re.sub(r"\s+", " ", text[a:b]).strip()


def _classify_marker(raw: str, *, location: str, snippet: str) -> dict[str, Any]:
    inner = raw[1:-1]
    base = {"marker": raw, "location": location, "context": snippet}
    if is_empty_slot_inner(inner):
        return {**base, "kind": "empty", "marker": "【】"}
    if RANGE_INNER_RE.search(inner) or inner.count("【"):
        return {**base, "kind": "range"}
    if not VALID_INNER_RE.fullmatch(inner.strip()):
        return {**base, "kind": "invalid"}
    return {**base, "kind": "numbered", "marker": f"【{inner.strip()}】"}


def analyze_markers(text: str, *, location: str = "") -> dict[str, Any]:
    text = normalize_manuscript_text(text)
    issues: list[dict[str, Any]] = []
    slots: list[dict[str, str]] = []

    for match in ANY_MARKER_RE.finditer(text):
        classified = _classify_marker(
            match.group(0),
            location=location,
            snippet=_snippet(text, match.start(), match.end()),
        )
        kind = classified.pop("kind")
        if kind in {"range", "invalid"}:
            issues.append({"type": kind, **classified})
            continue
        slots.append({"kind": kind, **classified})

    return _finalize_slots(slots, issues)


def _finalize_slots(
    slots: list[dict[str, str]], issues: list[dict[str, Any]]
) -> dict[str, Any]:
    empties = [item for item in slots if item.get("kind") == "empty"]
    numbered = [item for item in slots if item.get("kind") == "numbered"]

    if empties and numbered:
        issues.append(
            {
                "type": "mixed",
                "marker": "【】 / 【n】",
                "location": "",
                "context": "请统一写成空的【】，由软件编号；或全文都用互不重复的【1】【2】",
            }
        )
        return {
            "markers": [],
            "issues": issues,
            "valid_slots": 0,
            "raw_hits": len(slots),
        }

    if empties:
        markers = [
            {
                "marker": f"【{index}】",
                "context": item.get("context") or "",
                "location": item.get("location") or "",
            }
            for index, item in enumerate(empties, start=1)
        ]
        return {
            "markers": markers,
            "issues": issues,
            "valid_slots": len(markers),
            "raw_hits": len(slots),
        }

    by_marker: dict[str, list[dict[str, str]]] = defaultdict(list)
    for item in numbered:
        by_marker[item["marker"]].append(item)
    unique: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in numbered:
        marker = item["marker"]
        if marker in seen:
            continue
        seen.add(marker)
        copies = by_marker[marker]
        if len(copies) > 1:
            issues.append(
                {
                    "type": "duplicate",
                    "marker": marker,
                    "count": len(copies),
                    "location": "；".join(
                        sorted({c.get("location") or "" for c in copies if c.get("location")})
                    ),
                    "context": copies[0].get("context") or "",
                }
            )
            continue
        unique.append(
            {
                "marker": item["marker"],
                "context": item.get("context") or "",
                "location": item.get("location") or "",
            }
        )
    return {
        "markers": unique,
        "issues": issues,
        "valid_slots": len(unique),
        "raw_hits": len(slots),
    }


def analyze_file(path: Path | str) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    slots: list[dict[str, str]] = []
    for location, chunk in iter_text_chunks(path):
        text = normalize_manuscript_text(chunk)
        for match in ANY_MARKER_RE.finditer(text):
            classified = _classify_marker(
                match.group(0),
                location=location,
                snippet=_snippet(text, match.start(), match.end()),
            )
            kind = classified.pop("kind")
            if kind in {"range", "invalid"}:
                issues.append({"type": kind, **classified})
            else:
                slots.append({"kind": kind, **classified})
    return _finalize_slots(slots, issues)


def format_extract_report(report: dict[str, Any]) -> str:
    lines = [
        "【】抽取未通过。请在每个要插文献的位置写空的【】（编号由软件按出现顺序生成）。不要写【1-3】。",
        f"合法引文位：{report.get('valid_slots', 0)}",
        f"问题：{len(report.get('issues') or [])} 处",
        "",
    ]
    labels = {
        "range": "合并/范围编号",
        "duplicate": "同一个号用了两次",
        "invalid": "括号里不是空的，也不是纯数字编号",
        "mixed": "空【】和已编号【n】混用",
    }
    for issue in report.get("issues") or []:
        kind = labels.get(issue.get("type"), issue.get("type"))
        loc = issue.get("location") or ""
        marker = issue.get("marker") or ""
        ctx = issue.get("context") or ""
        extra = f" ×{issue['count']}" if issue.get("count") else ""
        lines.append(f"- {kind}{extra}: {marker}  {loc}")
        if ctx:
            lines.append(f"  附近：{ctx}")
    return "\n".join(lines).strip()


def extract_markers(path: Path | str) -> list[dict[str, str]]:
    report = analyze_file(path)
    if report["issues"]:
        raise MarkerExtractError(report)
    if not report["markers"]:
        raise MarkerExtractError(
            {
                **report,
                "issues": [
                    {
                        "type": "invalid",
                        "marker": "",
                        "location": "",
                        "context": "没有找到【】占位。每个要插文献的位置请写成空的【】。",
                    }
                ],
            }
        )
    return report["markers"]


def empty_citation(index: int, marker: str, context: str, location: str = "") -> dict[str, Any]:
    return {
        "id": f"C{index:03d}",
        "markerIndex": index,
        "marker": marker,
        "section": "",
        "location": location,
        "claim": "",
        "recommended": "",
        "title": "",
        "journal": "",
        "year": None,
        "doi": "",
        "url": "",
        "excerpt": context[:400],
        "sourceParagraph": "",
        "strength": "",
        "status": "pending",
        "userDecision": "",
        "userNote": "",
    }


def build_registry(
    markers: list[dict[str, str]],
    *,
    project_id: str,
    manuscript_name: str,
    title: str = "",
    target_journal: str = "Journal of Environmental Management",
    max_same_source: int = 2,
    ban_mdpi: bool = True,
) -> dict[str, Any]:
    citations = [
        empty_citation(
            i,
            item["marker"],
            item.get("context") or "",
            item.get("location") or "",
        )
        for i, item in enumerate(markers, start=1)
    ]
    return {
        "meta": {
            "projectId": project_id,
            "manuscriptTitle": title,
            "manuscriptFile": manuscript_name,
            "targetJournal": target_journal,
            "workflowPhase": 1,
            "phaseLabel": "核查中",
            "lastUpdated": date.today().isoformat(),
            "constraints": {
                "banMdpi": True,
                "maxSameSource": max_same_source,
            },
            "pdfMarkerCount": len(citations),
            "registryEntryCount": len(citations),
            "oneToOneMarkers": True,
        },
        "citations": citations,
    }
