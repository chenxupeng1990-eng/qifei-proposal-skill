from __future__ import annotations

import hashlib
import json
import os
import re
import signal
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import draft_studio  # noqa: E402
from validate_feishu_draft import validate_feishu_draft_evidence  # noqa: E402


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


class WindowsCompatRegressionTests(unittest.TestCase):
    def test_legacy_crlf_baseline_does_not_regress_verified_status(self) -> None:
        """A pre-LF-normalisation log.jsonl with a raw CRLF sha256 must not trigger sync_external."""
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            draft_dir = project / "content" / "draft"
            rev_dir = draft_dir / "revisions"
            rev_dir.mkdir(parents=True)
            draft_path = draft_dir / "proposal-draft.md"
            crlf_bytes = (
                "# 测试提案\r\n\r\n"
                "## P01｜封面\r\n"
                "### 核心内容\r\n开场判断。\r\n"
            ).encode("utf-8")
            draft_path.write_bytes(crlf_bytes)
            raw_sha = hashlib.sha256(crlf_bytes).hexdigest()

            (rev_dir / "rev-000001.md").write_bytes(crlf_bytes)
            (rev_dir / "log.jsonl").write_text(
                json.dumps({"revision": 1, "sha256": raw_sha, "actor": "baseline", "slides": [], "note": "init"}) + "\n",
                encoding="utf-8",
            )
            state_path = project / "project-state.json"
            state_path.write_text(
                json.dumps({
                    "project_id": "win-crlf-01",
                    "project_name": "CRLF Legacy Fixture",
                    "phase": "drafting",
                    "proposal_draft": {
                        "authority": "studio",
                        "status": "verified",
                        "revision_id": 1,
                        "verified_snapshot_path": "content/draft/proposal-draft.md",
                        "verified_snapshot_sha256": raw_sha,
                    },
                    "chapters": [],
                }, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            path, state = draft_studio.load_project(project, None)
            store = draft_studio.DraftStore(project, path, state)
            self.assertIsNone(store.sync_external())
            self.assertEqual(store.revision, 1)
            reloaded = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(reloaded["proposal_draft"]["status"], "verified")

    def test_validate_feishu_draft_accepts_lf_hash_for_crlf_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            feishu_dir = project / "content" / "feishu"
            feishu_dir.mkdir(parents=True)
            snap = feishu_dir / "proposal-draft.md"
            lf_text = "# 提案\n\n## P01｜标题\n### 核心内容\n正文。\n"
            snap.write_bytes(lf_text.replace("\n", "\r\n").encode("utf-8"))
            state = {
                "proposal_draft": {
                    "authority": "feishu",
                    "status": "verified",
                    "format_version": "proposal-draft-v2",
                    "feishu_doc_url": "https://example.feishu.cn/docx/demo",
                    "document_id": "doc-demo",
                    "last_verified_at": "2026-11-26T18:00:00+08:00",
                    "revision_id": 1,
                    "verified_snapshot_path": "content/feishu/proposal-draft.md",
                    "verified_snapshot_sha256": hashlib.sha256(lf_text.encode("utf-8")).hexdigest(),
                },
                "chapters": [],
            }
            errors = validate_feishu_draft_evidence(project, state)
            self.assertEqual(errors, [])

    def test_serve_detached_handles_chinese_path_under_gbk_parent_encoding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "项目"
            draft_dir = project / "content" / "draft"
            draft_dir.mkdir(parents=True)
            (draft_dir / "proposal-draft.md").write_text(
                "# 中文路径测试\n\n## P01｜封面\n### 核心内容\n测试。\n",
                encoding="utf-8",
            )
            port = _free_port()
            env = {**os.environ, "PYTHONIOENCODING": "gbk"}
            env.pop("PYTHONUTF8", None)
            pid = None
            try:
                res = subprocess.run(
                    [
                        sys.executable,
                        str(SCRIPTS / "draft_studio.py"),
                        "serve",
                        str(project),
                        "--detach",
                        "--port",
                        str(port),
                    ],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    env=env,
                    timeout=20,
                    check=False,
                )
                self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
                self.assertIn("Draft studio: http://", res.stdout)
                m = re.search(r"pid (\d+)", res.stdout)
                if m:
                    pid = int(m.group(1))
            finally:
                if pid:
                    try:
                        if os.name == "nt":
                            subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True, check=False)
                        else:
                            os.kill(pid, signal.SIGTERM)
                    except OSError:
                        pass


if __name__ == "__main__":
    unittest.main()
