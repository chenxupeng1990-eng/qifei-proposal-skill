from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import draft_studio  # noqa: E402


FEISHU_DRAFT = """<title>示例品牌长期合作提案｜协作母版</title>

<callout emoji="💡">
**内容确认版**
请按 slide_id 逐页评论。
</callout>

# 开场｜重新选择增长伙伴

**本章回答：** 为什么现在需要长期伙伴。

## P01｜示例品牌中国市场长期合作提案

![封面图说明](https://internal-api-drive-stream.feishu.cn/space/api/box/stream/download/authcode/?code=abc)

### 核心内容

**我们要承担的是长期经营，而不是一次传播。**

| **页面任务** | **内容** |
|-|-|
| 页面角色 | 封面 |

### 逻辑展开

长期意图 → 单渠道失效 → 需要增长出口

### PPT上屏内容

| **元素** | **精确内容** |
|-|-|
| 标题 | 示例品牌中国市场长期合作提案 |
| 副标题 | 长期总代合作方案 |

### 讲解方向

从合作意图开场。

### 策略与过桥

| 字段 | 内容 |
|-|-|
| next_page_need | 证明单渠道失效 |

### 视觉生成建议

| **项目** | **建议** |
|-|-|
| 视觉锤 | 植物与产品同框 |

### 证据与来源

> 证据编号：EX-001

## P02｜单一渠道能力不再构成竞争优势

### 核心内容

渠道已经全域化。

# 抖音机会更大

## P03｜抖音把流量和销售放在同一个经营场

### 核心内容

内容即货架。
"""

CHAPTER_FILE = """# CH02｜把品牌经营成生活方式

## 章节演讲任务

把增长方向编译成经营打法。

## 页面

### [P08] 品牌锚点是香气生活方式

- 页面角色：品牌判断
- 核心内容：统一两个品类。
- 认知变化 `belief_shift`：从跨品类经营转为一个品牌。
- 逻辑展开：个护增长 → 家清差异 → 统一锚点
- 上屏副标题：同一种香气生活方式
- 讲解方向：先讲为什么不能各自增长。
- 视觉锤：一条香气轨迹。
- 前页推导：品类角色不同。
- 证据编号：EX-002
- 用户确认记录：待确认

### [P09] 核心用户是追求体面日常的女性

- 核心内容：先服务最懂品牌的人。
"""


def write_project(root: Path, draft: str, state: dict | None) -> Path:
    (root / "content" / "draft").mkdir(parents=True)
    (root / "content" / "draft" / "proposal-draft.md").write_text(draft, encoding="utf-8")
    if state is not None:
        (root / "project-state.json").write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    return root


class DraftStudioParsingTests(unittest.TestCase):
    def test_feishu_snapshot_maps_chapters_pages_and_fields(self) -> None:
        model = draft_studio.parse_draft(FEISHU_DRAFT)
        self.assertEqual(model["title"], "示例品牌长期合作提案｜协作母版")
        self.assertIn(":::callout", model["preface_md"])
        self.assertEqual([c["title"] for c in model["chapters"]], ["开场｜重新选择增长伙伴", "抖音机会更大"])
        self.assertEqual([s["id"] for s in model["chapters"][0]["slides"]], ["P01", "P02"])
        keys = [f["key"] for f in model["chapters"][0]["slides"][0]["fields"]]
        self.assertEqual(keys, ["lead", "core", "logic", "screen", "talk", "visual", "bridge", "evidence"])

    def test_chapter_file_bullets_become_page_fields(self) -> None:
        model = draft_studio.parse_draft(CHAPTER_FILE)
        self.assertEqual(len(model["chapters"]), 1)
        chapter = model["chapters"][0]
        self.assertEqual(chapter["title"], "把品牌经营成生活方式")
        self.assertIn("章节演讲任务", chapter["intro_md"])
        self.assertEqual([s["id"] for s in chapter["slides"]], ["P08", "P09"])
        fields = {f["key"]: f["md"] for f in chapter["slides"][0]["fields"]}
        self.assertTrue(fields["core"].startswith("**统一两个品类。**"))
        self.assertIn("| 认知变化 |", fields["core"])
        self.assertEqual(fields["logic"], "个护增长 → 家清差异 → 统一锚点")
        self.assertIn("视觉锤", fields["visual"])
        self.assertIn("前页推导", fields["bridge"])
        self.assertIn("用户确认记录", fields["other"])

    def test_status_comes_from_project_state(self) -> None:
        model = draft_studio.parse_draft(FEISHU_DRAFT)
        draft_studio.attach_status(model, {
            "chapters": [{"chapter_id": "CH00", "slides": ["P01", "P02"], "manuscript_confirmed": True}],
            "proposal_draft": {"verified_slide_ids": ["P03"]},
        })
        statuses = {s["id"]: s["status"] for c in model["chapters"] for s in c["slides"]}
        self.assertEqual(statuses, {"P01": "confirmed", "P02": "confirmed", "P03": "verified"})

    def test_missing_page_units_fail_loudly(self) -> None:
        with self.assertRaises(ValueError):
            draft_studio.parse_draft("# 只有标题\n\n正文")


class DraftStudioExportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.project = write_project(Path(self.tmp.name), FEISHU_DRAFT, {
            "project_name": "示例项目",
            "phase": "manuscript",
            "proposal_draft": {"authority": "local", "revision_id": 3, "verified_slide_ids": []},
            "chapters": [],
        })

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_brief_markdown_drops_production_fields_and_auth_images(self) -> None:
        model = draft_studio.build_model(self.project, None)
        full = draft_studio.export_markdown(model, "full")
        brief = draft_studio.export_markdown(model, "brief")
        self.assertIn("#### 视觉生成建议", full)
        self.assertNotIn("#### 视觉生成建议", brief)
        self.assertNotIn("#### 策略与过桥", brief)
        self.assertIn("#### PPT上屏内容", brief)
        for text in (full, brief):
            self.assertNotIn("internal-api-drive-stream", text)
            self.assertNotIn("<callout", text)
            self.assertIn("> **提示**", text)
            self.assertIn("rev 3", text)

    def test_rendered_page_embeds_model_and_both_markdown_profiles(self) -> None:
        out = self.project / "deck" / "review" / "draft-studio.html"
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "draft_studio.py"), "render", str(self.project)],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        html = out.read_text(encoding="utf-8")
        self.assertNotIn("{{", html)
        model = json.loads(html.split('<script type="application/json" id="model">', 1)[1].split("</script>", 1)[0])
        self.assertEqual(model["meta"]["revision"], 3)
        self.assertEqual(sum(len(c["slides"]) for c in model["chapters"]), 3)
        markdown = json.loads(html.split('<script type="application/json" id="markdown">', 1)[1].split("</script>", 1)[0])
        self.assertEqual(set(markdown), {"full", "brief"})

    def test_script_closing_tags_inside_draft_cannot_break_the_page(self) -> None:
        draft = FEISHU_DRAFT.replace("从合作意图开场。", "从合作意图开场。</script><script>alert(1)</script>")
        project = write_project(Path(self.tmp.name) / "injected", draft, None)
        html = draft_studio.render_html(draft_studio.build_model(project, None))
        self.assertNotIn("</script><script>alert(1)", html)

    def test_export_cli_writes_brief_file(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "draft_studio.py"), "export-md", str(self.project),
             "--profile", "brief", "--out", "exports/draft-brief.md"],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.project / "exports" / "draft-brief.md").read_text(encoding="utf-8").startswith("# "))


@unittest.skipUnless(
    shutil.which("node") and (SKILL_ROOT / "node_modules" / "playwright-core").is_dir(),
    "node runtime dependencies are not installed",
)
class DraftStudioBrowserTests(unittest.TestCase):
    def test_page_renders_every_view_without_script_errors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = write_project(Path(tmp), FEISHU_DRAFT, None)
            html = project / "studio.html"
            html.write_text(draft_studio.render_html(draft_studio.build_model(project, None)), encoding="utf-8")
            result = subprocess.run(
                ["node", str(SCRIPTS / "check_draft_studio.mjs"), str(html)],
                cwd=SKILL_ROOT, capture_output=True, text=True, check=False,
            )
            if "not found" in result.stderr and "Chrome" in result.stderr:
                self.skipTest("no Chromium-based browser available")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["slides"], 3)
            self.assertEqual(report["script_errors"], [])
            self.assertEqual(report["views"]["client"]["visual_fields"], 0)
            self.assertGreater(report["views"]["full"]["visual_fields"], 0)
            self.assertEqual(report["views"]["chain"]["screens"], 0)
            self.assertTrue(report["search_empty_state"])


if __name__ == "__main__":
    unittest.main()
