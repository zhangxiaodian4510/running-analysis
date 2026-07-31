"""导入页：上传 .fit/.tcx/.gpx，或生成/清理示例数据。"""
from __future__ import annotations

import asyncio

from nicegui import run, ui

from config import SUPPORTED_EXTS, UPLOAD_DIR
from core import db, seed
from ingest import loader
from ui.components import page_header, section_title


def render(nav):
    page_header("导入", "上传 .fit / .tcx / .gpx 文件，自动解析入库（同名不重复）")
    ui.label(f"当前库内活动：{db.activity_count()} 次").classes("muted")

    results: list[dict] = []
    counts = {"ok": 0, "skipped": 0, "error": 0}
    total_processed = [0]  # 总共处理了多少个文件（本次会话）- 用列表以便在闭包里修改
    # 全局锁：确保同一时间只处理一个文件（避免 SQLite 写锁冲突）
    import_lock = asyncio.Lock()
    current_file = [None]  # 用列表以便在闭包里修改

    @ui.refreshable
    def log_panel():
        if not results:
            ui.label("等待上传…").classes("muted")
            return
        ok = counts["ok"]
        sk = counts["skipped"]
        er = counts["error"]
        ui.label(f"本次：成功 {ok} · 跳过 {sk} · 失败 {er}").classes("section-title")
        with ui.column().style("gap:4px"):
            for r in results[-50:]:
                color = {"ok": "positive", "skipped": "warning", "error": "negative"}[r["status"]]
                icon = {"ok": "✓", "skipped": "→", "error": "✕"}[r["status"]]
                with ui.row().style("gap:6px;align-items:center"):
                    ui.label(icon).classes("muted")
                    ui.label(r["filename"]).style("font-weight:600;color:#c3c2b7")
                    ui.label(r["message"]).classes("muted")

    async def handle(e):
        # 串行处理：同一时间只处理一个文件，避免 SQLite 写锁冲突
        async with import_lock:
            # NiceGUI 3.x：UploadEventArguments 带 .file（on_upload 每文件触发一次）；
            # MultiUploadEventArguments 带 .files（on_multi_upload 一次触发）。
            file = getattr(e, "file", None)
            files = getattr(e, "files", None)
            items = [file] if file is not None else (list(files) if files else None)
            if not items:
                results.append({"status": "error", "filename": "?",
                                "message": f"无法读取上传内容：{type(e).__name__}"})
                counts["error"] += 1
                log_panel.refresh()
                progress_panel.refresh()
                return

            for fu in items:
                name = fu.name or "未命名"
                dest = UPLOAD_DIR / name
                try:
                    current_file[0] = name  # 更新"正在处理"显示
                    progress_panel.refresh()
                    await fu.save(dest)                              # 异步落盘（小/大文件通用）
                    res = await run.io_bound(loader.import_file, str(dest))  # 解析丢线程池，不卡 UI
                except Exception as ex:  # noqa: BLE001
                    results.append({"status": "error", "filename": name, "message": f"导入失败：{ex}"})
                    counts["error"] += 1
                    total_processed[0] += 1
                    log_panel.refresh()
                    progress_panel.refresh()
                    continue
                results.append(res)
                counts[res["status"]] += 1
                total_processed[0] += 1
                log_panel.refresh()
                progress_panel.refresh()
                ui.notify(f"{res['filename']}：{res['message']}",
                          type={"ok": "positive", "skipped": "warning", "error": "negative"}[res["status"]])
            current_file[0] = None  # 处理完清空
            progress_panel.refresh()

    ui.upload(label=f"选择文件（{', '.join('.' + e for e in SUPPORTED_EXTS)}）",
              multiple=True, auto_upload=True, on_upload=handle
              ).props('accept=".fit,.tcx,.gpx" color=primary').classes("w-full")

    # 导入进度显示
    @ui.refreshable
    def progress_panel():
        if total_processed[0] == 0:
            ui.label("等待上传…").classes("muted")
            return
        ok = counts["ok"]
        sk = counts["skipped"]
        er = counts["error"]
        ui.label(f"已处理 {total_processed[0]} 个文件（成功 {ok} / 跳过 {sk} / 失败 {er}）").classes("section-title")
        if current_file[0]:
            ui.label(f"正在处理：{current_file[0]}").classes("muted")

    section_title("导入进度")
    progress_panel()

    section_title("导入日志")
    log_panel()

    section_title("示例数据")
    with ui.row().style("gap:10px"):
        ui.button("生成示例数据", on_click=lambda: _do_seed(results, counts, log_panel))
        ui.button("清空示例数据", color="negative",
                  on_click=lambda: (seed.clear_seed(), ui.notify("已清空示例数据"), log_panel.refresh()))
    ui.label("示例数据仅用于预览界面效果；真实文件请用上方上传。").classes("muted")


def _do_seed(results, counts, log_panel):
    wrote = seed.run(force=False)
    if wrote:
        msg = "已生成示例数据（约 90 天跑步）"
        results.append({"status": "ok", "filename": "(seed)", "message": msg})
        counts["ok"] += 1
    else:
        msg = "库中已有数据，未重复生成"
        results.append({"status": "skipped", "filename": "(seed)", "message": msg})
        counts["skipped"] += 1
    ui.notify(msg)
    log_panel.refresh()
