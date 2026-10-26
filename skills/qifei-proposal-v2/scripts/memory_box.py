#!/usr/bin/env python3
"""Proposal memory box: one local page for every memory layer across all projects.

The Owner reviews agent candidates, accepts or discards them, and edits or retires
existing entries. Everything stays in the Markdown files under the memory home.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import proposal_memory as pm


ASSET_ROOT = Path(__file__).resolve().parents[1] / "assets" / "memory-box"


def entry_dict(entry: pm.Entry) -> dict[str, Any]:
    return {
        "id": entry.id, "title": entry.title, "layer": entry.layer, "target": entry.target,
        "file": entry.path.relative_to(pm.memory_home()).as_posix(), "stages": entry.stages,
        "status": entry.status, "date": entry.date, "source": entry.source, "scope": entry.scope,
        "body": entry.body, "project": entry.project,
    }


def snapshot() -> dict[str, Any]:
    """Every layer in one payload: shared layers once, then each project with its decisions and candidates."""
    shared = pm.collect(None)
    projects = []
    for pdir in pm.project_dirs():
        info = json.loads((pdir / "project.json").read_text(encoding="utf-8"))
        projects.append({
            "key": pdir.name, "name": info.get("name") or pdir.name, "path": info.get("path", ""),
            "entries": [entry_dict(e) for e in pm.collect(pdir) if e.layer == "project"],
            "candidates": [entry_dict(c) for c in pm.load_candidates(pdir)],
        })
    return {
        "home": str(pm.memory_home()),
        "enabled": pm.memory_enabled(),
        "env_override": bool(os.environ.get("QIFEI_MEMORY")),
        "layers": pm.LAYER_LABEL,
        "stages": list(pm.STAGES),
        "owner": [entry_dict(e) for e in shared if e.layer == "owner"],
        "playbook": [entry_dict(e) for e in shared if e.layer == "playbook"],
        "projects": projects,
    }


def home_digest() -> str:
    """Changes anywhere in the memory home (agents write candidates; the Owner may edit by hand)."""
    home = pm.memory_home()
    digest = hashlib.sha256()
    if home.is_dir():
        for path in sorted(home.rglob("*")):
            if path.suffix in {".md", ".json"} and path.is_file():
                stat = path.stat()
                digest.update(f"{path}:{stat.st_mtime_ns}:{stat.st_size}".encode("utf-8"))
    return digest.hexdigest()


def memory_path(relative: str) -> Path:
    """A Markdown file inside the memory home; anything else is refused."""
    home = pm.memory_home().resolve()
    path = (home / relative).resolve()
    if path.suffix != ".md" or not path.is_file() or home not in path.parents:
        raise ValueError(f"not a memory file: {relative}")
    return path


def project_folder(key: str) -> Path:
    pdir = next((p for p in pm.project_dirs() if p.name == key), None)
    if pdir is None:
        raise ValueError(f"unknown project {key}")
    return pdir


def stage_list(value: Any) -> list[str]:
    return [str(x) for x in value] if isinstance(value, list) else pm.split_list(str(value or ""))


class BoxServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int]) -> None:
        super().__init__(address, BoxHandler)
        self.token = secrets.token_urlsafe(18)
        self.digest = home_digest()
        self.changed = threading.Condition()
        self.stopping = threading.Event()

    def watch(self, interval: float = 0.7) -> None:
        while not self.stopping.wait(interval):
            digest = home_digest()
            if digest != self.digest:
                with self.changed:
                    self.digest = digest
                    self.changed.notify_all()


class BoxHandler(BaseHTTPRequestHandler):
    server: BoxServer
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, value: Any) -> None:
        self._send(status, json.dumps(value, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def _host_ok(self) -> bool:
        host = (self.headers.get("Host") or "").rsplit(":", 1)[0].strip("[]")
        return host in {"127.0.0.1", "localhost", "::1", self.server.server_address[0]}

    def _token_ok(self, query: dict[str, list[str]]) -> bool:
        supplied = self.headers.get("X-Box-Token") or (query.get("token") or [""])[0]
        return secrets.compare_digest(supplied, self.server.token)

    def do_GET(self) -> None:
        url = urlparse(self.path)
        query = parse_qs(url.query)
        if not self._host_ok():
            return self._json(403, {"error": "host not allowed"})
        if url.path == "/":
            return self._send(200, render_html(self.server.token).encode("utf-8"), "text/html; charset=utf-8")
        if not self._token_ok(query):
            return self._json(403, {"error": "missing token"})
        if url.path == "/api/memory":
            return self._json(200, snapshot())
        if url.path == "/api/events":
            return self._events()
        return self._json(404, {"error": "not found"})

    def do_POST(self) -> None:
        url = urlparse(self.path)
        if not self._host_ok() or not self._token_ok({}):
            return self._json(403, {"error": "forbidden"})
        try:
            length = int(self.headers.get("Content-Length") or 0)
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            if url.path == "/api/candidate/accept":
                result: dict[str, Any] = {"accepted": pm.accept(
                    project_folder(str(payload["project"])), str(payload["id"]), payload.get("layer") or None,
                    payload.get("title"), payload.get("body"), stage_list(payload.get("stages")) or None,
                    str(payload.get("author") or "Owner"),
                )}
            elif url.path == "/api/candidate/reject":
                pm.reject(project_folder(str(payload["project"])), str(payload["id"]))
                result = {"rejected": payload["id"]}
            elif url.path == "/api/settings":
                pm.set_memory_enabled(bool(payload["enabled"]))
                result = {"enabled": pm.memory_enabled()}
            elif url.path == "/api/entry/update":
                pm.update_entry(memory_path(str(payload["file"])), str(payload["id"]), str(payload.get("title") or ""),
                                str(payload.get("body") or ""), stage_list(payload.get("stages")),
                                stage_list(payload.get("scope")), str(payload.get("status") or ""))
                result = {"updated": payload["id"]}
            else:
                return self._json(404, {"error": "not found"})
        except (KeyError, json.JSONDecodeError, ValueError) as error:
            return self._json(400, {"error": str(error)})
        return self._json(200, {**result, "memory": snapshot()})

    def _events(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        seen = self.server.digest
        try:
            self.wfile.write(b": connected\n\n")
            self.wfile.flush()
            while not self.server.stopping.is_set():
                with self.server.changed:
                    self.server.changed.wait(timeout=15)
                    digest = self.server.digest
                if digest != seen:
                    seen = digest
                    self.wfile.write(b"event: changed\ndata: {}\n\n")
                else:
                    self.wfile.write(b": ping\n\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            return


def render_html(token: str) -> str:
    template = (ASSET_ROOT / "box.html").read_text(encoding="utf-8")
    return (template.replace("{{CSS}}", (ASSET_ROOT / "box.css").read_text(encoding="utf-8"))
            .replace("{{JS}}", (ASSET_ROOT / "box.js").read_text(encoding="utf-8").replace("</script", "<\\/script"))
            .replace("{{TOKEN_JSON}}", json.dumps(token)))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8770)
    parser.add_argument("--open", action="store_true", help="open the page in the default browser")
    args = parser.parse_args()
    pm.init(None)
    server = None
    for port in range(args.port, args.port + 20):
        try:
            server = BoxServer((args.host, port))
            break
        except OSError:
            continue
    if server is None:
        raise SystemExit(f"No free port between {args.port} and {args.port + 19}")
    threading.Thread(target=server.watch, daemon=True).start()
    url = f"http://{args.host}:{server.server_address[1]}/"
    print(f"Memory box: {url}")
    print(f"Memory home: {pm.memory_home()}")
    sys.stdout.flush()
    if args.open:
        webbrowser.open(url)
    try:
        server.serve_forever(poll_interval=0.3)
    except KeyboardInterrupt:
        pass
    finally:
        server.stopping.set()
        with server.changed:
            server.changed.notify_all()
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
