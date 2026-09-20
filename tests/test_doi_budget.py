from daocha.doi_budget import audit_doi_budget, check_doi_available


def _registry(dois: list[str]) -> dict:
    citations = []
    for i, doi in enumerate(dois, start=1):
        citations.append(
            {
                "id": f"C{i:03d}",
                "marker": f"【{i}】",
                "doi": doi,
                "userDecision": "keep",
                "status": "locked",
            }
        )
    return {
        "meta": {
            "pdfMarkerCount": len(citations),
            "constraints": {"maxSameSource": 2},
        },
        "citations": citations,
    }


def test_doi_budget_allows_two() -> None:
    registry = _registry(["10.1/a", "10.1/a", "10.1/b"])
    assert audit_doi_budget(registry)["ok"]


def test_doi_budget_rejects_third() -> None:
    registry = _registry(["10.1/a", "10.1/a", "10.1/a"])
    audit = audit_doi_budget(registry)
    assert not audit["ok"]
    assert audit["violations"][0]["id"] == "C003"


def test_check_doi_available_respects_order() -> None:
    registry = _registry(["10.1/a", "10.1/a"])
    allowed, prior = check_doi_available(registry, "10.1/a", entry_id="C003")
    assert not allowed
    assert prior == ["C001", "C002"]
