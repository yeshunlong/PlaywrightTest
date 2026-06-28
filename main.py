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


if __name__ == "__main__":
    app()
