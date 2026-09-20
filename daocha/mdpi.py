"""Hard ban on MDPI. Publisher, Crossref member, DOI prefixes, and journal names."""

from __future__ import annotations

import re
from typing import Any

# Crossref member 1968 = MDPI AG (verified)
MDPI_MEMBER_IDS = frozenset({"1968"})

# Prefixes registered to MDPI AG on Crossref
MDPI_PREFIXES = frozenset(
    {
        "10.3390",
        "10.1989",
        "10.20944",
        "10.32545",
        "10.35995",
    }
)

# Backup when publisher/prefix/member is missing from a record
MDPI_JOURNAL_NAMES = frozenset(
    name.casefold()
    for name in (
        "Sustainability",
        "International Journal of Environmental Research and Public Health",
        "IJERPH",
        "Sensors",
        "Applied Sciences",
        "Energies",
        "Materials",
        "Molecules",
        "International Journal of Molecular Sciences",
        "IJMS",
        "Water",
        "Forests",
        "Land",
        "Agriculture",
        "Animals",
        "Plants",
        "Atmosphere",
        "Remote Sensing",
        "ISPRS International Journal of Geo-Information",
        "International Journal of Geo-Information",
        "Electronics",
        "Entropy",
        "Catalysts",
        "Polymers",
        "Nanomaterials",
        "Coatings",
        "Metals",
        "Minerals",
        "Processes",
        "Foods",
        "Nutrients",
        "Healthcare",
        "Medicina",
        "Biology",
        "Life",
        "Genes",
        "Cells",
        "Cancers",
        "Vaccines",
        "Viruses",
        "Pathogens",
        "Microorganisms",
        "Antibiotics",
        "Pharmaceutics",
        "Marine Drugs",
        "Toxins",
        "Diversity",
        "Journal of Marine Science and Engineering",
        "Journal of Risk and Financial Management",
        "Administrative Sciences",
        "Economies",
        "Education Sciences",
        "Social Sciences",
        "Urban Science",
        "Buildings",
        "Geosciences",
        "Climate",
        "Environments",
        "Int. J. Environ. Res. Public Health",
        "Int. J. Mol. Sci.",
        "Int. J. Environ. Res. Public Health",
    )
)

_PUBLISHER_RE = re.compile(r"\bmdpi\b", re.I)


def doi_prefix(doi: str | None) -> str:
    text = (doi or "").strip().lower()
    text = re.sub(r"^https?://(dx\.)?doi\.org/", "", text)
    parts = text.split("/")
    if len(parts) < 2:
        return ""
    return parts[0]


def is_mdpi_record(meta: dict[str, Any] | None) -> bool:
    if not meta:
        return False
    member = str(meta.get("member") or "").strip()
    if member in MDPI_MEMBER_IDS:
        return True
    publisher = str(meta.get("publisher") or "")
    if _PUBLISHER_RE.search(publisher):
        return True
    prefix = doi_prefix(meta.get("doi"))
    if prefix in MDPI_PREFIXES:
        return True
    journal = str(meta.get("journal") or meta.get("container-title") or "").strip()
    return journal.casefold() in MDPI_JOURNAL_NAMES


def mdpi_reason(meta: dict[str, Any]) -> str:
    member = str(meta.get("member") or "").strip()
    if member in MDPI_MEMBER_IDS:
        return "Crossref member 1968 (MDPI AG)"
    publisher = str(meta.get("publisher") or "")
    if _PUBLISHER_RE.search(publisher):
        return f"publisher={publisher}"
    prefix = doi_prefix(meta.get("doi"))
    if prefix in MDPI_PREFIXES:
        return f"DOI prefix {prefix}"
    journal = str(meta.get("journal") or "").strip()
    if journal.casefold() in MDPI_JOURNAL_NAMES:
        return f"journal={journal}"
    return "MDPI"
