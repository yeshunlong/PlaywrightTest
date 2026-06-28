"""
测试用例清洗核心引擎

这是整个项目的核心模块，实现了完整的清洗流程：

清洗流程:
1. 解析阶段：解析 Excel，提取测试用例
2. 分析阶段：AI 分析用例描述清晰度和完整性
3. 转换阶段：将自然语言步骤转换为 Playwright 操作指令
4. 执行阶段：通过 Playwright 在真实客户端上执行操作
5. 验证阶段：AI 分析截图和执行日志，判断通过与否
6. 清洗阶段：标记问题用例，生成清洗标签和建议
7. 输出阶段：生成清洗后的 Excel 和详细报告

支持两种运行模式：
- full: 完整模式，需要 API Key 和实际客户端
- demo: 演示模式，使用预置结果，无需外部依赖
"""

import asyncio
import time
from pathlib import Path
from typing import Optional

from loguru import logger

from src import (
    TestCase,
    CaseExecutionResult,
    CleaningReport,
)
from src.parser.excel_parser import ExcelParser
from src.ai.llm_client import LLMClient
from src.engine.action_generator import ActionGenerator
from src.engine.playwright_runner import PlaywrightRunner


class CaseCleaner:
    """用例清洗引擎"""

    def __init__(self, config: dict):
        self.config = config
        self.llm = LLMClient(config)
        self.runner: Optional[PlaywrightRunner] = None
        self.action_gen = ActionGenerator(llm_client=self.llm)
        self.parser = ExcelParser(config["input"]["excel_path"])

    async def run_full(self) -> CleaningReport:
        """完整清洗流程：解析 -> 生成 -> 执行 -> 分析 -> 清洗"""
        logger.info("=" * 60)
        logger.info("开始完整测试用例清洗流程")
        logger.info("=" * 60)

        # 1. 解析 Excel
        logger.info("[阶段 1/6] 解析 Excel 文件...")
        cases = self.parser.parse()
        logger.info(f"  解析到 {len(cases)} 条用例")

        # 2. AI 分析步骤并生成操作指令
        logger.info("[阶段 2/6] AI 分析用例并生成操作指令...")
        case_actions: list[tuple[TestCase, list[dict]]] = []
        for case in cases:
            actions = self.action_gen.generate_for_case(case)
            case_actions.append((case, actions))
            logger.info(f"  {case.name}: 生成 {len(actions)} 个操作")

        # 3. 启动 Playwright
        logger.info("[阶段 3/6] 启动 Playwright 执行引擎...")
        self.runner = PlaywrightRunner(self.config)
        await self.runner.start()

        # 4. 执行测试用例
        logger.info("[阶段 4/6] 执行测试用例...")
        raw_results: list[CaseExecutionResult] = []
        for case, actions in case_actions:
            logger.info(f"  执行: {case.name}")
            result = await self.runner.execute_case(case, actions)
            raw_results.append(result)
            status = "PASS" if result.passed else "FAIL"
            logger.info(f"    [{status}] {result.reason}")

        # 5. AI 分析执行结果
        logger.info("[阶段 5/6] AI 分析执行结果并生成清洗标签...")
        cleaned_results: list[CaseExecutionResult] = []
        for result in raw_results:
            execution_log = self.runner.generate_execution_log(result.case, result.step_results)
            analysis = self.llm.analyze_result(
                case_name=result.case.name,
                expected_result=result.case.expected_result,
                execution_log=execution_log,
            )

            result.passed = analysis.get("passed", result.passed)
            result.reason = analysis.get("reason", result.reason)
            result.tags = analysis.get("tags", [])
            result.ai_suggestion = analysis.get("suggestion", "")

            cleaned_results.append(result)
            logger.info(f"  {result.case.name}: {'通过' if result.passed else '未通过'} | 标签: {result.tags}")

        # 6. 生成报告
        logger.info("[阶段 6/6] 生成清洗报告...")
        report = self._build_report(cleaned_results)

        # 7. 关闭浏览器
        if self.runner:
            await self.runner.stop()

        logger.info(f"清洗完成: {report.passed_count}通过 / {report.failed_count}未通过 / {report.not_executable_count}不可执行")
        return report

    async def run_demo(self) -> CleaningReport:
        """
        演示模式：使用预置的清洗结果，无需 API Key 和客户端。

        读取预制的清洗结果并生成报告。
        适用于演示、CI 环境和快速验证清洗逻辑。
        """
        logger.info("=" * 60)
        logger.info("开始演示模式清洗流程（使用预置结果）")
        logger.info("=" * 60)

        # 1. 解析 Excel
        logger.info("[阶段 1/4] 解析 Excel 文件...")
        cases = self.parser.parse()
        logger.info(f"  解析到 {len(cases)} 条用例")

        # 2. 生成操作指令（规则模式）
        logger.info("[阶段 2/4] 生成操作指令（规则模式）...")
        for case in cases:
            actions = self.action_gen.generate_for_case(case)
            logger.info(f"  {case.name}: 生成 {len(actions)} 个操作")

        # 3. 使用预置的清洗结果
        logger.info("[阶段 3/4] 加载预置清洗结果...")
        results = self._load_demo_results(cases)

        # 4. 生成报告
        logger.info("[阶段 4/4] 生成清洗报告...")
        report = self._build_report(results)

        passed = report.passed_count
        failed = report.failed_count
        logger.info(f"清洗完成: {passed}通过 / {failed}未通过")
        return report

    def _load_demo_results(self, cases: list[TestCase]) -> list[CaseExecutionResult]:
        """
        加载预置的演示结果。

        这些结果来自预先在实际客户端上执行后的 AI 分析。
        演示了清洗的核心价值：识别过期用例（组件不存在）、
        验证可执行性、评估预期一致性。
        """
        # 预置的演示结果映射
        DEMO_RESULTS = {
            "TC_组件窗口_基础布局": {
                "passed": True,
                "reason": "窗口布局要素完整：标题栏、内容区、菜单按钮均显示正常",
                "tags": ["通过", "可执行"],
                "suggestion": "",
            },
            "TC_组件窗口_默认尺寸": {
                "passed": True,
                "reason": "窗口以默认尺寸打开，内容区域完整显示，无遮挡",
                "tags": ["通过", "可执行"],
                "suggestion": "",
            },
            "TC_导航栏_标签显示": {
                "passed": True,
                "reason": "导航栏标签正常显示，选中状态、高亮、切换刷新均符合预期",
                "tags": ["通过", "可执行"],
                "suggestion": "",
            },
            "TC_列表区域_基础显示": {
                "passed": True,
                "reason": "左侧分类列表、右侧明细区域显示正常，分类切换后明细刷新正确",
                "tags": ["通过", "可执行"],
                "suggestion": "",
            },
            "TC_窗口缩放_横向拉伸": {
                "passed": True,
                "reason": "窗口拉伸后内容区域自适应扩展，控件布局正常，无重叠",
                "tags": ["通过", "可执行"],
                "suggestion": "",
            },
            "TC_组件入口_打开板块": {
                "passed": False,
                "reason": "当前版本客户端中不存在「示例板块」组件入口。\n该用例引用的组件已被移除或重命名，导致测试步骤无法执行。",
                "tags": ["未通过", "不可执行", "组件缺失"],
                "suggestion": "建议：1) 确认「示例板块」组件在当前版本中是否已下线；\n"
                            "2) 如果组件已重命名，更新操作描述中的组件名称；\n"
                            "3) 如果组件已下线，标记此用例为「已废弃」或删除。\n"
                            "4) 使用实际存在的业务板块（如「行情中心」-「板块指数」）替换测试目标。",
            },
            "TC_导航栏_默认选中项": {
                "passed": False,
                "reason": "当前版本无「示例板块」组件，因此无法验证导航栏默认选中项。\n"
                        "即使存在该组件，默认选中标签也可能随版本变化。",
                "tags": ["未通过", "不可执行", "组件缺失"],
                "suggestion": "建议：1) 将测试目标替换为实际存在的组件；\n"
                            "2) 将预期结果中的明确标签名（「地域指数」）改为验证'存在默认选中项且高亮'，避免标签名硬编码。",
            },
            "TC_右上角菜单_分组设置": {
                "passed": False,
                "reason": "当前版本无「示例板块」组件，无法验证其菜单功能。\n"
                        "此外，菜单项名称可能已变更（「设置组件分组」vs 当前命名）。",
                "tags": ["未通过", "不可执行", "组件缺失", "预期不一致"],
                "suggestion": "建议：1) 替换测试目标为实际存在的组件；\n"
                            "2) 验证菜单项名称是否与当前版本一致；\n"
                            "3) 将预期结果改为'菜单中包含分组相关设置项'以降低维护成本。",
            },
            "TC_窗口最小宽度_校验": {
                "passed": False,
                "reason": "当前版本无「示例板块」组件，无法验证其窗口最小宽度。\n"
                        "建议使用实际存在的组件窗口进行最小宽度校验。",
                "tags": ["未通过", "不可执行", "组件缺失"],
                "suggestion": "建议：1) 替换为目标组件（如「板块指数」窗口）；\n"
                            "2) 预期结果应量化最小宽度值（如'窗口最小宽度≥400px'）。",
            },
            "TC_列表刷新_切换分类": {
                "passed": False,
                "reason": "当前版本无「示例板块」组件，无法验证列表刷新功能。\n"
                        "预期结果中提到与「行情中心」保持一致，属于跨模块依赖校验，增加了维护成本。",
                "tags": ["未通过", "不可执行", "组件缺失", "预期不一致"],
                "suggestion": "建议：1) 替换测试目标组件；\n"
                            "2) 解耦与行情中心的依赖，改为验证'切换后明细列表数据有变化'即可；\n"
                            "3) 如果需要精确的颜色/数量/排序校验，建议使用独立的接口级自动化测试。",
            },
        }

        results: list[CaseExecutionResult] = []
        for case in cases:
            preset = DEMO_RESULTS.get(
                case.case_id,
                {
                    "passed": True,
                    "reason": "未找到预置结果，默认标记为通过（需人工复查）",
                    "tags": ["通过"],
                    "suggestion": "请手动执行此用例后确认结果",
                },
            )

            result = CaseExecutionResult(
                case=case,
                passed=preset["passed"],
                reason=preset["reason"],
                tags=preset["tags"],
                ai_suggestion=preset["suggestion"],
            )
            results.append(result)

        return results

    def _build_report(self, results: list[CaseExecutionResult]) -> CleaningReport:
        """构建清洗报告"""
        total = len(results)
        passed = sum(1 for r in results if r.passed)
        failed = sum(1 for r in results if not r.passed)
        not_executable = sum(1 for r in results if "不可执行" in r.tags)

        # 统计标签分布
        tag_stats: dict[str, int] = {}
        for r in results:
            for tag in r.tags:
                tag_stats[tag] = tag_stats.get(tag, 0) + 1

        report = CleaningReport(
            total_cases=total,
            passed_count=passed,
            failed_count=failed,
            not_executable_count=not_executable,
            tag_statistics=tag_stats,
            results=results,
        )

        # AI 生成摘要
        try:
            stats = {
                "total": total,
                "passed": passed,
                "failed": failed,
                "not_executable": not_executable,
                "tag_stats": tag_stats,
                "failure_details": self._format_failure_details(results),
                "module_name": results[0].case.category if results else "",
            }
            summary = self.llm.generate_summary(stats)
            if not summary or summary.strip() in ("", "{}"):
                report.summary = self._generate_fallback_summary(report)
            else:
                report.summary = summary
        except Exception as e:
            logger.warning(f"AI 摘要生成失败: {e}")
            report.summary = self._generate_fallback_summary(report)

        report.suggestions = self._collect_suggestions(results)
        return report

    @staticmethod
    def _format_failure_details(results: list[CaseExecutionResult]) -> str:
        """格式化失败用例详情"""
        failures = [r for r in results if not r.passed]
        if not failures:
            return "无失败用例"

        lines = []
        for r in failures:
            lines.append(
                f"- {r.case.name}: {r.reason}\n  标签: {', '.join(r.tags)}"
            )
        return "\n".join(lines)

    @staticmethod
    def _collect_suggestions(results: list[CaseExecutionResult]) -> list[str]:
        """收集所有修复建议"""
        suggestions = []
        for r in results:
            if r.ai_suggestion:
                suggestions.append(f"【{r.case.name}】{r.ai_suggestion}")
        return suggestions

    @staticmethod
    def _generate_fallback_summary(report: CleaningReport) -> str:
        """生成备用摘要（当 AI 不可用时）"""
        total = report.total_cases
        passed = report.passed_count
        failed = report.failed_count
        rate = f"{passed / total * 100:.1f}%" if total > 0 else "N/A"

        return f"""## 清洗摘要

### 总体情况
- 总用例数：{total}
- 通过数：{passed}
- 未通过数：{failed}
- 通过率：{rate}

### 问题分类
{chr(10).join(f'- {tag}: {count}条' for tag, count in report.tag_statistics.items())}

### 关键发现
1. 通过率 {rate}，需关注未通过用例的修复。
2. 存在 {report.not_executable_count} 条不可执行用例，需要与产品和开发确认组件状态。
3. 建议对不可执行用例进行分类处理：废弃、更新或替换测试目标。

### 改进建议
- 定期（建议每版本/每月）执行用例清洗，避免用例腐化
- 对预期结果中硬编码的具体值（如标签名、菜单名）进行参数化
- 将跨模块依赖的校验项解耦，降低维护成本
"""
