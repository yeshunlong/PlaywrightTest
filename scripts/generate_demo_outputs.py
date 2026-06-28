import sys
import asyncio
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.cleaner.case_cleaner import CaseCleaner
from src.reporter.report_generator import ReportGenerator


def main():
    excel_path = PROJECT_ROOT / "data" / "布局与显示.xlsx"
    if not excel_path.exists():
        print(f"ERROR: Excel file not found: {excel_path}")
        sys.exit(1)

    config = {
        "input": {"excel_path": str(excel_path)},
        "output": {"dir": str(PROJECT_ROOT / "outputs")},
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

    cleaner = CaseCleaner(config)

    async def _run():
        report = await cleaner.run_demo()

        output_dir = PROJECT_ROOT / "outputs"
        reporter = ReportGenerator(output_dir)
        files = reporter.generate_all(report)

        print("\nDemo outputs generated successfully!")
        for name, path in files.items():
            print(f"  {name}: {path}")

        total = report.total_cases
        passed = report.passed_count
        failed = report.failed_count
        rate = f"{passed / total * 100:.1f}%" if total > 0 else "N/A"
        print(f"\nSummary: {total} cases, {passed} passed, {failed} failed ({rate})")

    asyncio.run(_run())


if __name__ == "__main__":
    main()
