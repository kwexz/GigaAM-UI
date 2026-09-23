"""First-run setup page: what will be downloaded, where, big button, progress."""
from pathlib import Path

from PySide6.QtCore import QThread, Qt, Signal, Slot
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from giga_transcribe.installer import setup
from giga_transcribe.installer.state import data_dir
from .setup_worker import SetupWorker


class SetupPage(QWidget):
    done = Signal()  # everything verified, main window may open
    retry_requested = Signal()  # manifest fetch failed, rebuild the page

    def __init__(self, manifest, target=None, fetch_error: str | None = None):
        super().__init__()
        self._manifest = manifest
        self._fetch_error = fetch_error
        self._target = Path(target or data_dir())
        self._thread = None
        self._received = {}
        self.setWindowTitle("Giga Transcribe — установка компонентов")

        root = QVBoxLayout()
        title = QLabel("Первый запуск: нужно скачать компоненты"
                       if manifest.components else "Нет компонентов для установки")
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        root.addWidget(title)

        self.rows = {}
        for comp in manifest.components:
            box = QVBoxLayout()
            head = QHBoxLayout()
            name = QLabel(f"<b>{comp.title}</b> — {setup.format_bytes(comp.size)}")
            head.addWidget(name, 1)
            state = QLabel("")
            head.addWidget(state)
            box.addLayout(head)
            desc = QLabel(comp.description)
            desc.setStyleSheet("color: #888;")
            desc.setWordWrap(True)
            box.addWidget(desc)
            bar = QProgressBar()
            bar.setVisible(False)
            box.addWidget(bar)
            root.addLayout(box)
            self.rows[comp.id] = (state, bar)

        self.total_lbl = QLabel("")
        root.addWidget(self.total_lbl)

        path_row = QHBoxLayout()
        path_row.addWidget(QLabel("Папка установки:"))
        self.path_edit = QLabel(str(self._target))
        self.path_edit.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        path_row.addWidget(self.path_edit, 1)
        change = QPushButton("Изменить…")
        change.clicked.connect(self._on_change_path)
        path_row.addWidget(change)
        root.addLayout(path_row)

        self.total_bar = QProgressBar()
        self.total_bar.setVisible(False)
        root.addWidget(self.total_bar)

        btn_row = QHBoxLayout()
        self.go_btn = QPushButton()
        self.go_btn.clicked.connect(self._on_start)
        self.cancel_btn = QPushButton("Отменить")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._on_cancel)
        btn_row.addWidget(self.go_btn, 1)
        btn_row.addWidget(self.cancel_btn)
        root.addLayout(btn_row)

        self.setLayout(root)
        self.refresh()

    def refresh(self):
        if self._fetch_error is not None:
            self.total_lbl.setText(f"Не удалось загрузить список "
                                   f"компонентов:\n{self._fetch_error}")
            self.go_btn.setText("Повторить")
            self.go_btn.setEnabled(True)
            return
        missing = setup.missing(self._manifest, self._target)
        for comp in self._manifest.components:
            state, _ = self.rows[comp.id]
            state.setText("Готов" if comp not in missing else "Нужно скачать")
        if missing:
            total = setup.format_bytes(setup.total_bytes(missing))
            self.total_lbl.setText(f"Всего к загрузке: ≈ {total}")
            self.go_btn.setText(f"Скачать и установить (≈ {total})")
            self.go_btn.setEnabled(True)
        else:
            self.total_lbl.setText("Все компоненты на месте.")
            self.go_btn.setText("Продолжить")
            self.go_btn.setEnabled(True)
        self.path_edit.setText(str(self._target))

    def _on_change_path(self):
        chosen = QFileDialog.getExistingDirectory(self, "Папка установки",
                                                  str(self._target))
        if chosen:
            self._target = Path(chosen)
            self._received.clear()
            self.refresh()

    def _on_start(self):
        if self._fetch_error is not None:
            self.retry_requested.emit()
            return
        if not setup.missing(self._manifest, self._target):
            self.done.emit()
            return
        self.go_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.total_bar.setVisible(True)
        missing = setup.missing(self._manifest, self._target)
        self._total_bytes = setup.total_bytes(missing) or 1
        for comp in missing:
            _, bar = self.rows[comp.id]
            bar.setVisible(True)
            bar.setRange(0, comp.size or 1)
            bar.setValue(0)

        self._thread = QThread(self)
        self._worker = SetupWorker(self._manifest, self._target)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.component.connect(self._on_component)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.finished.connect(self._thread.quit)
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

    def _on_cancel(self):
        self.cancel_btn.setEnabled(False)
        self._worker.cancel()

    @Slot(object, int, int)
    def _on_component(self, comp, i, n):
        state, _ = self.rows[comp.id]
        state.setText(f"Загрузка {i + 1}/{n}…")

    @Slot(object, int, int)
    def _on_progress(self, comp, received, total):
        _, bar = self.rows[comp.id]
        bar.setRange(0, total or comp.size or 1)
        bar.setValue(received)
        self._received[comp.id] = received
        done = sum(self._received.values())
        self.total_bar.setRange(0, self._total_bytes)
        self.total_bar.setValue(min(done, self._total_bytes))

    @Slot(object)
    def _on_finished(self, result):
        self.cancel_btn.setEnabled(False)
        self.total_bar.setVisible(False)
        if result.status == "done":
            self.refresh()
            if not setup.missing(self._manifest, self._target):
                self.done.emit()
        elif result.status == "cancelled":
            self.refresh()
            self.go_btn.setEnabled(True)
        else:
            self.go_btn.setEnabled(True)
            self.total_lbl.setText(f"Ошибка загрузки: {result.error}")
