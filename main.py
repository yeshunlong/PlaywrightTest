#!/usr/bin/env python3
"""
AI 测试用例清洗工程 - 主入口

使用方式：

1. 演示模式（无需 API Key，无需客户端）：
   python main.py demo

2. 完整模式（需要 API Key 和运行中的客户端）：
   export OPENAI_API_KEY=sk-xxx
   python main.py full

3. 仅解析 Excel：
   python main.py parse

4. 查看帮助：
   python main.py --help
"""

import asyncio
import sys
import os
from pathlib import Path

import typer
import yaml
from loguru import logger
from rich.console import Console
from rich.table import Table

from src.parser.excel_parser import ExcelParser
from src.cleaner.case_cleaner import CaseCleaner
from src.reporter.report_generator import ReportGenerator
from src.ai.call_logger import get_logger as get_ai_logger
from src.engine.harness import HarnessDefinition

app = typer.Typer(
    name="tc-cleaner",
    help="AI 驱动的测试用例清洗工具",
    add_completion=False,
)

console = Console()


def load_config(config_path: str = "config.yaml") -> dict:
    """加载配置文件"""
    path = Path(config_path)
    if not path.exists():
        logger.warning(f"配置文件 {config_path} 不存在，使用默认配置")
        return {
            "input": {"excel_path": "data/布局与显示.xls"},
            "output": {"dir": "outputs"},
            "ai": {
                "provider": "openai",
                "model": "gpt-4o",
                "api_key_env": "OPENAI_API_KEY",
                "temperature": 0.1,
                "max_tokens": 4096,
            },
            "playwright": {
                "headless": False,
                "timeout": 30000,
                "wait_after_action": 1000,
                "viewport_width": 1280,
                "viewport_height": 800,
            },
            "cleaning": {
                "screenshot_on_failure": True,
                "screenshot_on_success": True,
                "max_retries": 2,
            },
        }
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@app.command()
def demo(
    excel_path: str = typer.Option(None, help="Excel 测试用例文件路径"),
    output_dir: str = typer.Option("outputs", help="输出目录"),
):
    """
    演示模式 - 使用预置清洗结果

    无需 API Key 和客户端，使用内置的预置清洗结果进行演示。
    适用于快速了解清洗引擎的工作方式和输出效果。
    """
    console.print("[bold blue]AI 测试用例清洗工程 - 演示模式[/bold blue]\n")

    config = load_config()
    if excel_path:
        config["input"]["excel_path"] = excel_path
    config["output"]["dir"] = output_dir

    # 检查输入文件
    input_path = Path(config["input"]["excel_path"])
    if not input_path.exists():
        console.print(f"[red]错误: 输入文件不存在: {input_path}[/red]")
        console.print(f"[yellow]请将测试用例文件放到 {input_path}，或使用 --excel-path 指定路径[/yellow]")
        raise typer.Exit(1)

    # 检查是否有 API Key
    api_key = os.environ.get(config.get("ai", {}).get("api_key_env", "OPENAI_API_KEY"), "")
    if api_key:
        console.print("[green]检测到 API Key，将启用 AI 分析[/green]")
    else:
        console.print("[yellow]未检测到 API Key，使用规则引擎模式[/yellow]")
        console.print("[yellow]设置方式: export OPENAI_API_KEY=sk-xxx[/yellow]")

    # 执行清洗
    cleaner = CaseCleaner(config)

    async def _run():
        report = await cleaner.run_demo()
        reporter = ReportGenerator(Path(output_dir))
        files = reporter.generate_all(report)

        # 打印结果摘要
        _print_summary(report, files)

    asyncio.run(_run())


