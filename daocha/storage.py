"""Self-contained project folders. A project can be copied to another computer."""

from __future__ import annotations

import json
import re
import shutil
from datetime import date
from pathlib import Path
from typing import Any

from daocha.config import projects_root
from daocha.extract import MarkerExtractError, build_registry, extract_markers
from daocha.manuscript import backfill_source_paragraphs

LEGACY_KEEP_DECISIONS = frozenset({"keep_engel_2008", "split_feock_inline"})

REGISTRY_NAME = "citation-registry.json"


def slugify(name: str) -> str:
    text = re.sub(r"[^\w\-]+", "-", name.strip(), flags=re.UNICODE)
    text = re.sub(r"-{2,}", "-", text).strip("-").lower()
    return text or "manuscript"


def unique_project_id(name: str) -> str:
    base = slugify(name)
    if not registry_path(base).exists():
        return base
    index = 2
    while registry_path(f"{base}-{index}").exists():
        index += 1
    return f"{base}-{index}"


def project_dir(project_id: str) -> Path:
    return projects_root() / project_id


def registry_path(project_id: str) -> Path:
    return project_dir(project_id) / REGISTRY_NAME


def list_projects() -> list[dict[str, Any]]:
    root = projects_root()
    if not root.exists():
        return []
    items: list[dict[str, Any]] = []
    for folder in sorted(root.iterdir()):
        path = folder / REGISTRY_NAME
        if not path.exists():
            continue
        try:
            registry = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        meta = registry.get("meta", {})
        items.append(
            {
                "id": folder.name,
                "title": meta.get("manuscriptTitle") or folder.name,
                "journal": meta.get("targetJournal") or "",
                "phase": meta.get("phaseLabel") or "",
                "updated": meta.get("lastUpdated") or "",
                "count": len(registry.get("citations", [])),
                "path": str(folder),
            }
        )
    return items


def load_project(project_id: str) -> dict[str, Any]:
    return json.loads(registry_path(project_id).read_text(encoding="utf-8"))


def save_project(project_id: str, registry: dict[str, Any]) -> Path:
    registry.setdefault("meta", {})
    registry["meta"]["lastUpdated"] = date.today().isoformat()
    registry["meta"]["registryEntryCount"] = len(registry.get("citations", []))
    path = registry_path(project_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def manuscript_path(project_id: str, registry: dict[str, Any] | None = None) -> Path:
    folder = project_dir(project_id)
    if registry is None:
        registry = load_project(project_id)
    name = registry.get("meta", {}).get("manuscriptFile")
    if name and (folder / name).exists():
        return folder / name
    for pattern in ("manuscript.pdf", "manuscript.docx", "manuscript.txt"):
        if (folder / pattern).exists():
            return folder / pattern
    matches = list(folder.glob("*.pdf")) + list(folder.glob("*.docx"))
    if matches:
        return matches[0]
    raise FileNotFoundError("项目里没有找到稿件文件")


def create_project(
    *,
    title: str,
    manuscript: Path | str,
    target_journal: str,
    project_id: str | None = None,
    max_same_source: int = 2,
    ban_mdpi: bool = True,
) -> dict[str, Any]:
    source = Path(manuscript).expanduser().resolve()
    if not source.exists():
        raise FileNotFoundError(source)
    suffix = source.suffix.lower()
    if suffix == ".doc":
        raise ValueError("不支持旧版 .doc，请另存为 .docx 或 PDF。")
    if suffix not in {".pdf", ".docx", ".txt", ".md"}:
        raise ValueError("请使用 PDF、.docx、.txt 或 .md。")
    markers = extract_markers(source)
    pid = unique_project_id(project_id or title or source.stem)
    dest = project_dir(pid)
    dest.mkdir(parents=True, exist_ok=True)
    copied = dest / f"manuscript{source.suffix.lower()}"
    shutil.copy2(source, copied)
    registry = build_registry(
        markers,
        project_id=pid,
        manuscript_name=copied.name,
        title=title or source.stem,
        target_journal=target_journal,
        max_same_source=max_same_source,
        ban_mdpi=ban_mdpi,
    )
    backfill_source_paragraphs(registry, copied)
    save_project(pid, registry)
    return registry


def import_legacy_registry(
    source_registry: Path | str,
    *,
    manuscript: Path | str | None = None,
    project_id: str | None = None,
) -> dict[str, Any]:
    src = Path(source_registry).expanduser().resolve()
    registry = json.loads(src.read_text(encoding="utf-8"))
    pid = unique_project_id(
        project_id or registry.get("meta", {}).get("projectId") or src.parent.name
    )
    dest = project_dir(pid)
    dest.mkdir(parents=True, exist_ok=True)
    for entry in registry.get("citations", []):
        if entry.get("userDecision") in LEGACY_KEEP_DECISIONS:
            entry["userDecision"] = "keep"
    manuscript_src = Path(manuscript) if manuscript else None
    if manuscript_src is None:
        old = registry.get("meta", {}).get("manuscriptPdf") or registry.get("meta", {}).get(
            "manuscriptFile"
        )
        if old and Path(old).exists():
            manuscript_src = Path(old)
    if manuscript_src and manuscript_src.exists():
        copied = dest / f"manuscript{manuscript_src.suffix.lower()}"
        shutil.copy2(manuscript_src, copied)
        registry.setdefault("meta", {})["manuscriptFile"] = copied.name
    registry["meta"]["projectId"] = pid
    registry["meta"].pop("manuscriptPdf", None)
    save_project(pid, registry)
    return registry


def write_export(project_id: str, filename: str, content: str) -> Path:
    path = project_dir(project_id) / filename
    path.write_text(content, encoding="utf-8")
    return path
