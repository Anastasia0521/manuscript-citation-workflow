"""Reference-list formatters for JEM and GB/T 7714."""

from __future__ import annotations

import re
from typing import Any

from daocha.doi_budget import normalize_doi
from daocha.journals import style_for_journal

JOURNAL_ABBREV: dict[str, str] = {
    "Journal of Environmental Management": "J. Environ. Manag.",
    "Ecological Economics": "Ecol. Econ.",
    "Environmental Research Letters": "Environ. Res. Lett.",
    "Land Use Policy": "Land Use Policy",
    "Nature Communications": "Nat. Commun.",
    "Science of The Total Environment": "Sci. Total Environ.",
    "Science of the Total Environment": "Sci. Total Environ.",
    "Policy Studies Journal": "Policy Stud. J.",
    "Biodiversity and Conservation": "Biodivers. Conserv.",
    "Biological Conservation": "Biol. Conserv.",
    "Ecosystem Services": "Ecosyst. Serv.",
    "Global Ecology and Conservation": "Glob. Ecol. Conserv.",
    "Ecological Indicators": "Ecol. Indic.",
    "Conservation and Society": "Conserv. Soc.",
    "Political Research Quarterly": "Pol. Res. Q.",
}


def abbreviate_journal(name: str) -> str:
    name = (name or "").strip()
    if not name:
        return ""
    if name in JOURNAL_ABBREV:
        return JOURNAL_ABBREV[name]
    skip = {"of", "the", "and", "for", "in", "on", "a", "an"}
    words = name.replace("-", " ").split()
    out: list[str] = []
    for i, word in enumerate(words):
        low = word.lower()
        if low in skip and 0 < i < len(words) - 1:
            out.append(low)
        elif len(word) <= 3 and word.isupper():
            out.append(word)
        else:
            out.append(word[:1].upper() + "." if len(word) > 4 else word)
    return " ".join(out) + ("." if out and not out[-1].endswith(".") else "")


def _normalize_pages(page: str | None) -> str:
    if not page:
        return ""
    if re.search(r"\d-\d", page):
        return page.replace("--", "–").replace("-", "–")
    return page


def format_volume_issue_pages(
    volume: str | int | None,
    issue: str | int | None,
    page: str | None,
    article_number: str | None,
) -> str:
    vol = str(volume).strip() if volume not in (None, "") else ""
    iss = str(issue).strip() if issue not in (None, "") else ""
    pg = _normalize_pages(page)
    art = str(article_number).strip() if article_number not in (None, "") else ""
    if vol and iss and pg:
        return f"{vol} ({iss}), {pg}."
    if vol and iss and art:
        return f"{vol} ({iss}), {art}."
    if vol and pg:
        return f"{vol}, {pg}."
    if vol and art:
        return f"{vol}, {art}."
    if vol:
        return f"{vol}."
    if pg:
        return f"{pg}."
    if art:
        return f"{art}."
    return ""


def format_reference_line_jem(entry: dict[str, Any], *, year_suffix: str = "") -> str:
    authors = entry.get("authorsFormatted") or ""
    if not authors:
        rec = (entry.get("recommended") or "").split("（")[0].strip()
        match = re.match(r"^(.+),\s*(\d{4})$", rec)
        authors = match.group(1).strip() if match else rec
    year = entry.get("year")
    if year_suffix:
        year = f"{year}{year_suffix}"
    year = str(year or "")
    title = (entry.get("title") or "").strip()
    if title and not title.endswith("."):
        title += "."
    journal = entry.get("journalAbbrev") or abbreviate_journal(entry.get("journal") or "")
    vip = format_volume_issue_pages(
        entry.get("volume"),
        entry.get("issue"),
        entry.get("pages"),
        entry.get("articleNumber"),
    )
    doi = normalize_doi(entry.get("doi"))
    parts = [f"{authors}, {year}. {title}".strip()]
    if journal:
        parts.append(f"{journal} {vip}".strip() if vip else f"{journal}.")
    elif vip:
        parts.append(vip)
    line = " ".join(part for part in parts if part)
    if doi:
        line = line.rstrip(".") + f". https://doi.org/{doi}."
    elif not line.endswith("."):
        line += "."
    return line


def _gbt_authors(entry: dict[str, Any]) -> str:
    authors = entry.get("authors") or []
    names: list[str] = []
    for author in authors:
        family = (author.get("family") or "").strip()
        given = (author.get("given") or "").strip()
        if not family:
            continue
        if re.search(r"[\u4e00-\u9fff]", family + given):
            names.append(f"{family}{given}")
        else:
            initials = "".join(part[0].upper() for part in re.split(r"[\s\-]+", given) if part)
            names.append(f"{family} {initials}".strip())
    if not names:
        rec = (entry.get("recommended") or "").split(",")[0].strip()
        return rec
    if len(names) > 3:
        return ", ".join(names[:3]) + ", 等"
    return ", ".join(names)


def format_reference_line_gbt7714(entry: dict[str, Any], *, year_suffix: str = "") -> str:
    authors = _gbt_authors(entry)
    year = str(entry.get("year") or "")
    if year_suffix:
        year = f"{year}{year_suffix}"
    title = (entry.get("title") or "").rstrip(".")
    journal = entry.get("journal") or ""
    vol = entry.get("volume") or ""
    issue = entry.get("issue") or ""
    pages = _normalize_pages(entry.get("pages")) or entry.get("articleNumber") or ""
    doi = normalize_doi(entry.get("doi"))
    loc = ""
    if vol and issue and pages:
        loc = f"{vol}({issue}): {pages}"
    elif vol and pages:
        loc = f"{vol}: {pages}"
    elif vol:
        loc = str(vol)
    parts = [f"{authors}, {year}. {title}[J]. {journal}"]
    if loc:
        parts[0] += f", {loc}"
    line = parts[0] + "."
    if doi:
        line += f" https://doi.org/{doi}."
    return line


def format_reference_line(
    entry: dict[str, Any],
    *,
    year_suffix: str = "",
    target_journal: str | None = None,
) -> str:
    style = style_for_journal(target_journal)
    if style.reference_style == "gbt7714":
        return format_reference_line_gbt7714(entry, year_suffix=year_suffix)
    return format_reference_line_jem(entry, year_suffix=year_suffix)


def reference_sort_key(line: str) -> str:
    match = re.match(r"^([^,]+)", line)
    key = (match.group(1) if match else line).strip().lower()
    return re.sub(r"^(de|van|von|le|la)\s+", "", key)
