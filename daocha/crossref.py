"""Crossref lookup for English journal articles."""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from daocha.doi_budget import normalize_doi
from daocha.mdpi import is_mdpi_record, mdpi_reason

_CACHE: dict[str, dict[str, Any]] = {}
USER_AGENT = (
    "Daocha/1.0 (https://github.com/Anastasia0521/manuscript-citation-workflow; "
    "mailto:anastasiachan@163.com)"
)
_CJK_RE = re.compile(r"[\u4e00-\u9fff]")
ALLOWED_TYPES = frozenset({"journal-article"})


def _get(url: str, *, retries: int = 3) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    last: Exception | None = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=25) as resp:
                return json.load(resp)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last = exc
            time.sleep(0.4 * (attempt + 1))
    raise RuntimeError(f"Crossref 请求失败：{last}") from last


def _author_initials(given: str) -> str:
    given = (given or "").strip()
    if not given:
        return ""
    words = [word for word in re.split(r"[\s\-]+", given) if word]
    return " ".join(f"{word[0].upper()}." for word in words)


def format_crossref_author(author: dict[str, Any]) -> str:
    family = (author.get("family") or "").strip()
    given = (author.get("given") or "").strip()
    initials = _author_initials(given)
    if not family:
        return initials
    if not initials:
        return family
    return f"{family}, {initials}"


def format_authors(authors: list[dict[str, Any]], *, max_listed: int = 6) -> str:
    formatted = [format_crossref_author(item) for item in authors if item.get("family")]
    if not formatted:
        return ""
    if len(formatted) > max_listed:
        return ", ".join(formatted[:max_listed]) + ", et al."
    return ", ".join(formatted)


def recommended_from_authors(authors: list[dict[str, Any]], year: Any) -> str:
    families = [item.get("family", "").strip() for item in authors if item.get("family")]
    year_s = str(year or "")
    if not families:
        return year_s
    if len(families) == 1:
        label = families[0]
    elif len(families) == 2:
        label = f"{families[0]} and {families[1]}"
    else:
        label = f"{families[0]} et al."
    return f"{label}, {year_s}".strip(", ")


def work_to_meta(work: dict[str, Any]) -> dict[str, Any]:
    authors = work.get("author") or []
    year = (
        work.get("published-print")
        or work.get("published")
        or work.get("created")
        or {}
    ).get("date-parts", [[None]])[0][0]
    journal = (work.get("container-title") or [""])[0]
    title = (work.get("title") or [""])[0]
    doi = normalize_doi(work.get("DOI"))
    return {
        "doi": doi,
        "title": title,
        "journal": journal,
        "year": year,
        "volume": work.get("volume"),
        "issue": work.get("issue"),
        "pages": work.get("page"),
        "articleNumber": work.get("article-number"),
        "authors": authors,
        "authorsFormatted": format_authors(authors),
        "recommended": recommended_from_authors(authors, year),
        "url": f"https://doi.org/{doi}" if doi else "",
        "publisher": work.get("publisher") or "",
        "member": str(work.get("member") or ""),
        "type": work.get("type") or "",
        "issn": work.get("ISSN") or [],
    }


def usable_journal_article(meta: dict[str, Any]) -> bool:
    """Return True if this Crossref record can be adopted."""
    try:
        require_usable_journal_article(meta)
    except ValueError:
        return False
    return True


def require_usable_journal_article(meta: dict[str, Any]) -> None:
    if is_mdpi_record(meta):
        raise ValueError(f"禁止 MDPI：{mdpi_reason(meta)}")
    if not normalize_doi(meta.get("doi")):
        raise ValueError("没有 DOI，请换一篇能核对的英文期刊论文。")
    work_type = (meta.get("type") or "").strip()
    if work_type and work_type not in ALLOWED_TYPES:
        raise ValueError(
            f"这不是期刊论文（Crossref type={work_type}）。请换一篇带 DOI 的英文期刊论文。"
        )
    title = meta.get("title") or ""
    if _CJK_RE.search(title):
        raise ValueError("题名含中文，请换一篇英文期刊论文。")


def fetch_doi(doi: str) -> dict[str, Any]:
    doi = normalize_doi(doi)
    if not doi:
        raise ValueError("DOI 为空")
    if doi in _CACHE:
        meta = _CACHE[doi]
    else:
        url = "https://api.crossref.org/works/" + urllib.parse.quote(doi)
        meta = work_to_meta(_get(url)["message"])
        _CACHE[doi] = meta
    require_usable_journal_article(meta)
    return meta


def search_works(query: str, *, rows: int = 8) -> list[dict[str, Any]]:
    query = (query or "").strip()
    if not query:
        return []
    params = urllib.parse.urlencode(
        {
            "query.bibliographic": query,
            "filter": "type:journal-article",
            "rows": max(rows * 2, 12),
        }
    )
    data = _get(f"https://api.crossref.org/works?{params}")
    out: list[dict[str, Any]] = []
    for item in data.get("message", {}).get("items", []):
        meta = work_to_meta(item)
        if not usable_journal_article(meta):
            continue
        out.append(meta)
        if len(out) >= rows:
            break
    return out


def apply_meta(entry: dict[str, Any], meta: dict[str, Any]) -> dict[str, Any]:
    require_usable_journal_article(meta)
    for key in (
        "doi",
        "title",
        "journal",
        "year",
        "volume",
        "issue",
        "pages",
        "articleNumber",
        "authors",
        "authorsFormatted",
        "recommended",
        "url",
        "publisher",
        "member",
        "type",
        "issn",
    ):
        value = meta.get(key)
        if value not in (None, ""):
            entry[key] = value
    return entry
