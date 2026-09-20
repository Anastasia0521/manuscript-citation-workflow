"""Desktop UI for 倒插文献."""

from __future__ import annotations

import traceback
from pathlib import Path
from typing import Any

from nicegui import app, ui

from daocha.config import projects_root, set_projects_root, free_port
from daocha.crossref import apply_meta, fetch_doi, search_works
from daocha.doi_budget import (
    audit_doi_budget,
    check_doi_available,
    format_audit_report,
    normalize_doi,
    validate_one_to_one_markers,
)
from daocha.export import progress_stats, run_export
from daocha.journals import journal_choices
from daocha.mdpi import is_mdpi_record, mdpi_reason
from daocha.storage import (
    create_project,
    import_legacy_registry,
    list_projects,
    load_project,
    manuscript_path,
    project_dir,
    save_project,
    write_export,
)

DECISIONS = {
    "": "未决定",
    "keep": "保留",
    "delete_marker": "删除【】",
    "replace": "更换文献",
}


def pick_file(title: str, filetypes: list[tuple[str, str]]) -> str:
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    path = filedialog.askopenfilename(title=title, filetypes=filetypes)
    root.destroy()
    return path or ""


def pick_folder(title: str) -> str:
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    path = filedialog.askdirectory(title=title)
    root.destroy()
    return path or ""


def notify_error(exc: Exception) -> None:
    ui.notify(str(exc), type="negative", timeout=8000)


class Workspace:
    def __init__(self) -> None:
        self.project_id = ""
        self.registry: dict[str, Any] = {}
        self.selected_id = ""
        self.search_hits: list[dict[str, Any]] = []

    def open(self, project_id: str) -> None:
        self.project_id = project_id
        self.registry = load_project(project_id)
        citations = self.registry.get("citations") or []
        self.selected_id = citations[0]["id"] if citations else ""
        self.search_hits = []

    def selected(self) -> dict[str, Any] | None:
        for item in self.registry.get("citations", []):
            if item["id"] == self.selected_id:
                return item
        return None

    def persist(self) -> None:
        if self.project_id:
            save_project(self.project_id, self.registry)


workspace = Workspace()


def header_bar(title: str, *, show_home: bool = False) -> None:
    with ui.header().classes("items-center px-6 py-3").style(
        "background:#1f3a2e;color:white"
    ):
        ui.label(title).classes("text-lg font-medium")
        ui.space()
        if show_home:
            ui.button("全部稿件", on_click=lambda: ui.navigate.to("/")).props(
                "flat color=white"
            )


def render_home() -> None:
    header_bar("倒插文献")
    with ui.column().classes("w-full max-w-5xl mx-auto p-8 gap-6"):
        ui.label("把带【】的稿件做成可核对、可导出的引文稿。").classes(
            "text-slate-600 text-base"
        )
        with ui.row().classes("gap-3"):
            ui.button("新建稿件", on_click=open_new_dialog).props("unelevated")
            ui.button("导入旧项目", on_click=open_import_dialog).props("outline")
            ui.button("更改存放位置", on_click=change_root).props("flat")
        ui.label(f"项目存放在：{projects_root()}").classes("text-xs text-slate-500")

        projects = list_projects()
        if not projects:
            ui.label("还没有稿件。先选一份带【1】【2】的 PDF 或 Word。").classes(
                "text-slate-500"
            )
            return
        with ui.column().classes("w-full gap-3"):
            for item in projects:
                with ui.card().classes("w-full"):
                    with ui.row().classes("w-full items-center"):
                        with ui.column().classes("gap-0"):
                            ui.label(item["title"]).classes("text-base font-medium")
                            ui.label(
                                f"{item['journal']} · {item['count']} 处引文 · {item['phase']}"
                            ).classes("text-xs text-slate-500")
                        ui.space()
                        ui.button(
                            "打开",
                            on_click=lambda pid=item["id"]: ui.navigate.to(
                                f"/project/{pid}"
                            ),
                        ).props("flat")


