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

WIDE = "| 价格带 | 2025 商品数 | 2025 销售额 | 2025 销量 | 2026 商品数 | 2026 销售额 | 2026 销量 | 变化 |\n|-|-|-|-|-|-|-|-|\n" + "".join(
    f"| 带{i} | 1% | 2% | 3% | 4% | 5% | 6% | +{i} |\n" for i in range(7)
)
DRAFT = f"""<title>上屏表格样例</title>

# 数据页

## P01｜键值上屏

### PPT上屏内容

| **元素** | **精确内容** |
|-|-|
| 标题 | 键值标题 |
| 副标题 | 键值副标题 |
| 核心数字 | 24.95% → 16.49% |

## P02｜多列上屏

### PPT上屏内容

- 标题：多列标题
- 核心数字：¥100–200　24.95% → 16.49%

**上屏数据表：全价格带**

{WIDE}
**上屏数据表：带货方式**

| 年份 | 品牌自营 | 达人推广 | 商品卡 |
|-|-|-|-|
| 2025 | 33.13% | 37.91% | 28.96% |
| 2026 | 36.91% | 40.97% | 22.12% |

来源：飞瓜带货品类分析。

## P03｜两张两列表

### PPT上屏内容

| 年份 | 销售额 |
|-|-|
| 2025 | 100 |

| 渠道 | 占比 |
|-|-|
| 抖音 | 60% |
| 天猫 | 40% |

## P04｜两列数据表

### PPT上屏内容

- 标题：两列数据标题

**上屏数据表：现有资产**

| 资产 | 数据 |
|-|-|
| 天猫旗舰店 | 6 年 |
| 高端零售 | 连卡佛 |

- 来源：天猫旗舰店页面
"""


@unittest.skipUnless(
    shutil.which("node") and (SKILL_ROOT / "node_modules" / "playwright-core").is_dir(),
    "node runtime dependencies are not installed",
)
class ScreenFieldPreviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp = tempfile.TemporaryDirectory()
        project = Path(cls.temp.name)
        (project / "content" / "draft").mkdir(parents=True)
        (project / "content" / "draft" / "proposal-draft.md").write_text(DRAFT, encoding="utf-8")
        out = project / "studio.html"
        subprocess.run([sys.executable, str(SCRIPTS / "draft_studio.py"), "render", str(project), "--out", str(out)],
                       check=True, capture_output=True, text=True, encoding="utf-8", errors="replace")
        result = subprocess.run(["node", str(Path(__file__).with_name("draft-studio-screen.e2e.mjs")), str(out)],
                                cwd=SKILL_ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False, timeout=60)
        if result.returncode == 3:
            raise unittest.SkipTest("no Chromium-based browser available")
        assert result.returncode == 0, result.stdout + result.stderr
        cls.report = json.loads(result.stdout)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp.cleanup()

    def test_page_has_no_script_errors(self) -> None:
        self.assertEqual(self.report["script_errors"], [])

    def test_two_column_key_value_table_keeps_card_layout(self) -> None:
        p01 = self.report["slides"]["P01"]
        self.assertEqual(p01["title"], "键值标题")
        self.assertEqual(p01["kv_rows"], ["核心数字"])
        self.assertEqual(p01["tables"], [])

    def test_wide_tables_show_every_column_and_row_in_place(self) -> None:
        p02 = self.report["slides"]["P02"]
        self.assertEqual(p02["title"], "多列标题")
        self.assertEqual(p02["kv_rows"], [])
        self.assertEqual([(t["columns"], t["rows"]) for t in p02["tables"]], [(8, 7), (4, 2)])
        self.assertEqual(p02["tables"][0]["cells"], [8] * 7)
        self.assertEqual(p02["sequence"], ["核心数字：¥100–20", "上屏数据表：全价格带", "TABLE", "上屏数据表：带货方式", "TABLE", "来源：飞瓜带货品类分析。"])

    def test_several_tables_are_not_merged(self) -> None:
        p03 = self.report["slides"]["P03"]
        self.assertEqual([(t["columns"], t["rows"]) for t in p03["tables"]], [(2, 1), (2, 2)])

    def test_single_two_column_data_table_is_shown_whole(self) -> None:
        p04 = self.report["slides"]["P04"]
        self.assertEqual(p04["title"], "两列数据标题")
        self.assertEqual(p04["kv_rows"], [])
        self.assertEqual([(t["columns"], t["rows"]) for t in p04["tables"]], [(2, 2)])
        self.assertEqual(p04["sequence"], ["上屏数据表：现有资产", "TABLE", "来源：天猫旗舰店页面"])


if __name__ == "__main__":
    unittest.main()
