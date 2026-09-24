"""Downloader + manifest + state. Local HTTP server, no network."""
import hashlib
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from gigaam_ui.installer import downloads, manifest as manifest_mod
from gigaam_ui.installer import state as state_mod

PAYLOAD = bytes(range(256)) * 400  # 102400 bytes
SHA = hashlib.sha256(PAYLOAD).hexdigest()


class Handler(BaseHTTPRequestHandler):
    support_range = True

    def _send(self, start, end):
        body = PAYLOAD[start:end]
        self.send_response(206 if start else 200)
        if start:
            self.send_header("Content-Range", f"bytes {start}-{end - 1}/{len(PAYLOAD)}")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/norange":
            self.send_response(200)
            self.send_header("Content-Length", str(len(PAYLOAD)))
            self.end_headers()
            self.wfile.write(PAYLOAD)
            return
        start = 0
        rng = self.headers.get("Range")
        if rng and self.support_range:
            start = int(rng.split("=")[1].split("-")[0])
        self._send(start, len(PAYLOAD))

    def log_message(self, *a):
        pass


@pytest.fixture()
def server():
    httpd = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_port}"
    httpd.shutdown()


def test_full_download(tmp_path, server):
    seen = []
    out = downloads.download(f"{server}/f.bin", tmp_path / "f.bin",
                             expected_sha256=SHA,
                             on_progress=lambda r, t: seen.append((r, t)))
    assert out.read_bytes() == PAYLOAD
    assert not (tmp_path / "f.bin.part").exists()
    assert seen[0][0] == 0 and seen[-1] == (len(PAYLOAD), len(PAYLOAD))
    received = [r for r, _ in seen]
    assert all(b >= a for a, b in zip(received, received[1:]))


def test_resume(tmp_path, server):
    part = tmp_path / "f.bin.part"
    part.write_bytes(PAYLOAD[:40000])
    out = downloads.download(f"{server}/f.bin", tmp_path / "f.bin",
                             expected_sha256=SHA)
    assert out.read_bytes() == PAYLOAD


def test_range_ignored_restarts(tmp_path, server):
    part = tmp_path / "f.bin.part"
    part.write_bytes(b"stale-partial-data")
    out = downloads.download(f"{server}/norange", tmp_path / "f.bin",
                             expected_sha256=SHA)
    assert out.read_bytes() == PAYLOAD


def test_bad_checksum_removes_part(tmp_path, server):
    with pytest.raises(downloads.ChecksumError):
        downloads.download(f"{server}/f.bin", tmp_path / "f.bin",
                           expected_sha256="0" * 64)
    assert not (tmp_path / "f.bin.part").exists()


def test_cancel_keeps_part(tmp_path, server):
    stop = {"go": False}

    def prog(received, total):
        if received > 0:
            stop["go"] = True

    with pytest.raises(downloads.Cancelled):
        downloads.download(f"{server}/f.bin", tmp_path / "f.bin",
                           expected_sha256=SHA, on_progress=prog,
                           should_cancel=lambda: stop["go"])
    assert (tmp_path / "f.bin.part").is_file()


def test_manifest_roundtrip():
    m = manifest_mod.Manifest.from_dict({
        "version": 1,
        "components": [{
            "id": "ffmpeg", "title": "FFmpeg", "description": "media",
            "version": "9.0", "url": "https://x/y.zip",
            "sha256": "ab" * 32, "size": 123,
        }],
    })
    assert m.get("ffmpeg").size == 123
    with pytest.raises(KeyError):
        m.get("nope")
    with pytest.raises(ValueError):
        manifest_mod.Manifest.from_json("{bad")
    with pytest.raises(ValueError):
        manifest_mod.Manifest.from_dict({"components": [{"id": "x"}]})


def test_state_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv(state_mod.ENV_OVERRIDE, str(tmp_path / "portable"))
    assert state_mod.data_dir() == tmp_path / "portable"
    assert state_mod.component_dir("ffmpeg") == tmp_path / "portable" / "ffmpeg"
