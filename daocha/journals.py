"""Journal style presets. Add new styles here instead of hardcoding one paper."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class JournalStyle:
    id: str
    label: str
    paren: str  # ascii | fullwidth
    reference_style: str  # jem | gbt7714
    notes: str


STYLES: dict[str, JournalStyle] = {
    "jem": JournalStyle(
        id="jem",
        label="Journal of Environmental Management",
        paren="ascii",
        reference_style="jem",
        notes="作者—年份，期刊名缩写，卷(期), 页码，DOI",
    ),
    "acta-ecologica": JournalStyle(
        id="acta-ecologica",
        label="生态学报",
        paren="fullwidth",
        reference_style="gbt7714",
        notes="GB/T 7714 著者-出版年制，中文括号",
    ),
    "gbt7714": JournalStyle(
        id="gbt7714",
        label="GB/T 7714 著者-出版年制",
        paren="fullwidth",
        reference_style="gbt7714",
        notes="通用中文学位论文/学报体例",
    ),
    "author-year": JournalStyle(
        id="author-year",
        label="通用英文作者—年份",
        paren="ascii",
        reference_style="jem",
        notes="英文括号 (Author, Year)",
    ),
}


def style_for_journal(name: str | None) -> JournalStyle:
    text = (name or "").strip()
    if not text:
        return STYLES["author-year"]
    for style in STYLES.values():
        if text == style.label or text == style.id:
            return style
    if any(token in text for token in ("学报", "期刊", "研究")):
        return STYLES["gbt7714"]
    return STYLES["author-year"]


def journal_choices() -> list[str]:
    return [style.label for style in STYLES.values()]
