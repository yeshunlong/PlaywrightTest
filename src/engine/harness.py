"""
测试 Harness（测试执行框架）定义与导出

Harness 是支撑测试用例自动执行的完整基础设施，
包括 Playwright 配置、操作执行器、元素定位策略、
截图管理、错误处理等。

本模块负责：
1. 定义并导出 Harness 的完整配置
2. 生成 Harness 说明文档
3. 为面试官展示可复现的测试环境
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger


class HarnessDefinition:
    """测试 Harness 完整定义"""

    def __init__(self, config: dict):
        self.config = config
        self.pw_cfg = config.get("playwright", {})
        self.ai_cfg = config.get("ai", {})
        self.app_cfg = config.get("app", {})

    def to_dict(self) -> dict:
        """导出为结构化字典"""
        return {
            "meta": {
                "name": "同花顺远航版测试用例清洗 Harness",
                "version": "1.0.0",
                "description": "基于 Playwright + AI 的测试用例自动化执行与清洗框架",
                "exported_at": datetime.now(timezone.utc).isoformat(),
            },
            "architecture": {
                "overview": "Playwright 自动化浏览器 → 操作同花顺远航版客户端 → AI 分析结果",
                "components": {
                    "browser_engine": {
                        "framework": "Playwright (async)",
                        "browser": "Chromium",
                        "mode": "desktop_webview",
                        "connection": "通过 Chromium 连接到客户端内嵌 WebView",
                    },
                    "ai_engine": {
                        "provider": self.ai_cfg.get("provider", "openai"),
                        "model": self.ai_cfg.get("model", "gpt-4o"),
                        "temperature": self.ai_cfg.get("temperature", 0.1),
                        "api_type": "OpenAI 兼容 API",
                        "roles": [
                            "步骤解析: 自然语言 → 结构化操作步骤",
                            "操作生成: 结构化步骤 → Playwright 操作指令",
                            "结果分析: 截图 + 日志 → 通过/失败 + 清洗标签",
                            "报告摘要: 统计数据 → 自然语言分析报告",
                        ],
                    },
                    "action_executor": {
                        "supported_actions": [
                            {"type": "click", "description": "点击 UI 元素，支持 text/role/menuitem 定位"},
                            {"type": "dblclick", "description": "双击 UI 元素"},
                            {"type": "input", "description": "文本输入"},
                            {"type": "wait", "description": "等待，毫秒级"},
                            {"type": "screenshot", "description": "全页截图"},
                            {"type": "assert", "description": "断言元素存在/文本匹配"},
                            {"type": "scroll", "description": "页面滚动"},
                            {"type": "hover", "description": "鼠标悬停"},
                            {"type": "resize", "description": "窗口尺寸调整"},
                            {"type": "observe", "description": "截图 + AI 视觉分析"},
                        ],
                        "element_strategies": [
                            {"strategy": "text", "description": "按文本内容匹配元素"},
                            {"strategy": "role", "description": "按 WAI-ARIA 语义角色匹配"},
                            {"strategy": "selector", "description": "CSS/XPath 精确选择器"},
                        ],
                    },
                },
            },
            "configuration": {
                "playwright": {
                    "headless": self.pw_cfg.get("headless", False),
                    "timeout_ms": self.pw_cfg.get("timeout", 30000),
                    "wait_after_action_ms": self.pw_cfg.get("wait_after_action", 1000),
                    "viewport": {
                        "width": self.pw_cfg.get("viewport_width", 1280),
                        "height": self.pw_cfg.get("viewport_height", 800),
                    },
                },
                "execution": {
                    "max_concurrent_cases": self.config.get("cleaning", {}).get("max_concurrent", 1),
                    "max_retries": self.config.get("cleaning", {}).get("max_retries", 2),
                    "screenshot_on_success": self.config.get("cleaning", {}).get("screenshot_on_success", True),
                    "screenshot_on_failure": self.config.get("cleaning", {}).get("screenshot_on_failure", True),
                },
            },
            "pipeline": {
                "stages": [
                    {
                        "stage": 1,
                        "name": "Excel 解析",
                        "input": "布局与显示.xlsx",
                        "output": "TestCase[] 结构化用例列表",
                        "tools": ["openpyxl"],
                        "description": "读取 Excel，自动识别列头，映射为结构化 TestCase 对象",
                    },
                    {
                        "stage": 2,
                        "name": "AI 步骤解析",
                        "input": "TestCase（自然语言描述）",
                        "output": "TestCase（含 parsed_steps 结构化步骤）",
                        "tools": ["LLMClient → step_parse prompt"],
                        "description": "LLM 将操作描述拆分为独立的结构化步骤",
                    },
                    {
                        "stage": 3,
                        "name": "操作指令生成",
                        "input": "结构化步骤",
                        "output": "PlaywrightAction[] 操作指令列表",
                        "tools": ["LLMClient → action_gen prompt", "ActionGenerator (规则降级)"],
                        "description": "AI 生成 + 规则引擎降级的双重操作生成策略",
                    },
                    {
                        "stage": 4,
                        "name": "Playwright 执行",
                        "input": "PlaywrightAction[]",
                        "output": "StepExecutionResult[] + 截图",
                        "tools": ["PlaywrightRunner", "Chromium"],
                        "description": "在真实客户端上逐步执行操作，截图留证",
                    },
                    {
                        "stage": 5,
                        "name": "AI 结果分析",
                        "input": "执行日志 + 截图 + 预期结果",
                        "output": "CaseExecutionResult (passed/failed + tags + suggestion)",
                        "tools": ["LLMClient → result_analysis prompt"],
                        "description": "AI 综合判断用例是否通过，生成清洗标签和修复建议",
                    },
                    {
                        "stage": 6,
                        "name": "报告生成",
                        "input": "CaseExecutionResult[]",
                        "output": "cleaned_cases.xlsx + cleaning_report.md + cleaning_report.html",
                        "tools": ["openpyxl", "ReportGenerator"],
                        "description": "生成三种格式的清洗报告",
                    },
                ],
            },
            "run_modes": {
                "demo": {
                    "description": "演示模式，零外部依赖",
                    "requires": ["Python 3.10+", "pip install -r requirements.txt"],
                    "command": "python main.py demo",
                    "output": "outputs/cleaned_cases.xlsx, outputs/cleaning_report.md, outputs/cleaning_report.html",
                },
                "full": {
                    "description": "完整模式，真实执行 + AI 分析",
                    "requires": ["Python 3.10+", "OpenAI API Key", "同花顺远航版客户端", "playwright install chromium"],
                    "command": "export OPENAI_API_KEY=sk-xxx && python main.py full",
                    "output": "同 demo + outputs/screenshots/ + outputs/ai_interaction_log.json",
                },
            },
        }

    def export_json(self, path: Path) -> Path:
        """导出为 JSON"""
        data = self.to_dict()
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info(f"Harness 定义已导出: {path}")
        return path

    def export_markdown(self, path: Path) -> Path:
        """导出为 Markdown 文档"""
        d = self.to_dict()
        meta = d["meta"]
        arch = d["architecture"]
        cfg = d["configuration"]
        pipe = d["pipeline"]
        modes = d["run_modes"]

        lines = [
            f"# {meta['name']}",
            f"",
            f"**版本**: {meta['version']} | **导出时间**: {meta['exported_at']}",
            f"",
            f"> {meta['description']}",
            f"",
            "---",
            "",
            "## 1. 架构概览",
            "",
            f"{arch['overview']}",
            "",
            "## 2. 核心组件",
            "",
            "### 2.1 浏览器引擎",
            "",
            "| 属性 | 值 |",
            "|------|------|",
            f"| 框架 | {arch['components']['browser_engine']['framework']} |",
            f"| 浏览器 | {arch['components']['browser_engine']['browser']} |",
            f"| 模式 | {arch['components']['browser_engine']['mode']} |",
            f"| 连接方式 | {arch['components']['browser_engine']['connection']} |",
            "",
            "### 2.2 AI 引擎",
            "",
            "| 属性 | 值 |",
            "|------|------|",
            f"| 服务商 | {arch['components']['ai_engine']['provider']} |",
            f"| 模型 | {arch['components']['ai_engine']['model']} |",
            f"| 温度 | {arch['components']['ai_engine']['temperature']} |",
            f"| API类型 | {arch['components']['ai_engine']['api_type']} |",
            "",
            "**AI 的 4 个角色**:",
        ]
        for role in arch["components"]["ai_engine"]["roles"]:
            lines.append(f"- {role}")
        lines.extend([
            "",
            "### 2.3 操作执行器",
            "",
            "支持的操作类型:",
            "",
        ])
        for action in arch["components"]["action_executor"]["supported_actions"]:
            lines.append(f"- `{action['type']}`: {action['description']}")
        lines.extend([
            "",
            "元素定位策略:",
            "",
        ])
        for strategy in arch["components"]["action_executor"]["element_strategies"]:
            lines.append(f"- **{strategy['strategy']}**: {strategy['description']}")
        lines.extend([
            "",
            "## 3. 执行配置",
            "",
            "### Playwright",
            f"- 无头模式: {cfg['playwright']['headless']}",
            f"- 超时: {cfg['playwright']['timeout_ms']}ms",
            f"- 每步等待: {cfg['playwright']['wait_after_action_ms']}ms",
            f"- 视口: {cfg['playwright']['viewport']['width']}×{cfg['playwright']['viewport']['height']}",
            "",
            "### 执行策略",
            f"- 最大并发: {cfg['execution']['max_concurrent_cases']}",
            f"- 最大重试: {cfg['execution']['max_retries']}",
            f"- 成功截图: {cfg['execution']['screenshot_on_success']}",
            f"- 失败截图: {cfg['execution']['screenshot_on_failure']}",
            "",
            "## 4. 执行流水线",
            "",
        ])
        for stage in pipe["stages"]:
            lines.append(f"### 阶段 {stage['stage']}: {stage['name']}")
            lines.append(f"- **输入**: {stage['input']}")
            lines.append(f"- **输出**: {stage['output']}")
            lines.append(f"- **工具**: {', '.join(stage['tools'])}")
            lines.append(f"- **说明**: {stage['description']}")
            lines.append("")
        lines.extend([
            "## 5. 运行方式",
            "",
        ])
        for mode_name, mode_info in modes.items():
            lines.append(f"### {mode_name} 模式")
            lines.append(f"{mode_info['description']}")
            lines.append(f"**依赖**: {', '.join(mode_info['requires'])}")
            lines.append(f"**命令**: `{mode_info['command']}`")
            lines.append(f"**输出**: {mode_info['output']}")
            lines.append("")

        path.write_text("\n".join(lines), encoding="utf-8")
        logger.info(f"Harness 文档已导出: {path}")
        return path