def open_new_dialog() -> None:
    title = ui.input("稿件标题").classes("w-full")
    journal = ui.select(journal_choices(), value=journal_choices()[0], label="目标期刊")
    journal.classes("w-full")
    file_label = ui.input("稿件文件").classes("w-full")
    file_label.props("readonly")

    def browse() -> None:
        path = pick_file(
            "选择稿件",
            [("稿件", "*.pdf *.docx *.txt *.md"), ("PDF", "*.pdf"), ("Word", "*.docx")],
        )
        if path:
            file_label.value = path

    with ui.dialog() as dialog, ui.card().classes("w-[520px]"):
        ui.label("新建稿件").classes("text-lg")
        title
        journal
        with ui.row().classes("w-full items-end"):
            file_label.classes("flex-1")
            ui.button("浏览", on_click=browse).props("outline")
        with ui.row().classes("justify-end w-full"):
            ui.button("取消", on_click=dialog.close).props("flat")

            def create() -> None:
                try:
                    registry = create_project(
                        title=title.value or Path(file_label.value).stem,
                        manuscript=file_label.value,
                        target_journal=str(journal.value),
                    )
                    dialog.close()
                    ui.navigate.to(f"/project/{registry['meta']['projectId']}")
                except Exception as exc:
                    notify_error(exc)

            ui.button("创建并提取【】", on_click=create).props("unelevated")
    dialog.open()


def open_import_dialog() -> None:
    registry_label = ui.input("旧版 citation-registry.json").classes("w-full")
    manuscript_label = ui.input("稿件（可选，找不到原路径时再选）").classes("w-full")

    def browse_reg() -> None:
        path = pick_file("选择 registry", [("JSON", "*.json")])
        if path:
            registry_label.value = path

    def browse_ms() -> None:
        path = pick_file(
            "选择稿件",
            [("稿件", "*.pdf *.docx *.txt *.md"), ("PDF", "*.pdf"), ("Word", "*.docx")],
        )
        if path:
            manuscript_label.value = path

    with ui.dialog() as dialog, ui.card().classes("w-[560px]"):
        ui.label("导入旧的倒插文献项目").classes("text-lg")
        ui.label("会把 registry 和稿件复制进本机数据目录，不再依赖原来的盘符。").classes(
            "text-sm text-slate-500"
        )
        with ui.row().classes("w-full"):
            registry_label.classes("flex-1")
            ui.button("浏览", on_click=browse_reg).props("outline")
        with ui.row().classes("w-full"):
            manuscript_label.classes("flex-1")
            ui.button("浏览", on_click=browse_ms).props("outline")
        with ui.row().classes("justify-end w-full"):
            ui.button("取消", on_click=dialog.close).props("flat")

            def do_import() -> None:
                try:
                    registry = import_legacy_registry(
                        registry_label.value,
                        manuscript=manuscript_label.value or None,
                    )
                    dialog.close()
                    ui.navigate.to(f"/project/{registry['meta']['projectId']}")
                except Exception as exc:
                    notify_error(exc)

            ui.button("导入", on_click=do_import).props("unelevated")
    dialog.open()


def change_root() -> None:
    path = pick_folder("选择项目存放目录")
    if not path:
        return
    set_projects_root(path)
    ui.navigate.to("/")


def render_project(project_id: str) -> None:
    try:
        workspace.open(project_id)
    except Exception as exc:
        header_bar("倒插文献", show_home=True)
        ui.label(str(exc)).classes("p-8")
        return

    registry = workspace.registry
    meta = registry.get("meta", {})
    stats = progress_stats(registry)
    header_bar(meta.get("manuscriptTitle") or project_id, show_home=True)

    with ui.column().classes("w-full p-6 gap-4"):
        with ui.row().classes("gap-6 text-sm text-slate-600"):
            ui.label(f"期刊：{meta.get('targetJournal')}")
            ui.label(f"引文位 {stats['total']}")
            ui.label(f"已填 DOI {stats['filled']}")
            ui.label(f"已锁定 {stats['locked']}")
            ui.label(f"存放：{project_dir(project_id)}")

        with ui.tabs().classes("w-full") as tabs:
            tab_review = ui.tab("核查")
            tab_export = ui.tab("导出")
        with ui.tab_panels(tabs, value=tab_review).classes("w-full"):
            with ui.tab_panel(tab_review):
                render_review()
            with ui.tab_panel(tab_export):
                render_export()


