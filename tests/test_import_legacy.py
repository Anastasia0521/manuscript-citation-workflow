import json
from pathlib import Path

from citeverify.storage import import_legacy_registry


def test_import_maps_legacy_decisions(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("citeverify.storage.projects_root", lambda: tmp_path)
    src = tmp_path / "old.json"
    src.write_text(
        json.dumps(
            {
                "meta": {"projectId": "legacy-demo", "pdfMarkerCount": 2},
                "citations": [
                    {
                        "id": "C001",
                        "marker": "【1】",
                        "userDecision": "split_feock_inline",
                        "doi": "10.1111/psj.12023",
                    },
                    {
                        "id": "C002",
                        "marker": "【2】",
                        "userDecision": "keep_engel_2008",
                        "doi": "10.1016/j.ecolecon.2008.03.011",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    registry = import_legacy_registry(src, project_id="legacy-demo")
    assert {c["userDecision"] for c in registry["citations"]} == {"keep"}
    assert (tmp_path / "legacy-demo" / "citation-registry.json").exists()
