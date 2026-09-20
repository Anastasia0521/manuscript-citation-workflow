import pytest

from daocha.citation_format import (
    format_short_cite,
    is_reference_entry,
    merge_adjacent_citation_groups,
)
from daocha.crossref import require_usable_journal_article, usable_journal_article
from daocha.doi_budget import assert_registry_valid
from daocha.reference_format import format_reference_line_gbt7714, format_reference_line_jem


def test_merge_adjacent_cites() -> None:
    text = "(Hou et al., 2021)(Hu et al., 2019)"
    assert merge_adjacent_citation_groups(text, "(", ")") == "(Hou et al., 2021; Hu et al., 2019)"


def test_short_cite() -> None:
    entry = {"id": "C001", "recommended": "Hou et al., 2021", "year": 2021}
    assert format_short_cite(entry, open_p="（", close_p="）") == "（Hou et al., 2021）"


def test_jem_and_gbt_lines() -> None:
    entry = {
        "authorsFormatted": "Hou, L., Xia, F.",
        "authors": [{"family": "Hou", "given": "Lingling"}, {"family": "Xia", "given": "Fan"}],
        "year": 2021,
        "title": "Grassland ecological compensation policy in China",
        "journal": "Nature Communications",
        "volume": "12",
        "articleNumber": "4683",
        "doi": "10.1038/s41467-021-24942-8",
    }
    jem = format_reference_line_jem(entry)
    assert "Nat. Commun." in jem
    assert "https://doi.org/10.1038/s41467-021-24942-8" in jem
    gbt = format_reference_line_gbt7714(entry)
    assert "[J]" in gbt
    assert "Hou L" in gbt or "Hou" in gbt


def test_replace_with_doi_is_not_a_reference() -> None:
    entry = {"userDecision": "replace", "doi": "10.1/a"}
    assert not is_reference_entry(entry)


def test_export_rejects_unlocked_replace() -> None:
    registry = {
        "meta": {"pdfMarkerCount": 1, "constraints": {"maxSameSource": 2}},
        "citations": [
            {
                "id": "C001",
                "marker": "【1】",
                "doi": "10.1/a",
                "userDecision": "replace",
                "status": "locked",
            }
        ],
    }
    with pytest.raises(ValueError, match="尚未完成"):
        assert_registry_valid(registry, require_locked=True)


def test_usable_journal_article_filters() -> None:
    ok = {
        "doi": "10.1016/j.jenvman.2020.111840",
        "title": "An English journal article",
        "type": "journal-article",
        "publisher": "Elsevier",
        "member": "78",
    }
    require_usable_journal_article(ok)
    assert usable_journal_article(ok)
    assert not usable_journal_article({**ok, "type": "book"})
    assert not usable_journal_article({**ok, "title": "草原生态补偿政策研究"})
    assert not usable_journal_article({**ok, "doi": ""})
    assert not usable_journal_article({**ok, "doi": "10.3390/su13116120", "publisher": "MDPI"})