@ui.refreshable
def render_review() -> None:
    citations = workspace.registry.get("citations", [])
    with ui.row().classes("w-full gap-4 items-start"):
        with ui.column().classes("w-[42%] gap-2"):
            for item in citations:
                selected = item["id"] == workspace.selected_id
                bg = "background:#e8f3ec" if selected else ""
                with ui.card().classes("w-full cursor-pointer").style(bg).on(
                    "click",
                    lambda cid=item["id"]: select_entry(cid),
                ):
                    with ui.row().classes("w-full items-center"):
                        ui.label(f"{item['id']} {item.get('marker')}").classes(
                            "font-medium"
                        )
                        ui.space()
                        status = item.get("status") or "pending"
                        color = "green" if status == "locked" else "grey"
                        ui.badge(status, color=color)
                    ui.label(
                        (item.get("recommended") or item.get("title") or "尚未填写文献")[:80]
                    ).classes("text-xs text-slate-600")

        with ui.column().classes("flex-1 gap-3"):
            entry = workspace.selected()
            if not entry:
                ui.label("左侧选择一条引文位。")
                return
            ui.label(f"{entry['id']}  {entry.get('marker')}").classes("text-xl")
            ui.label(entry.get("sourceParagraph") or entry.get("excerpt") or "").classes(
                "text-sm leading-7 bg-slate-50 p-3 rounded"
            )
            claim = ui.textarea("这句话要支撑的主张").classes("w-full")
            claim.value = entry.get("claim") or ""
            claim.on("blur", lambda e=entry, box=claim: save_field(e, "claim", box.value))

            with ui.row().classes("w-full items-end"):
                doi = ui.input("DOI").classes("flex-1")
                doi.value = entry.get("doi") or ""

                def apply_doi() -> None:
                    try:
                        bind_doi(entry, doi.value)
                        render_review.refresh()
                    except Exception as exc:
                        notify_error(exc)

                ui.button("用 DOI 拉取", on_click=apply_doi).props("unelevated")

            ui.label(
                f"{entry.get('recommended') or ''}  {entry.get('title') or ''}"
            ).classes("text-sm")
            if entry.get("url"):
                ui.link("打开 DOI 核对", entry["url"], new_tab=True)

            query = ui.input("按主张或关键词检索 Crossref").classes("w-full")
            query.value = entry.get("claim") or ""

            def do_search() -> None:
                try:
                    workspace.search_hits = search_works(query.value)
                    if not workspace.search_hits:
                        ui.notify("没有可用的英文期刊论文（MDPI 已过滤）。请改英文关键词，或直接填 DOI。")
                    render_review.refresh()
                except Exception as exc:
                    notify_error(exc)

            ui.button("检索候选文献", on_click=do_search).props("outline")
            for hit in workspace.search_hits:
                with ui.card().classes("w-full"):
                    ui.label(hit.get("title") or "").classes("font-medium")
                    ui.label(
                        f"{hit.get('recommended')} · {hit.get('journal')} · {hit.get('doi')}"
                    ).classes("text-xs text-slate-500")

                    def use_hit(meta=hit, current=entry) -> None:
                        try:
                            bind_meta(current, meta)
                            render_review.refresh()
                        except Exception as exc:
                            notify_error(exc)

                    ui.button("采用这篇", on_click=use_hit).props("flat")

            decision = ui.select(DECISIONS, label="决定").classes("w-64")
            decision.value = entry.get("userDecision") or ""
            note = ui.input("备注").classes("w-full")
            note.value = entry.get("userNote") or ""

            def lock_keep() -> None:
                chosen = decision.value or "keep"
                if chosen == "replace":
                    notify_error(
                        ValueError("「更换文献」表示本条未完成，请改成保留或删除【】后再锁定。")
                    )
                    return
                if chosen == "keep" and not normalize_doi(entry.get("doi")):
                    notify_error(ValueError("没有 DOI，请换一篇英文期刊论文后再锁定。"))
                    return
                save_field(entry, "userDecision", chosen)
                save_field(entry, "userNote", note.value)
                save_field(entry, "status", "locked")
                workspace.persist()
                ui.notify("已锁定")
                render_review.refresh()

            def just_save() -> None:
                save_field(entry, "userDecision", decision.value or "")
                save_field(entry, "userNote", note.value)
                workspace.persist()
                ui.notify("已保存")
                render_review.refresh()

            with ui.row():
                ui.button("保存", on_click=just_save).props("outline")
                ui.button("锁定本条", on_click=lock_keep).props("unelevated")


