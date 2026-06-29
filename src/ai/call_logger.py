"""
AI 交互日志记录器

记录每一次 AI 调用的完整信息：
- 调用目的（步骤解析 / 操作生成 / 结果分析 / 报告摘要）
- 完整的 System Prompt
- 完整的 User Prompt
- AI 返回的 Raw Response
- 解析后的结构化结果
- 时间戳、Token 数、耗时

用于导出和审查 AI 在清洗过程中的"思考轨迹"。
"""

import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from loguru import logger


class AICallRecord:
    """单次 AI 调用记录"""

    def __init__(
        self,
        purpose: str,
        system_prompt: str,
        user_prompt: str,
        response: str,
        parsed_result: Optional[Any] = None,
        duration_ms: int = 0,
        model: str = "",
        temperature: float = 0.0,
        tokens_used: int = 0,
        case_name: str = "",
        mock_mode: bool = False,
        error: Optional[str] = None,
    ):
        self.id = str(uuid.uuid4())[:8]
        self.timestamp = datetime.now(timezone.utc).isoformat()
        self.purpose = purpose
        self.system_prompt = system_prompt
        self.user_prompt = user_prompt
        self.response = response
        self.parsed_result = parsed_result
        self.duration_ms = duration_ms
        self.model = model
        self.temperature = temperature
        self.tokens_used = tokens_used
        self.case_name = case_name
        self.mock_mode = mock_mode
        self.error = error

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "purpose": self.purpose,
            "system_prompt": self.system_prompt,
            "user_prompt": self.user_prompt,
            "response": self.response,
            "parsed_result": self.parsed_result,
            "duration_ms": self.duration_ms,
            "model": self.model,
            "temperature": self.temperature,
            "tokens_used": self.tokens_used,
            "case_name": self.case_name,
            "mock_mode": self.mock_mode,
            "error": self.error,
        }

    def to_markdown(self) -> str:
        """导出为可读的 Markdown 格式"""
        lines = [
            f"---",
            f"## AI 调用 #{self.id}",
            f"",
            f"| 属性 | 值 |",
            f"|------|------|",
            f"| 目的 | {self.purpose} |",
            f"| 时间 | {self.timestamp} |",
            f"| 模型 | {self.model} |",
            f"| 温度 | {self.temperature} |",
            f"| 耗时 | {self.duration_ms}ms |",
            f"| Token | {self.tokens_used} |",
            f"| 用例 | {self.case_name or '-'} |",
            f"| 模式 | {'模拟' if self.mock_mode else '真实'} |",
        ]
        if self.error:
            lines.append(f"| 错误 | {self.error} |")
        lines.extend([
            "",
            "### System Prompt",
            "",
            "```",
            self.system_prompt[:2000] + ("..." if len(self.system_prompt) > 2000 else ""),
            "```",
            "",
            "### User Prompt",
            "",
            "```",
            self.user_prompt[:2000] + ("..." if len(self.user_prompt) > 2000 else ""),
            "```",
            "",
            "### AI Response",
            "",
            "```json" if self._is_json(self.response) else "```",
            self.response[:3000] + ("..." if len(self.response) > 3000 else ""),
            "```",
            "",
            "### 解析结果",
            "",
            "```json",
            json.dumps(self.parsed_result, ensure_ascii=False, indent=2) if self.parsed_result else "(无)",
            "```",
            "",
        ])
        return "\n".join(lines)

    @staticmethod
    def _is_json(s: str) -> bool:
        try:
            json.loads(s)
            return True
        except (json.JSONDecodeError, TypeError):
            return "{" in s or "[" in s


class AICallLogger:
    """AI 调用日志收集器"""

    def __init__(self):
        self.records: list[AICallRecord] = []

    def record(
        self,
        purpose: str,
        system_prompt: str,
        user_prompt: str,
        response: str,
        parsed_result: Any = None,
        duration_ms: int = 0,
        model: str = "",
        temperature: float = 0.0,
        case_name: str = "",
        mock_mode: bool = False,
        error: Optional[str] = None,
    ) -> AICallRecord:
        """记录一次 AI 调用"""
        rec = AICallRecord(
            purpose=purpose,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response=response,
            parsed_result=parsed_result,
            duration_ms=duration_ms,
            model=model,
            temperature=temperature,
            case_name=case_name,
            mock_mode=mock_mode,
            error=error,
        )
        self.records.append(rec)
        logger.debug(f"[AI LOG] {purpose} | case={case_name} | {duration_ms}ms")
        return rec

    def export_json(self, path: Path) -> Path:
        """导出为 JSON 格式"""
        data = {
            "title": "AI 交互日志",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_calls": len(self.records),
            "calls": [r.to_dict() for r in self.records],
            "statistics": self._calc_stats(),
        }
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info(f"AI 交互日志已导出: {path} ({len(self.records)} 条记录)")
        return path

    def export_markdown(self, path: Path) -> Path:
        """导出为 Markdown 格式（可读性强）"""
        lines = [
            f"# AI 交互日志",
            f"",
            f"**生成时间**: {datetime.now(timezone.utc).isoformat()}",
            f"**总调用数**: {len(self.records)}",
            f"",
            "## 统计",
            f"",
            f"| 调用目的 | 次数 |",
            f"|----------|------|",
        ]
        for purpose, count in self._calc_stats()["by_purpose"].items():
            lines.append(f"| {purpose} | {count} |")
        lines.extend(["", "---", ""])

        for i, rec in enumerate(self.records, 1):
            lines.append(rec.to_markdown())

        path.write_text("\n".join(lines), encoding="utf-8")
        logger.info(f"AI 交互日志(MD)已导出: {path}")
        return path

    def _calc_stats(self) -> dict:
        """计算统计信息"""
        by_purpose: dict[str, int] = {}
        total_tokens = 0
        total_duration = 0
        for r in self.records:
            by_purpose[r.purpose] = by_purpose.get(r.purpose, 0) + 1
            total_tokens += r.tokens_used
            total_duration += r.duration_ms
        return {
            "total_calls": len(self.records),
            "by_purpose": by_purpose,
            "total_tokens": total_tokens,
            "total_duration_ms": total_duration,
            "mock_calls": sum(1 for r in self.records if r.mock_mode),
            "error_calls": sum(1 for r in self.records if r.error),
            "avg_duration_ms": total_duration // max(len(self.records), 1),
        }


# 全局日志实例
_call_logger: Optional[AICallLogger] = None


def get_logger() -> AICallLogger:
    global _call_logger
    if _call_logger is None:
        _call_logger = AICallLogger()
    return _call_logger


def reset_logger():
    global _call_logger
    _call_logger = AICallLogger()
