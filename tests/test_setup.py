"""setup.ensure + SetupPage, local HTTP server, no network."""
import hashlib
import io
import os
import threading
import zipfile
from http.server import BaseHTTPRequestHandler, HTTPServer

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from giga_transcribe.desktop.setup_page import SetupPage
from giga_transcribe.desktop.setup_worker import SetupWorker
from giga_transcribe.installer import downloads, setup
from giga_transcribe.installer.manifest import Component, Manifest

FILES = {"/a.bin": b"A" * 50000, "/b.bin": b"B" * 30000}
SHA = {p: hashlib.sha256(b).hexdigest() for p, b in FILES.items()}

_buf = io.BytesIO()
with zipfile.ZipFile(_buf, "w") as z:
    z.writestr("bin/tool.exe", b"TOOL")
FILES["/pack.zip"] = _buf.getvalue()
SHA["/pack.zip"] = hashlib.sha256(FILES["/pack.zip"]).hexdigest()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = FILES[self.path]
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


@pytest.fixture()
def server():
    httpd = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_port}"
    httpd.shutdown()


def make_manifest(base):
    return Manifest(version=1, components=(
        Component("c-a", "Движок", "Нейросети", "1", f"{base}/a.bin",
                  SHA["/a.bin"], len(FILES["/a.bin"])),
        Component("c-b", "Модель", "Веса", "1", f"{base}/b.bin",
                  SHA["/b.bin"], len(FILES["/b.bin"])),
    ))


def test_ensure_downloads_and_skips(tmp_path, server):
    m = make_manifest(server)
    target = tmp_path / "data"
    fetched = setup.ensure(m, target)
    assert [c.id for c in fetched] == ["c-a", "c-b"]
    assert setup.is_installed(target)
    assert setup.missing(m, target) == []
    assert setup.format_bytes(80000) == "78.1 КБ"
    assert setup.total_bytes(list(m.components)) == 80000
    assert setup.ensure(m, target) == []  # second run: nothing to do


def test_ensure_cancel(tmp_path, server):
    m = make_manifest(server)
    with pytest.raises(downloads.Cancelled):
        setup.ensure(m, tmp_path / "data", should_cancel=lambda: True)
    assert not setup.is_installed(tmp_path / "data")


def test_ensure_archive(tmp_path, server):
    m = Manifest(version=1, components=(
        Component("pack", "Pack", "zip", "1", f"{server}/pack.zip",
                  SHA["/pack.zip"], len(FILES["/pack.zip"]),
                  extract=True, files=("bin/tool.exe",)),
    ))
    target = tmp_path / "data"
    assert setup.ensure(m, target)[0].id == "pack"
    assert (target / "pack" / "bin" / "tool.exe").read_bytes() == b"TOOL"
    assert setup.ensure(m, target) == []  # verified present, skip
    assert setup.is_installed(target)


def test_strip_top_and_validation(tmp_path, server):
    import io as _io
    import zipfile as _zf
    buf = _io.BytesIO()
    with _zf.ZipFile(buf, "w") as z:
        z.writestr("ffmpeg-9.0/bin/ffmpeg.exe", b"FF")
        z.writestr("ffmpeg-9.0/bin/ffprobe.exe", b"FP")
        z.writestr("../evil", b"X")
    FILES["/strip.zip"] = buf.getvalue()
    SHA["/strip.zip"] = hashlib.sha256(buf.getvalue()).hexdigest()
    m = Manifest(version=1, components=(
        Component("ff", "FF", "zip", "1", f"{server}/strip.zip",
                  SHA["/strip.zip"], len(buf.getvalue()),
                  extract=True, strip_top=True,
                  files=("bin/ffmpeg.exe", "bin/ffprobe.exe")),
    ))
    target = tmp_path / "data"
    setup.ensure(m, target)
    assert (target / "ff" / "bin" / "ffmpeg.exe").read_bytes() == b"FF"
    assert not (target / "evil").exists()
    with pytest.raises(ValueError):
        Manifest.from_dict({"components": [{
            "id": "x", "title": "X", "description": "d", "version": "1",
            "url": "u", "sha256": "s", "size": 1, "extract": True}]})


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_page_shows_total(qapp, tmp_path, server):
    page = SetupPage(make_manifest(server), tmp_path / "data")
    assert "78.1" in page.total_lbl.text()
    assert "78.1" in page.go_btn.text()
    assert len(page.rows) == 2
    page.refresh()
    assert page.rows["c-a"][0].text() == "Нужно скачать"


def test_page_fetch_error_offers_retry(qapp, tmp_path):
    from giga_transcribe.installer.manifest import Manifest
    page = SetupPage(Manifest(), tmp_path / "data",
                     fetch_error="cannot fetch: 404")
    assert "Не удалось загрузить" in page.total_lbl.text()
    assert page.go_btn.text() == "Повторить"
    got = []
    page.retry_requested.connect(lambda: got.append(True))
    page._on_start()
    assert got == [True]


def test_worker_relays(qapp, monkeypatch, tmp_path, server):
    import giga_transcribe.installer.setup as setup_mod

    m = make_manifest(server)

    def fake_ensure(manifest, target, *, on_component=None, on_progress=None,
                    should_cancel=None):
        on_component(manifest.components[0], 0, 2)
        on_progress(manifest.components[0], 10, 50)
        return ["c-a"]

    monkeypatch.setattr(setup_mod, "ensure", fake_ensure)
    got = {}
    w = SetupWorker(m, tmp_path)
    w.component.connect(lambda c, i, n: got.setdefault("comp", (c.id, i, n)))
    w.progress.connect(lambda c, r, t: got.setdefault("prog", (r, t)))
    w.finished.connect(lambda r: got.setdefault("done", (r.status, r.fetched)))
    w.run()
    assert got["comp"] == ("c-a", 0, 2)
    assert got["prog"] == (10, 50)
    assert got["done"] == ("done", ["c-a"])
