from daocha.mdpi import is_mdpi_record, mdpi_reason
from daocha.storage import LEGACY_KEEP_DECISIONS


def test_mdpi_prefix() -> None:
    meta = {"doi": "10.3390/su13116120", "journal": "Sustainability", "publisher": "MDPI"}
    assert is_mdpi_record(meta)
    assert "10.3390" in mdpi_reason(meta) or "MDPI" in mdpi_reason(meta)


def test_mdpi_member() -> None:
    assert is_mdpi_record({"doi": "10.1000/xyz", "member": "1968", "journal": "Whatever"})


def test_mdpi_journal_name_backup() -> None:
    assert is_mdpi_record({"doi": "10.1000/xyz", "journal": "IJERPH"})


def test_non_mdpi_elsevier() -> None:
    assert not is_mdpi_record(
        {
            "doi": "10.1016/j.jenvman.2020.111840",
            "journal": "Journal of Environmental Management",
            "publisher": "Elsevier",
            "member": "78",
        }
    )


def test_legacy_specials_are_mapped_names() -> None:
    assert "keep_engel_2008" in LEGACY_KEEP_DECISIONS
    assert "split_feock_inline" in LEGACY_KEEP_DECISIONS
