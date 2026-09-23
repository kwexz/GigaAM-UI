"""Main window: one screen, two states (idle / running)."""
import os
import time

from PySide6.QtCore import QThread, QTimer, Qt, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from giga_transcribe.core import devices, formats, models
from giga_transcribe.core.events import Job, default_output
from giga_transcribe.desktop.worker import TranscribeWorker
from giga_transcribe.installer.engine import find_engine

AUDIO_FILTER = "Audio/video (*.wav *.mp3 *.flac *.ogg *.m4a *.mp4 *.mkv *.avi *.mov);;All (*)"


def _fmt_ts(seconds: float) -> str:
    m, s = divmod(max(0.0, seconds), 60)
    return f"{int(m):02}:{s:04.1f}"


def _device_label(dev) -> str:
    if dev.kind == "cpu":
        return f"CPU ({dev.cores} потоков)" if dev.cores else "CPU"
    if dev.kind == "cuda":
        gb = f", {dev.total_memory / 1e9:.0f} ГБ" if dev.total_memory else ""
        return f"GPU — {dev.name or 'CUDA'}{gb}"
    return "GPU Apple (Metal)"


class MainWindow(QMainWindow):
    need_setup = Signal()  # engine missing, user wants the setup page

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Giga Transcribe")
        self.resize(720, 560)
        self._job_path = ""
        self._thread = None
        self._worker = None
        self._started = 0.0

        root = QVBoxLayout()

        self.drop = QLabel("Перетащите аудио/видео сюда или выберите файл")
        self.drop.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop.setMinimumHeight(90)
        self.drop.setStyleSheet("QLabel { border: 2px dashed #888; border-radius: 8px; }")
        self.drop.setAcceptDrops(True)
        self.drop.dragEnterEvent = self._on_drag_enter
        self.drop.dropEvent = self._on_drop
        root.addWidget(self.drop)

        file_row = QHBoxLayout()
        self.pick_btn = QPushButton("Выбрать файл…")
        self.pick_btn.clicked.connect(self._on_pick)
        self.file_lbl = QLabel("Файл не выбран")
        self.file_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        file_row.addWidget(self.pick_btn)
        file_row.addWidget(self.file_lbl, 1)
        root.addLayout(file_row)

        opts = QHBoxLayout()
        self.model_cb = QComboBox()
        for mid, info in models.CATALOG.items():
            self.model_cb.addItem(info.title, mid)
        self.device_cb = QComboBox()
        for dev in devices.describe():
            self.device_cb.addItem(_device_label(dev), dev.id)
        self.format_cb = QComboBox()
        for fmt in sorted(formats.WRITERS):
            self.format_cb.addItem(fmt, fmt)
        for lbl, cb in (("Модель:", self.model_cb), ("Устройство:", self.device_cb),
                        ("Формат:", self.format_cb)):
            opts.addWidget(QLabel(lbl))
            opts.addWidget(cb)
        root.addLayout(opts)

        self.out_lbl = QLabel("")
        self.out_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        root.addWidget(self.out_lbl)

        btn_row = QHBoxLayout()
        self.go_btn = QPushButton("Распознать")
        self.go_btn.setDefault(True)
        self.go_btn.clicked.connect(self._on_start)
        self.cancel_btn = QPushButton("Отменить")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._on_cancel)
        btn_row.addWidget(self.go_btn)
        btn_row.addWidget(self.cancel_btn)
        root.addLayout(btn_row)

        self.status_lbl = QLabel("Готов.")
        root.addWidget(self.status_lbl)
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        root.addWidget(self.progress)

        self.live = QTextEdit()
        self.live.setReadOnly(True)
        self.live.setPlaceholderText("Здесь появится распознанный текст…")
        root.addWidget(self.live, 1)

        done_row = QHBoxLayout()
        self.open_btn = QPushButton("Открыть файл")
        self.open_btn.setEnabled(False)
        self.open_btn.clicked.connect(self._on_open)
        self.show_btn = QPushButton("Показать в папке")
        self.show_btn.setEnabled(False)
        self.show_btn.clicked.connect(self._on_show)
        done_row.addWidget(self.open_btn)
        done_row.addWidget(self.show_btn)
        done_row.addStretch(1)
        root.addLayout(done_row)

        central = QWidget()
        central.setLayout(root)
        self.setCentralWidget(central)

        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._on_tick)

    # --- file input ---

    def _on_drag_enter(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def _on_drop(self, event):
        urls = event.mimeData().urls()
        if urls:
            self.set_file(urls[0].toLocalFile())

    def _on_pick(self):
        path, _ = QFileDialog.getOpenFileName(self, "Выбрать аудио/видео", "", AUDIO_FILTER)
        if path:
            self.set_file(path)

    def set_file(self, path: str):
        self._job_path = path
        self.file_lbl.setText(os.path.basename(path))
        self.drop.setText(os.path.basename(path))
        self.out_lbl.setText("")
        self.open_btn.setEnabled(False)
        self.show_btn.setEnabled(False)

    # --- run ---

    def _on_start(self):
        if not self._job_path or not os.path.isfile(self._job_path):
            QMessageBox.warning(self, "Нет файла", "Сначала выберите аудио/видео файл.")
            return
        fmt = self.format_cb.currentData()
        job = Job(
            input=self._job_path,
            output=default_output(self._job_path, fmt),
            fmt=fmt,
            model_id=self.model_cb.currentData(),
            device=self.device_cb.currentData(),
        )
        self.live.clear()
        self._set_running(True)
        self._started = time.perf_counter()
        self._timer.start()
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)  # indeterminate until VAD reports total

        engine_exe = find_engine()
        if engine_exe is not None:
            self._start_engine_process(job, engine_exe)
        elif devices.has_torch():
            self._start_in_process(job)
        else:
            self._timer.stop()
            self._set_running(False)
            self.progress.setVisible(False)
            answer = QMessageBox.question(
                self, "Нет движка",
                "Нейросетевой движок не установлен.\n"
                "Открыть установку компонентов?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes)
            if answer == QMessageBox.StandardButton.Yes:
                self.need_setup.emit()
            return

    def _wire_common(self):
        self._worker.stage.connect(self._on_stage)
        self._worker.segments_total.connect(self._on_total)
        self._worker.chunk.connect(self._on_chunk)
        self._worker.finished.connect(self._on_finished)

    def _start_in_process(self, job):
        self._thread = QThread(self)
        self._worker = TranscribeWorker(job)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._wire_common()
        self._worker.finished.connect(self._thread.quit)
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

    def _start_engine_process(self, job, engine_exe):
        from giga_transcribe.desktop.worker_process import EngineProcessWorker
        self._thread = None
        self._worker = EngineProcessWorker(job, engine_exe)
        self._wire_common()
        self._worker.run()

    def _on_cancel(self):
        if self._worker is not None:
            self.status_lbl.setText("Отмена (дораспознаю текущий чанк)…")
            self.cancel_btn.setEnabled(False)
            self._worker.cancel()

    def _set_running(self, running: bool):
        for w in (self.go_btn, self.pick_btn, self.model_cb, self.device_cb,
                  self.format_cb):
            w.setEnabled(not running)
        self.cancel_btn.setEnabled(running)
        self.drop.setEnabled(not running)

    # --- worker events (arrive on GUI thread) ---

    def _on_stage(self, name: str):
        self.status_lbl.setText({"loading_model": "Загрузка модели…",
                                 "transcribing": "Распознавание…"}.get(name, name))

    @Slot(int)
    def _on_total(self, total: int):
        self.progress.setRange(0, total)
        self.progress.setValue(0)
        self.status_lbl.setText(f"Распознавание… 0/{total}")

    @Slot(object, object)
    def _on_chunk(self, seg, prog):
        self.progress.setValue(prog.done)
        self.status_lbl.setText(f"Распознавание… {prog.done}/{prog.total}")
        self.live.append(f"[{_fmt_ts(seg.start)}] {seg.text.strip()}")
        self.live.verticalScrollBar().setValue(
            self.live.verticalScrollBar().maximum())

    @Slot(object)
    def _on_finished(self, result):
        self._timer.stop()
        self._worker = None
        self._set_running(False)
        self.progress.setVisible(False)
        if result.status == "done":
            self.status_lbl.setText(
                f"Готово за {result.elapsed:.1f} с, сегментов: {result.segments}")
            self.out_lbl.setText(f"Сохранено: {result.output}")
            self.open_btn.setEnabled(True)
            self.show_btn.setEnabled(True)
        elif result.status == "cancelled":
            self.status_lbl.setText("Отменено.")
            self.out_lbl.setText(f"Частичный результат: {result.output}")
            self.open_btn.setEnabled(True)
            self.show_btn.setEnabled(True)
        else:
            self.status_lbl.setText("Ошибка.")
            QMessageBox.critical(self, "Ошибка распознавания", result.error)

    def _on_tick(self):
        if self._worker is not None:
            base = self.status_lbl.text().split(" · ")[0]
            self.status_lbl.setText(
                f"{base} · {time.perf_counter() - self._started:.0f} с")

    # --- result ---

    def _result_path(self) -> str:
        return self.out_lbl.text().replace("Сохранено: ", "").replace(
            "Частичный результат: ", "")

    def _on_open(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(self._result_path()))

    def _on_show(self):
        QDesktopServices.openUrl(
            QUrl.fromLocalFile(os.path.dirname(self._result_path())))
