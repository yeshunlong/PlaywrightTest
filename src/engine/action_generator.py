"""
操作生成器

将测试用例转换为具体的 Playwright 操作指令。

支持两种模式：
1. AI 生成模式：使用 LLM 分析用例并生成操作
2. 规则生成模式：使用预定义模板快速生成（用于演示/回放）
"""

from loguru import logger

from src import TestCase
from src.ai.llm_client import LLMClient


class ActionGenerator:
    """操作指令生成器"""

    def __init__(self, llm_client: LLMClient = None):
        self.llm = llm_client

    def generate_for_case(self, case: TestCase) -> list[dict]:
        """为单个用例生成 Playwright 操作指令列表"""
        if self.llm and not self.llm.mock_mode:
            return self._ai_generate(case)
        else:
            return self._rule_generate(case)

    def _ai_generate(self, case: TestCase) -> list[dict]:
        """使用 AI 生成操作指令"""
        case_dict = {
            "用例名称": case.name,
            "操作描述": case.operation_desc,
            "预期结果": case.expected_result,
            "前置条件": case.inner_precondition or case.macro_precondition,
            "步骤类型": case.step_type,
        }
        actions = self.llm.generate_actions(case_dict)
        logger.info(f"  AI 生成 {len(actions)} 个操作指令")
        return actions

    def _rule_generate(self, case: TestCase) -> list[dict]:
        """使用规则引擎生成操作指令（无需 AI API Key）"""
        desc = case.operation_desc
        expected = case.expected_result
        step_type = case.step_type
        case_name = case.name
        actions: list[dict] = []

        # 从操作描述中提取关键元素
        # 匹配菜单路径模式：【xxx】-【yyy】
        import re

        menu_pattern = re.findall(r"【(.+?)】", desc)
        menu_path = menu_pattern  # 例如 ["通用工具", "示例板块"]

        # 根据步骤类型生成不同的操作模板
        if "打开" in step_type or "组件入口" in case_name:
            if menu_path:
                for i, menu in enumerate(menu_path):
                    actions.append({
                        "action_type": "click",
                        "target": menu,
                        "description": f"点击【{menu}】",
                        "timeout": 10000,
                    })
                    if i < len(menu_path) - 1:
                        actions.append({
                            "action_type": "wait",
                            "target": "",
                            "value": 2000,
                            "description": "等待子菜单展开",
                        })
            actions.append({
                "action_type": "wait",
                "target": "",
                "value": 2000,
                "description": "等待窗口加载",
            })
            actions.append({
                "action_type": "screenshot",
                "target": "",
                "description": "截图验证",
            })

        elif "观察" in step_type or "观察" in desc or "查看" in desc:
            actions.append({
                "action_type": "wait",
                "target": "",
                "value": 2000,
                "description": "等待界面渲染完成",
            })
            actions.append({
                "action_type": "screenshot",
                "target": "",
                "description": "截取当前界面用于验证",
            })

        elif "拖动" in desc or "拉伸" in desc or "压缩" in desc:
            # 窗口缩放操作
            if "向右" in desc or "横向" in desc:
                actions.append({
                    "action_type": "resize",
                    "target": "",
                    "value": "wider",
                    "params": {"width": 1600, "height": 800},
                    "description": "横向拉伸窗口",
                })
            elif "压缩" in desc or "最小" in desc:
                actions.append({
                    "action_type": "resize",
                    "target": "",
                    "value": "narrower",
                    "params": {"width": 400, "height": 800},
                    "description": "横向压缩窗口",
                })
            actions.append({
                "action_type": "screenshot",
                "target": "",
                "description": "截图观察窗口变化",
            })

        elif "点击" in desc or "切换" in desc:
            # 提取点击目标
            click_targets = re.findall(r"点击(.+?)(?:[,，\n\r]|$)", desc)
            if not click_targets:
                click_targets = re.findall(r"切换(.+?)(?:[,，\n\r]|$)", desc)
            for target in click_targets:
                actions.append({
                    "action_type": "click",
                    "target": target.strip(),
                    "description": f"点击 {target.strip()}",
                    "timeout": 10000,
                })
                actions.append({
                    "action_type": "wait",
                    "target": "",
                    "value": 2000,
                    "description": "等待响应",
                })
            actions.append({
                "action_type": "screenshot",
                "target": "",
                "description": "截图验证结果",
            })

        elif "菜单" in desc or "右键" in desc:
            actions.append({
                "action_type": "click",
                "target": "菜单",
                "description": "点击菜单按钮",
                "timeout": 10000,
            })
            actions.append({
                "action_type": "wait",
                "target": "",
                "value": 1000,
                "description": "等待菜单展开",
            })
            actions.append({
                "action_type": "screenshot",
                "target": "",
                "description": "截图验证菜单内容",
            })

        else:
            # 默认：截图 + 交给 AI 分析
            actions.append({
                "action_type": "wait",
                "target": "",
                "value": 2000,
                "description": "等待页面加载",
            })
            actions.append({
                "action_type": "screenshot",
                "target": "",
                "description": "截取当前页面",
            })

        logger.debug(f"  规则生成 {len(actions)} 个操作指令")
        return actions