def select_entry(cid: str) -> None:
    workspace.selected_id = cid
    workspace.search_hits = []
    render_review.refresh()


def save_field(entry: dict[str, Any], key: str, value: Any) -> None:
    entry[key] = value
    workspace.persist()


def bind_doi(entry: dict[str, Any], doi: str) -> None:
    meta = fetch_doi(doi)
    bind_meta(entry, meta)


def bind_meta(entry: dict[str, Any], meta: dict[str, Any]) -> None:
    doi = normalize_doi(meta.get("doi"))
    allowed, prior = check_doi_available(
        workspace.registry, doi, entry_id=entry.get("id")
    )
    if not allowed:
        raise ValueError(f"同一 DOI 已用过 {len(prior)} 次：{', '.join(prior)}")
    if is_mdpi_record(meta):
        raise ValueError(f"禁止 MDPI：{mdpi_reason(meta)}")
    if not doi:
        raise ValueError("没有 DOI，请换一篇能核对的英文期刊论文。")
    apply_meta(entry, meta)
    entry["userDecision"] = entry.get("userDecision") or "keep"
    workspace.persist()
    ui.notify("已写入文献信息")


@ui.refreshable
def render_export() -> None:
    log = ui.textarea("检查与导出结果").classes("w-full")
    log.props("readonly rows=18")

    def validate() -> None:
        try:
            markers = validate_one_to_one_markers(workspace.registry)
            audit = audit_doi_budget(workspace.registry)
            log.value = format_audit_report(audit) + "\n\n" + str(markers)
        except Exception as exc:
            log.value = str(exc)

    def do_export() -> None:
        try:
            ms = manuscript_path(workspace.project_id, workspace.registry)
            phase3, phase4 = run_export(
                workspace.registry, manuscript_path=ms, require_locked=True
            )
            p3 = write_export(workspace.project_id, "phase3-cited-paragraphs.md", phase3)
            p4 = write_export(workspace.project_id, "phase4-references.md", phase4)
            workspace.persist()
            log.value = f"已写出：\n{p3}\n{p4}"
            ui.notify("导出完成")
        except Exception as exc:
            log.value = f"{exc}\n\n{traceback.format_exc()}"
            notify_error(exc)

    def lock_all_filled() -> None:
        for item in workspace.registry.get("citations", []):
            if item.get("userDecision") == "replace":
                continue
            if item.get("userDecision") == "delete_marker":
                item["status"] = "locked"
                continue
            if normalize_doi(item.get("doi")):
                item["status"] = "locked"
                if not item.get("userDecision"):
                    item["userDecision"] = "keep"
        workspace.persist()
        ui.notify("已锁定所有已填条目")
        render_export.refresh()

    with ui.row():
        ui.button("检查 DOI 预算", on_click=validate).props("outline")
        ui.button("锁定已填条目", on_click=lock_all_filled).props("outline")
        ui.button("导出正文和参考文献", on_click=do_export).props("unelevated")
    ui.label(
        "导出文件写在本项目文件夹里，整夹拷走即可换电脑继续。"
    ).classes("text-sm text-slate-500")


def setup_pages() -> None:
    @ui.page("/")
    def home_page() -> None:
        render_home()

    @ui.page("/project/{project_id}")
    def project_page(project_id: str) -> None:
        render_project(project_id)


def run_app(*, browser: bool = False) -> None:
    setup_pages()
    port = free_port()
    if browser:
        ui.run(title="倒插文献", reload=False, port=port, show=True)
        return
    app.native.window_args["title"] = "倒插文献"
    ui.run(
        title="倒插文献",
        native=True,
        reload=False,
        port=port,
        window_size=(1280, 840),
        favicon="📚",
    )