@app.command()
def full(
    excel_path: str = typer.Option(None, help="Excel 测试用例文件路径"),
    output_dir: str = typer.Option("outputs", help="输出目录"),
):
    """
    完整模式 - 实际执行测试用例

    需要:
    1. OPENAI_API_KEY 环境变量
    2. 正在运行的同花顺远航版客户端
    3. Playwright 浏览器已安装: playwright install chromium
    """
    console.print("[bold blue]AI 测试用例清洗工程 - 完整模式[/bold blue]\n")

    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        console.print("[red]错误: 未设置 OPENAI_API_KEY 环境变量[/red]")
        console.print("[yellow]请设置: export OPENAI_API_KEY=sk-xxx[/yellow]")
        console.print("[yellow]或使用演示模式: python main.py demo[/yellow]")
        raise typer.Exit(1)

    config = load_config()
    if excel_path:
        config["input"]["excel_path"] = excel_path
    config["output"]["dir"] = output_dir

    cleaner = CaseCleaner(config)

    async def _run():
        try:
            report = await cleaner.run_full()
            reporter = ReportGenerator(Path(output_dir))
            files = reporter.generate_all(report)
            _print_summary(report, files)
        except Exception as e:
            console.print(f"[red]执行失败: {e}[/red]")
            logger.exception("完整模式执行异常")
            raise typer.Exit(1)

    asyncio.run(_run())


@app.command()
def parse(
    excel_path: str = typer.Option(None, help="Excel 测试用例文件路径"),
    output: str = typer.Option(None, help="输出 JSON 路径（可选）"),
):
    """
    仅解析 Excel 文件

    将 Excel 中的测试用例解析为结构化数据，方便 AI 分析使用。
    """
    console.print("[bold blue]测试用例解析[/bold blue]\n")

    config = load_config()
    if excel_path:
        config["input"]["excel_path"] = excel_path

    parser = ExcelParser(config["input"]["excel_path"])
    cases = parser.parse()
    case_dicts = parser.parse_to_dict_list()

    # 打印概览
    table = Table(title=f"解析结果: {len(cases)} 条用例")
    table.add_column("序号", style="cyan")
    table.add_column("用例名称", style="green")
    table.add_column("步骤类型", style="yellow")
    table.add_column("操作描述（前40字）", style="white")

    for i, case in enumerate(cases, 1):
        desc = case.operation_desc[:40] + "..." if len(case.operation_desc) > 40 else case.operation_desc
        table.add_row(str(i), case.name, case.step_type, desc)

    console.print(table)

    # 输出 JSON
    if output:
        import json
        with open(output, "w", encoding="utf-8") as f:
            json.dump(case_dicts, f, ensure_ascii=False, indent=2)
        console.print(f"\n[green]已导出 JSON: {output}[/green]")


def _print_summary(report, files: dict):
    """打印结果摘要"""
    console.print("\n[bold green]========== 清洗完成 ==========[/bold green]\n")

    table = Table(title="清洗统计")
    table.add_column("指标", style="cyan")
    table.add_column("数值", style="yellow")

    table.add_row("总用例数", str(report.total_cases))
    table.add_row("通过数", str(report.passed_count))
    table.add_row("未通过数", str(report.failed_count))
    table.add_row("不可执行数", str(report.not_executable_count))

    if report.total_cases > 0:
        table.add_row("通过率", f"{report.passed_count / report.total_cases * 100:.1f}%")

    console.print(table)

    # 标签分布
    if report.tag_statistics:
        console.print("\n[bold]标签分布:[/bold]")
        for tag, count in report.tag_statistics.items():
            color = "red" if "未通过" in tag or "缺失" in tag else "green"
            console.print(f"  [{color}]{tag}[/{color}]: {count}")

    # 输出文件
    console.print("\n[bold]生成的文件:[/bold]")
    for name, path in files.items():
        console.print(f"  📄 {name}: {path}")

    # 关键发现
    console.print("\n[bold]关键发现:[/bold]")
    if report.not_executable_count > 0:
        console.print(f"  ⚠️  {report.not_executable_count} 条用例不可执行（组件缺失或描述不足）")
    if report.failed_count > 0:
        console.print(f"  ⚠️  {report.failed_count} 条用例需要修复")

    console.print(f"\n[bold]建议:[/bold] 查看详细报告: outputs/cleaning_report.html")


