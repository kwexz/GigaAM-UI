"""GigaTranscribe stub: ~20 MB window that fetches everything else.

Reuses installer/ modules (stdlib-only by design). Threading: the worker
thread pushes events into a queue; the UI polls it via after().
"""
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from giga_transcribe.installer import builtin, setup
from giga_transcribe.installer.engine import find_app, find_engine
from giga_transcribe.installer.state import data_dir


def pick_launch_target(target=None) -> str | None:
    """Full UI first, engine console as fallback, else None."""
    return find_app(target) or find_engine(target)


class StubApp:
    def __init__(self, root, manifest, fetch_error=None, target=None):
        self.root = root
        self.root.title("Giga Transcribe — установка")
        self.root.geometry("520x560")
        self.manifest = manifest
        self.target = target or data_dir()
        self.events: queue.Queue = queue.Queue()
        self.row_widgets = {}
        self.received = {}
        self.total_bytes = 1

        ttk.Label(root, text="Установка Giga Transcribe",
                  font=("", 14, "bold")).pack(pady=8, anchor="w", padx=10)

        if fetch_error is not None:
            ttk.Label(root, text=f"Не удалось загрузить список "
                                 f"компонентов:\n{fetch_error}",
                      foreground="red", wraplength=480).pack(
                          padx=10, anchor="w")
            ttk.Button(root, text="Повторить",
                       command=self._retry).pack(pady=8)
            self.list_frame = None
            return

        self.list_frame = ttk.Frame(root)
        self.list_frame.pack(fill="both", expand=True, padx=10)
        for comp in manifest.components:
            row = ttk.Frame(self.list_frame)
            row.pack(fill="x", pady=2)
            ttk.Label(row, text=f"{comp.title} — "
                                f"{setup.format_bytes(comp.size)}",
                      font=("", 10, "bold")).pack(anchor="w")
            ttk.Label(row, text=comp.description, wraplength=480,
                      foreground="gray").pack(anchor="w")
            bar = ttk.Progressbar(row, maximum=comp.size or 1)
            bar.pack(fill="x")
            self.row_widgets[comp.id] = bar

        missing = setup.missing(manifest, self.target)
        self.total_bytes = setup.total_bytes(missing) or 1
        self.total_lbl = ttk.Label(
            root, text=f"Всего к загрузке: ≈ "
                       f"{setup.format_bytes(self.total_bytes)}")
        self.total_lbl.pack(pady=4, anchor="w", padx=10)

        path_row = ttk.Frame(root)
        path_row.pack(fill="x", padx=10)
        ttk.Label(path_row, text="Папка:").pack(side="left")
        self.path_var = tk.StringVar(value=str(self.target))
        ttk.Entry(path_row, textvariable=self.path_var).pack(
            side="left", fill="x", expand=True, padx=4)
        ttk.Button(path_row, text="…", width=3,
                   command=self._change_path).pack(side="left")

        self.total_bar = ttk.Progressbar(root, maximum=self.total_bytes)
        self.total_bar.pack(fill="x", padx=10, pady=4)

        btn_row = ttk.Frame(root)
        btn_row.pack(pady=8)
        self.go_btn = ttk.Button(btn_row, text="Скачать и установить",
                                 command=self._start)
        self.go_btn.pack(side="left", padx=4)
        self.cancel_btn = ttk.Button(btn_row, text="Отменить",
                                     command=self._cancel, state="disabled")
        self.cancel_btn.pack(side="left", padx=4)
        self._cancel = threading.Event()
        self.root.after(100, self._poll)

    def _retry(self):
        self.root.destroy()
        main()

    def _change_path(self):
        from pathlib import Path
        chosen = filedialog.askdirectory(initialdir=self.path_var.get())
        if chosen:
            self.path_var.set(chosen)
            self.target = Path(chosen)

    def _start(self):
        from pathlib import Path
        self.target = Path(self.path_var.get())
        self.go_btn.config(state="disabled")
        self.cancel_btn.config(state="normal")
        self._cancel.clear()
        self.received.clear()
        threading.Thread(target=self._work, daemon=True).start()

    def _cancel(self):
        self._cancel.set()
        self.cancel_btn.config(state="disabled")

    def _work(self):
        try:
            setup.ensure(self.manifest, self.target,
                         on_component=lambda c, i, n: self.events.put(
                             ("comp", c.id, i, n)),
                         on_progress=lambda c, r, t: self.events.put(
                             ("prog", c.id, r, t)),
                         should_cancel=self._cancel.is_set)
        except Exception as e:  # noqa: BLE001 — shown in UI verbatim
            self.events.put(("done", "error", str(e)))
        else:
            self.events.put(("done", "ok", ""))

    def _poll(self):
        try:
            while True:
                ev = self.events.get_nowait()
                self._apply(ev)
        except queue.Empty:
            pass
        self.root.after(100, self._poll)

    def _apply(self, ev):
        kind = ev[0]
        if kind == "prog":
            _, cid, received, total = ev
            bar = self.row_widgets.get(cid)
            if bar is not None:
                bar["maximum"] = total or 1
                bar["value"] = received
            self.received[cid] = received
            done = min(sum(self.received.values()), self.total_bytes)
            self.total_bar["value"] = done
            self.total_lbl.config(
                text=f"Загружено ≈ {setup.format_bytes(done)} из "
                     f"{setup.format_bytes(self.total_bytes)}")
        elif kind == "done":
            _, status, message = ev
            self.cancel_btn.config(state="disabled")
            if status == "ok":
                self.total_lbl.config(text="Готово. Можно запускать.")
                self.go_btn.config(text="Запустить", state="normal",
                                   command=self._launch)
            else:
                self.go_btn.config(state="normal")
                messagebox.showerror("Ошибка загрузки", message)

    def _launch(self):
        exe = pick_launch_target(self.target)
        if exe is None:
            messagebox.showerror("Нет приложения",
                                 "Не найден установленный компонент.")
            return
        subprocess.Popen([exe])
        self.root.destroy()


def main(argv=None) -> int:
    manifest, err = builtin.default_manifest()
    root = tk.Tk()
    StubApp(root, manifest, fetch_error=err)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
