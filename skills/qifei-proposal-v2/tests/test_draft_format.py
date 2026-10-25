from __future__ import annotations

import hashlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import draft_studio  # noqa: E402
from validate_project import validate_verified_feishu_draft  # noqa: E402


def page(page_id: str, title: str, fields: dict[str, str] | None = None) -> str:
    fields = fields or {}
    body = [f"## {page_id}｜{title}", ""]
    for name in draft_studio.CANONICAL_FIELDS:
        body += [f"### {name}", "", fields.get(name, f"{name}的内容。"), ""]
    return "\n".join(body)


CANONICAL = "\n".join([
    "# 开场｜重新选择增长伙伴",
    "",
    "**本章回答：** 为什么需要长期伙伴。",
    "",
    page("P01", "示例品牌中国长期合作提案"),
    page("P02", "单一渠道能力不再构成竞争优势"),
])

BOLD_LABELS = """# 第一章｜生成越快，失控越隐蔽

## S01｜工具不稀缺，稀缺的是不让策略走丢的系统

**核心内容：**真正稀缺的是让想法在几十页里保持同一条策略。

**逻辑展开：**先承认生成能力已经普及，再转向控制难题。

**PPT上屏内容：**
工具不稀缺
**缺的是一套生产系统**

**讲解方向：**从大家都见过的 AI 生成 PPT 进入。

**策略与过桥：**belief_shift＝从工具转向系统。

**视觉生成建议：**视觉锤为“混沌被铸造成作品”。

**证据与来源：**本次全流程测试。
"""

FRAMEWORK = """<title>示例乳品提案框架 V2</title>

# 策略序章｜为什么现在是这个产品的时间

## 本章任务

用行业事实建立五个确定性判断。

## P01｜三股行业力量正在汇合

**本页结论：**人口、营养和产业正在同时变化。

| 行业力量 | 外部事实 |
|-|-|
| **人口结构上移** | 银发人口持续增长。 |

**品牌判断：**这是一条结构性机会。

**建议呈现：**三张大数字卡。

行业参考：[示例统计公报](https://example.com/report)

## P02｜核心创意：让好东西留下来

**本页结论：**这是一套完整的创意结构。

<grid>
<column width-ratio="0.5">
### 价值被留下
以专利结果建立进阶标准。
</column>
<column width-ratio="0.5">
### 习惯被留下
每天一杯的低门槛形态。
</column>
</grid>

**建议视觉：**以两个“留下来”作为全案母体。
"""


class CheckFormatTests(unittest.TestCase):
    def test_canonical_draft_passes(self) -> None:
        self.assertEqual(draft_studio.check_format(CANONICAL), [])

    def test_common_deviations_are_reported_by_page(self) -> None:
        broken = CANONICAL.replace("### 讲解方向", "### 演讲任务", 1)
        broken = broken.replace("## P02｜", "## [P02]｜", 1)
        broken = broken.replace("策略与过桥的内容。", "待补充", 1)
        broken += "\n## 附录说明\n\n一些说明。\n"
        messages = {(i["page"], i["message"]) for i in draft_studio.check_format(broken)}
        texts = " ".join(m for _, m in messages)
        self.assertIn(("P01", "`### 演讲任务` 请改成 `### 讲解方向`"), messages)
        self.assertIn(("P01", "缺少 `### 讲解方向`"), messages)
        self.assertIn(("P01", "`### 策略与过桥` 是空的"), messages)
        self.assertIn("## P02｜", texts)
        self.assertIn("二级标题只能用于页面", texts)

    def test_order_duplicates_stray_content_and_ids(self) -> None:
        swapped = CANONICAL.replace("### 核心内容\n\n核心内容的内容。\n\n### 逻辑展开\n\n逻辑展开的内容。",
                                    "### 逻辑展开\n\n逻辑展开的内容。\n\n### 核心内容\n\n核心内容的内容。", 1)
        swapped = swapped.replace("## P01｜示例品牌中国长期合作提案\n", "## P01｜示例品牌中国长期合作提案\n\n一段没有放进字段的话。\n", 1)
        swapped = swapped.replace("## P02｜", "## P01｜", 1)
        texts = [i["message"] for i in draft_studio.check_format(swapped)]
        self.assertTrue(any(t.startswith("字段顺序应为") for t in texts))
        self.assertTrue(any("只能放页面预览图" in t for t in texts))
        self.assertIn("页码重复", texts)

    def test_bold_labels_are_rejected(self) -> None:
        texts = [i["message"] for i in draft_studio.check_format(BOLD_LABELS)]
        self.assertIn("用了加粗标签 `**核心内容**`，请改成 `### 核心内容`", texts)
        self.assertIn("缺少 `### 核心内容`", texts)

    def test_preview_image_before_core_is_allowed(self) -> None:
        with_image = CANONICAL.replace("## P01｜示例品牌中国长期合作提案\n", "## P01｜示例品牌中国长期合作提案\n\n![封面](https://example.com/a.png)\n", 1)
        self.assertEqual(draft_studio.check_format(with_image), [])