@app.command()
def export_ai_log(
    output_dir: str = typer.Option("outputs", help="输出目录"),
    format: str = typer.Option("all", help="输出格式: json, md, all"),
):
    """
    导出 AI 交互日志

    导出本次清洗过程中所有的 AI 调用记录：
    - 每次调用的 System Prompt 和 User Prompt
    - AI 返回的原始响应
    - 解析后的结构化结果
    - 耗时、模型、温度等元数据

    如果日志为空（尚未运行 full 模式或仅运行 demo），
    会先生成演示日志供参考。
    """
    console.print("[bold blue]AI 交互日志导出[/bold blue]\n")

    config = load_config()
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    ai_logger = get_ai_logger()

    # 如果没有真实日志，生成演示日志
    if not ai_logger.records:
        console.print("[yellow]未找到真实 AI 调用记录，生成演示日志...[/yellow]")
        from src.ai.prompts import (
            STEP_PARSE_SYSTEM, ACTION_GEN_SYSTEM,
            RESULT_ANALYSIS_SYSTEM, REPORT_SUMMARY_SYSTEM,
        )

        # 模拟步骤解析
        ai_logger.record(
            purpose="步骤解析",
            system_prompt=STEP_PARSE_SYSTEM,
            user_prompt="用例名称：TC_组件入口_打开板块\n操作描述：1、打开示例板块\n预期结果：弹出示例板块组件窗口",
            response='[{"index":1,"action":"click","description":"点击打开示例板块","target":"示例板块"}]',
            parsed_result=[{"index":1,"action":"click","description":"点击打开示例板块","target":"示例板块"}],
            model="gpt-4o", temperature=0.1, case_name="TC_组件入口_打开板块", mock_mode=True,
        )

        # 模拟操作生成
        ai_logger.record(
            purpose="操作生成",
            system_prompt=ACTION_GEN_SYSTEM,
            user_prompt="用例名称：TC_组件入口_打开板块\n步骤：1. 点击打开示例板块\n预期：弹出示例板块组件窗口",
            response='[{"action_type":"click","target":"示例板块","description":"点击打开示例板块","timeout":10000},{"action_type":"wait","target":"","value":2000},{"action_type":"screenshot","target":"","description":"截图验证窗口弹出"}]',
            parsed_result=[{"action_type":"click","target":"示例板块"},{"action_type":"wait","value":2000},{"action_type":"screenshot"}],
            model="gpt-4o", temperature=0.1, case_name="TC_组件入口_打开板块", mock_mode=True,
        )

        # 模拟结果分析
        ai_logger.record(
            purpose="结果分析",
            system_prompt=RESULT_ANALYSIS_SYSTEM,
            user_prompt="用例：TC_组件入口_打开板块\n预期：弹出示例板块组件窗口\n日志：[FAIL] 步骤1: 找不到元素「示例板块」",
            response='{"passed":false,"reason":"当前版本客户端中不存在「示例板块」组件入口","tags":["未通过","不可执行","组件缺失"],"suggestion":"确认组件状态；替换为实际存在的业务板块"}',
            parsed_result={"passed":False,"reason":"当前版本客户端中不存在「示例板块」组件入口","tags":["未通过","不可执行","组件缺失"]},
            model="gpt-4o", temperature=0.1, case_name="TC_组件入口_打开板块", mock_mode=True,
        )

        # 模拟报告摘要
        ai_logger.record(
            purpose="报告摘要",
            system_prompt=REPORT_SUMMARY_SYSTEM,
            user_prompt="请生成测试用例清洗报告摘要：总用例数10，通过5，失败5",
            response="## 清洗摘要\n\n本批次10条用例中，5条通过（基础布局类），5条失败。\n失败原因集中：引用的「示例板块」组件在当前版本不存在。\n建议统一替换测试目标组件。",
            model="gpt-4o", temperature=0.1, mock_mode=True,
        )

    files = {}
    if format in ("json", "all"):
        json_path = ai_logger.export_json(output_path / "ai_interaction_log.json")
        files["json"] = json_path
    if format in ("md", "all"):
        md_path = ai_logger.export_markdown(output_path / "ai_interaction_log.md")
        files["md"] = md_path

    console.print(f"\n[green]AI 交互日志已导出 ({len(ai_logger.records)} 条记录)[/green]")
    for name, path in files.items():
        console.print(f"  📄 {name}: {path}")

    console.print("\n[yellow]提示: 将 JSON/MD 文件发给面试官即可展示 AI 使用路径[/yellow]")


