"""
Playwright 执行引擎

负责：
1. 连接到同花顺远航版客户端窗口
2. 执行 AI 生成的 Playwright 操作指令
3. 记录执行日志和截图
4. 返回结构化的执行结果

支持两种模式：
- 真实执行模式：通过 Playwright 连接到实际客户端
- 演示/回放模式：使用预录制的执行结果（用于演示和 CI）
"""

import json
import time
import asyncio
from pathlib import Path
from typing import Any, Optional
from datetime import datetime

from loguru import logger
from playwright.async_api import async_playwright, Page, Browser, BrowserContext

from src import TestCase, StepExecutionResult, CaseExecutionResult, PlaywrightAction


class PlaywrightRunner:
    """Playwright 测试执行器"""

    def __init__(self, config: dict):
        self.config = config
        pw_cfg = config.get("playwright", {})
        self.headless = pw_cfg.get("headless", False)
        self.timeout = pw_cfg.get("timeout", 30000)
        self.wait_after = pw_cfg.get("wait_after_action", 1000)
        self.viewport = {
            "width": pw_cfg.get("viewport_width", 1280),
            "height": pw_cfg.get("viewport_height", 800),
        }
        self.screenshots_dir = Path(config.get("output", {}).get("dir", "outputs")) / "screenshots"

        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    async def start(self) -> "PlaywrightRunner":
        """启动浏览器"""
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)

        logger.info("启动 Playwright 浏览器...")
        self.playwright = await async_playwright().start()

        launch_options = {
            "headless": self.headless,
            "args": ["--start-maximized"],
        }

        # 如果指定了可执行路径
        exe_path = self.config.get("playwright", {}).get("executable_path", "")
        if exe_path:
            launch_options["executable_path"] = exe_path

        self.browser = await self.playwright.chromium.launch(**launch_options)
        self.context = await self.browser.new_context(
            viewport=self.viewport,
            no_viewport=False,
        )
        self.page = await self.context.new_page()
        self.page.set_default_timeout(self.timeout)

        logger.info("Playwright 浏览器已启动")
        return self

    async def stop(self):
        """关闭浏览器"""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        logger.info("Playwright 浏览器已关闭")

    async def execute_case(self, case: TestCase, actions: list[dict]) -> CaseExecutionResult:
        """执行单个用例"""
        case_start = time.time()
        step_results: list[StepExecutionResult] = []
        screenshots: list[str] = []

        try:
            # 等待应用窗口稳定
            await self.page.wait_for_timeout(self.wait_after)

            for i, action_dict in enumerate(actions):
                step_start = time.time()
                action = PlaywrightAction(**action_dict)

                try:
                    logger.info(f"  执行步骤 {i+1}/{len(actions)}: {action.action_type} -> {action.target or action.description}")

                    screenshot_path = await self._execute_action(action, case.case_id, i)

                    elapsed = int((time.time() - step_start) * 1000)
                    sr = StepExecutionResult(
                        step_index=i + 1,
                        status="passed",
                        duration_ms=elapsed,
                        screenshot_path=str(screenshot_path) if screenshot_path else None,
                    )
                    step_results.append(sr)

                except Exception as step_err:
                    elapsed = int((time.time() - step_start) * 1000)
                    logger.warning(f"  步骤 {i+1} 执行失败: {step_err}")

                    # 失败时截图
                    screenshot_path = self.screenshots_dir / f"{case.case_id}_step{i+1}_error.png"
                    try:
                        await self.page.screenshot(path=str(screenshot_path), full_page=False)
                    except Exception:
                        screenshot_path = None

                    sr = StepExecutionResult(
                        step_index=i + 1,
                        status="failed",
                        duration_ms=elapsed,
                        screenshot_path=str(screenshot_path) if screenshot_path else None,
                        error_message=str(step_err),
                    )
                    step_results.append(sr)

            total_duration = int((time.time() - case_start) * 1000)

            # 成功截图
            if self.config.get("cleaning", {}).get("screenshot_on_success", True):
                success_path = self.screenshots_dir / f"{case.case_id}_final.png"
                try:
                    await self.page.screenshot(path=str(success_path), full_page=True)
                    screenshots.append(str(success_path))
                except Exception:
                    pass

            # 判断整体是否通过
            all_passed = all(s.status == "passed" for s in step_results)
            return CaseExecutionResult(
                case=case,
                passed=all_passed,
                reason="所有步骤执行成功" if all_passed else "部分步骤执行失败",
                step_results=step_results,
                total_duration_ms=total_duration,
                screenshots=screenshots,
            )

        except Exception as e:
            total_duration = int((time.time() - case_start) * 1000)
            logger.error(f"用例执行异常: {case.case_id} - {e}")
            return CaseExecutionResult(
                case=case,
                passed=False,
                reason=f"执行异常: {e}",
                step_results=step_results,
                total_duration_ms=total_duration,
            )

    async def _execute_action(
        self, action: PlaywrightAction, case_id: str, step_idx: int
    ) -> Optional[Path]:
        """执行单个 Playwright 操作"""
        a = action
        screenshot_path = None

        if a.action_type == "click":
            await self._click_target(a.target, a.timeout)

        elif a.action_type == "dblclick":
            await self._click_target(a.target, a.timeout, double=True)

        elif a.action_type == "input":
            if a.target:
                await self._type_text(a.target, a.value or "", a.timeout)

        elif a.action_type == "wait":
            ms = int(a.value) if a.value and str(a.value).isdigit() else self.wait_after
            await self.page.wait_for_timeout(ms)

        elif a.action_type == "screenshot" or a.action_type == "observe":
            filename = f"{case_id}_step{step_idx}.png"
            path = self.screenshots_dir / filename
            await self.page.screenshot(path=str(path), full_page=True)
            screenshot_path = path

        elif a.action_type == "assert":
            await self._execute_assert(a.target, a.value)

        elif a.action_type == "scroll":
            direction = a.value or "down"
            await self._scroll(direction)

        elif a.action_type == "hover":
            await self._hover_target(a.target, a.timeout)

        elif a.action_type == "navigate":
            if a.value:
                await self.page.goto(a.value, wait_until="domcontentloaded")

        elif a.action_type == "resize":
            # 模拟窗口缩放
            width = a.params.get("width", self.viewport["width"])
            height = a.params.get("height", self.viewport["height"])
            await self.page.set_viewport_size({"width": width, "height": height})

        await self.page.wait_for_timeout(self.wait_after)
        return screenshot_path

    async def _click_target(self, target: str, timeout: int, double: bool = False):
        """点击目标元素"""
        logger.debug(f"    查找并点击: {target}")
        try:
            # 按文本查找
            locator = self.page.get_by_text(target, exact=False).first
            await locator.wait_for(state="visible", timeout=timeout)
            if double:
                await locator.dblclick()
            else:
                await locator.click()
        except Exception:
            # 按 role 查找
            try:
                locator = self.page.get_by_role("button", name=target)
                await locator.wait_for(state="visible", timeout=timeout)
                if double:
                    await locator.dblclick()
                else:
                    await locator.click()
            except Exception:
                # 按 menuitem 查找
                locator = self.page.get_by_role("menuitem", name=target)
                await locator.wait_for(state="visible", timeout=timeout)
                if double:
                    await locator.dblclick()
                else:
                    await locator.click()

    async def _type_text(self, target: str, text: str, timeout: int):
        """输入文本"""
        try:
            locator = self.page.get_by_placeholder(target)
            await locator.fill(text, timeout=timeout)
        except Exception:
            locator = self.page.get_by_label(target)
            await locator.fill(text, timeout=timeout)

    async def _execute_assert(self, target: str, expected: str = None):
        """执行断言"""
        logger.debug(f"    断言检查: {target}")

        # 检查文本是否存在
        if expected:
            await self.page.get_by_text(expected).first.wait_for(
                state="visible", timeout=self.timeout
            )
        else:
            # 检查 target 描述的文本是否存在
            await self.page.get_by_text(target).first.wait_for(
                state="visible", timeout=self.timeout
            )

    async def _scroll(self, direction: str):
        """滚动页面"""
        scroll_map = {
            "up": {"deltaY": -300},
            "down": {"deltaY": 300},
            "left": {"deltaX": -300},
            "right": {"deltaX": 300},
        }
        opts = scroll_map.get(direction, {"deltaY": 300})
        await self.page.mouse.wheel(**opts)

    async def _hover_target(self, target: str, timeout: int):
        """悬停在目标元素上"""
        try:
            locator = self.page.get_by_text(target, exact=False).first
            await locator.wait_for(state="visible", timeout=timeout)
            await locator.hover()
        except Exception:
            locator = self.page.get_by_role("button", name=target)
            await locator.wait_for(state="visible", timeout=timeout)
            await locator.hover()

    def generate_execution_log(self, case: TestCase, step_results: list[StepExecutionResult]) -> str:
        """生成执行日志文本（供 AI 分析）"""
        lines = [
            f"用例: {case.name} ({case.case_id})",
            f"操作描述: {case.operation_desc}",
            f"预期结果: {case.expected_result}",
            "",
            "执行记录:",
        ]
        for sr in step_results:
            status_icon = "[OK]" if sr.status == "passed" else "[FAIL]"
            lines.append(f"  {status_icon} 步骤{sr.step_index}: 耗时{sr.duration_ms}ms")
            if sr.error_message:
                lines.append(f"    错误: {sr.error_message}")
        return "\n".join(lines)
