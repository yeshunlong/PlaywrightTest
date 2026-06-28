"""
LLM 客户端

封装与 AI 服务的交互，支持 OpenAI / DeepSeek / 兼容 API。
提供统一的接口用于：
- 步骤解析
- 操作生成
- 结果分析
- 报告生成
"""

import json
import os
import re
from typing import Any

import openai
from loguru import logger

from src.ai.prompts import (
    STEP_PARSE_SYSTEM,
    STEP_PARSE_USER,
    ACTION_GEN_SYSTEM,
    ACTION_GEN_USER,
    RESULT_ANALYSIS_SYSTEM,
    RESULT_ANALYSIS_USER,
    REPORT_SUMMARY_SYSTEM,
    REPORT_SUMMARY_USER,
)


class LLMClient:
    """AI 大模型客户端"""

    def __init__(self, config: dict):
        self.config = config
        ai_cfg = config.get("ai", {})

        self.model = ai_cfg.get("model", "gpt-4o")
        self.temperature = ai_cfg.get("temperature", 0.1)
        self.max_tokens = ai_cfg.get("max_tokens", 4096)
        self.api_key = os.environ.get(ai_cfg.get("api_key_env", "OPENAI_API_KEY"), "")
        self.base_url = ai_cfg.get("base_url", "https://api.openai.com/v1")

        if not self.api_key:
            logger.warning("未设置 API Key，将使用模拟模式运行")
            self.mock_mode = True
        else:
            self.client = openai.OpenAI(api_key=self.api_key, base_url=self.base_url)
            self.mock_mode = False

    def chat(self, system_prompt: str, user_prompt: str) -> str:
        """发送对话请求"""
        if self.mock_mode:
            logger.info("[MOCK] AI 调用: {}", user_prompt[:100])
            return self._mock_response(system_prompt, user_prompt)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.error(f"AI 调用失败: {e}")
            return self._mock_response(system_prompt, user_prompt)

    def _mock_response(self, system: str, user: str) -> str:
        """模拟 AI 响应（无 API Key 时使用）"""
        # 根据 system prompt 内容判断类型并返回模拟结果
        return "{}"

    def parse_steps(self, case: dict) -> list[dict]:
        """解析测试步骤：自然语言 -> 结构化步骤"""
        prompt = STEP_PARSE_USER.format(
            case_name=case.get("用例名称", ""),
            step_type=case.get("步骤类型", ""),
            precondition=case.get("前置条件", "") or case.get("大前提", ""),
            operation_desc=case.get("操作描述", ""),
            expected_result=case.get("预期结果", ""),
        )

        response = self.chat(STEP_PARSE_SYSTEM, prompt)
        return self._extract_json(response, default=[])

    def generate_actions(self, case: dict, parsed_steps: list[dict] = None) -> list[dict]:
        """生成 Playwright 操作指令"""
        steps_text = case.get("操作描述", "")
        if parsed_steps:
            steps_text = "\n".join(
                f"{s.get('index', i+1)}. {s.get('description', '')}"
                for i, s in enumerate(parsed_steps)
            )

        prompt = ACTION_GEN_USER.format(
            case_name=case.get("用例名称", ""),
            precondition=case.get("前置条件", "") or case.get("大前提", ""),
            steps_text=steps_text,
            expected_result=case.get("预期结果", ""),
        )

        response = self.chat(ACTION_GEN_SYSTEM, prompt)
        return self._extract_json(response, default=[])

    def analyze_result(
        self,
        case_name: str,
        expected_result: str,
        execution_log: str,
    ) -> dict:
        """分析执行结果"""
        prompt = RESULT_ANALYSIS_USER.format(
            case_name=case_name,
            expected_result=expected_result,
            execution_log=execution_log,
        )

        response = self.chat(RESULT_ANALYSIS_SYSTEM, prompt)
        return self._extract_json(response, default={
            "passed": False,
            "confidence": 0.5,
            "reason": "无法分析",
            "tags": ["不可执行"],
            "suggestion": "需人工复查",
        })

    def generate_summary(self, stats: dict) -> str:
        """生成报告摘要"""
        prompt = REPORT_SUMMARY_USER.format(
            total=stats.get("total", 0),
            passed=stats.get("passed", 0),
            failed=stats.get("failed", 0),
            not_executable=stats.get("not_executable", 0),
            tag_stats=json.dumps(stats.get("tag_stats", {}), ensure_ascii=False, indent=2),
            failure_details=stats.get("failure_details", "无"),
            module_name=stats.get("module_name", "布局与显示"),
        )

        response = self.chat(REPORT_SUMMARY_SYSTEM, prompt)
        return response

    @staticmethod
    def _extract_json(text: str, default: Any = None) -> Any:
        """从 AI 响应中提取 JSON"""
        # 尝试直接解析
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # 尝试提取 ```json ... ``` 代码块
        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # 尝试提取 { ... } 或 [ ... ]
        brace_match = re.search(r"\{[\s\S]*\}", text)
        if brace_match:
            try:
                return json.loads(brace_match.group(0))
            except json.JSONDecodeError:
                pass

        bracket_match = re.search(r"\[[\s\S]*\]", text)
        if bracket_match:
            try:
                return json.loads(bracket_match.group(0))
            except json.JSONDecodeError:
                pass

        logger.warning(f"无法从 AI 响应中提取 JSON: {text[:200]}")
        return default