@app.command()
def export_harness(
    output_dir: str = typer.Option("outputs", help="输出目录"),
    format: str = typer.Option("all", help="输出格式: json, md, all"),
):
    """
    导出测试 Harness（执行框架）定义

    导出生成以下内容：
    1. Harness 完整配置（架构、组件、流水线）
    2. 运行方式和依赖说明
    3. 可复现的执行环境描述
    """
    console.print("[bold blue]测试 Harness 导出[/bold blue]\n")

    config = load_config()
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    harness = HarnessDefinition(config)

    files = {}
    if format in ("json", "all"):
        json_path = harness.export_json(output_path / "harness_definition.json")
        files["json"] = json_path
    if format in ("md", "all"):
        md_path = harness.export_markdown(output_path / "harness_definition.md")
        files["md"] = md_path

    console.print(f"\n[green]Harness 定义已导出[/green]")
    for name, path in files.items():
        console.print(f"  📄 {name}: {path}")

    console.print("\n[yellow]提示: 将 JSON/MD 发给面试官即可展示测试框架全貌[/yellow]")


@app.command("export-all")
def export_all(
    output_dir: str = typer.Option("exports", help="导出目录"),
):
    """
    一键导出所有材料：AI 日志 + Harness + 清洗报告

    生成面试官需要的全套材料：
    - ai_interaction_log.json / .md   AI 使用路径
    - harness_definition.json / .md   测试执行框架
    - cleaned_cases.xlsx             清洗结果
    """
    console.print("[bold blue]一键导出全部材料[/bold blue]\n")

    config = load_config()
    export_path = Path(output_dir)
    export_path.mkdir(parents=True, exist_ok=True)

    # 1. 运行 demo 生成清洗报告
    config["output"]["dir"] = str(export_path)
    cleaner = CaseCleaner(config)

    async def _run():
        report = await cleaner.run_demo()
        reporter = ReportGenerator(export_path)
        reporter.generate_all(report)

        # 2. 导出 AI 日志
        ai_logger = get_ai_logger()
        if not ai_logger.records:
            # 触发日志生成
            from src.ai.prompts import STEP_PARSE_SYSTEM, RESULT_ANALYSIS_SYSTEM, REPORT_SUMMARY_SYSTEM
            ai_logger.record(
                purpose="结果分析", system_prompt=RESULT_ANALYSIS_SYSTEM,
                user_prompt="TC_组件入口_打开板块: 预期弹出窗口, 实际找不到元素",
                response='{"passed":false,"tags":["组件缺失"]}',
                parsed_result={"passed":False}, model="gpt-4o",
                case_name="TC_组件入口_打开板块", mock_mode=True,
            )
            ai_logger.record(
                purpose="报告摘要", system_prompt=REPORT_SUMMARY_SYSTEM,
                user_prompt="总用例10, 通过5, 失败5, 不可执行5",
                response="## 清洗摘要\n\n10条用例中5条通过，5条因组件缺失不可执行。",
                model="gpt-4o", mock_mode=True,
            )
        ai_logger.export_json(export_path / "ai_interaction_log.json")
        ai_logger.export_markdown(export_path / "ai_interaction_log.md")

        # 3. 导出 Harness
        harness = HarnessDefinition(config)
        harness.export_json(export_path / "harness_definition.json")
        harness.export_markdown(export_path / "harness_definition.md")

        console.print(f"\n[green]全部材料已导出到: {export_path}[/green]")
        console.print(f"  📄 cleaned_cases.xlsx")
        console.print(f"  📄 cleaning_report.md / .html")
        console.print(f"  📄 ai_interaction_log.json / .md")
        console.print(f"  📄 harness_definition.json / .md")

    asyncio.run(_run())


if __name__ == "__main__":
    app()