class NormalizeTests(unittest.TestCase):
    def test_bold_label_draft_becomes_canonical(self) -> None:
        normalized, notes = draft_studio.normalize_draft(BOLD_LABELS)
        self.assertEqual(draft_studio.check_format(normalized), [])
        model = draft_studio.parse_draft(normalized)
        fields = {f["key"]: f["md"] for f in model["chapters"][0]["slides"][0]["fields"]}
        self.assertEqual(fields["core"], "真正稀缺的是让想法在几十页里保持同一条策略。")
        self.assertIn("**缺的是一套生产系统**", fields["screen"])
        self.assertEqual(notes, [])

    def test_framework_draft_maps_labels_and_marks_gaps(self) -> None:
        normalized, notes = draft_studio.normalize_draft(FRAMEWORK)
        self.assertTrue(normalized.startswith("<title>示例乳品提案框架 V2</title>"))
        self.assertIn("**本章任务**", normalized)
        model = draft_studio.parse_draft(normalized)
        p01 = {f["key"]: f["md"] for f in model["chapters"][0]["slides"][0]["fields"]}
        self.assertEqual(p01["core"], "人口、营养和产业正在同时变化。")
        self.assertIn("| **人口结构上移** |", p01["logic"])
        self.assertIn("**品牌判断：**这是一条结构性机会。", p01["logic"])
        self.assertEqual(p01["visual"], "三张大数字卡。")
        self.assertIn("行业参考：[示例统计公报]", p01["evidence"])
        p02 = normalized.split("## P02｜", 1)[1]
        self.assertIn("<grid>", p02)
        self.assertIn("#### 价值被留下", p02)
        exported = draft_studio.export_markdown(draft_studio.parse_draft(normalized), "brief")
        self.assertIn("##### 价值被留下", exported)
        self.assertNotIn("<grid>", exported)
        self.assertNotIn("::col", exported)
        remaining = {i["message"] for i in draft_studio.check_format(normalized)}
        self.assertTrue(remaining)
        self.assertTrue(all(m.endswith("是空的") for m in remaining), remaining)
        messages = {n["message"] for n in notes}
        self.assertIn("`本页结论` 归入 `核心内容`", messages)
        self.assertIn("`品牌判断` 放进 `逻辑展开`，保留原标签", messages)
        self.assertIn("缺少 `PPT上屏内容`，已占位“待补充”，需要补写", messages)

    def test_canonical_draft_is_left_as_is(self) -> None:
        normalized, notes = draft_studio.normalize_draft(CANONICAL)
        self.assertEqual(draft_studio.check_format(normalized), [])
        self.assertEqual(notes, [])
        self.assertEqual(draft_studio.parse_draft(normalized), draft_studio.parse_draft(CANONICAL))

    def test_cli_previews_then_writes_with_backup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            draft = project / "content" / "draft" / "proposal-draft.md"
            draft.parent.mkdir(parents=True)
            draft.write_text(FRAMEWORK, encoding="utf-8")
            run = lambda *args: subprocess.run([sys.executable, str(SCRIPTS / "draft_studio.py"), *args, str(project)],
                                               capture_output=True, text=True, check=False)
            self.assertEqual(run("check").returncode, 1)
            preview = run("normalize")
            self.assertEqual(preview.returncode, 0, preview.stderr)
            self.assertEqual(draft.read_text(encoding="utf-8"), FRAMEWORK)
            self.assertTrue((draft.parent / "proposal-draft.normalize-preview.md").is_file())
            written = subprocess.run([sys.executable, str(SCRIPTS / "draft_studio.py"), "normalize", str(project), "--write"],
                                     capture_output=True, text=True, check=False)
            self.assertEqual(written.returncode, 0, written.stderr)
            backups = list(draft.parent.glob("proposal-draft.pre-normalize-*.md"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_text(encoding="utf-8"), FRAMEWORK)
            self.assertFalse((draft.parent / "proposal-draft.normalize-preview.md").exists())
            self.assertIn("## P01｜三股行业力量正在汇合", draft.read_text(encoding="utf-8"))


class StudioAndGateTests(unittest.TestCase):
    def test_studio_shows_unknown_content_instead_of_hiding_it(self) -> None:
        model = draft_studio.parse_draft(FRAMEWORK)
        keys = [f["key"] for f in model["chapters"][0]["slides"][0]["fields"]]
        self.assertEqual(keys, ["body"])

    def test_model_carries_format_issues(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            draft = project / "content" / "draft" / "proposal-draft.md"
            draft.parent.mkdir(parents=True)
            draft.write_text(FRAMEWORK, encoding="utf-8")
            self.assertTrue(draft_studio.build_model(project, None)["format_issues"])
            draft.write_text(CANONICAL, encoding="utf-8")
            self.assertEqual(draft_studio.build_model(project, None)["format_issues"], [])

    def _gate(self, text: str, version: str) -> list[str]:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            snapshot = project / "content" / "feishu" / "proposal-draft.md"
            snapshot.parent.mkdir(parents=True)
            snapshot.write_text(text, encoding="utf-8")
            state = {"proposal_draft": {
                "authority": "feishu", "status": "verified", "format_version": version,
                "feishu_doc_url": "https://example.com/doc", "document_id": "doc", "revision_id": 3,
                "last_verified_at": "2026-10-25T10:00:00+08:00",
                "verified_snapshot_path": "content/feishu/proposal-draft.md",
                "verified_snapshot_sha256": hashlib.sha256(snapshot.read_bytes()).hexdigest(),
                "verified_slide_ids": ["S01"],
            }}
            return validate_verified_feishu_draft(project, state, [{"chapter_id": "CH01", "slides": ["S01"]}])

    def test_v2_drafts_must_pass_the_format_check(self) -> None:
        self.assertTrue(any("draft format" in e and "加粗标签" in e for e in self._gate(BOLD_LABELS, "proposal-draft-v2")))

    def test_v1_projects_keep_the_legacy_check(self) -> None:
        self.assertFalse(any("draft format" in e for e in self._gate(BOLD_LABELS, "feishu-proposal-draft-v1")))


if __name__ == "__main__":
    unittest.main()
