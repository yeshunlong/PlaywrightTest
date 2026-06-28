"""
测试用例清洗工程 - 核心数据模型

定义了测试用例和清洗结果的完整数据结构
"""

from datetime import datetime
from typing import Optional, Any
from enum import Enum

from pydantic import BaseModel, Field


class CleanTag(str, Enum):
    """清洗标签"""
    PASSED = "通过"
    FAILED = "未通过"
    EXECUTABLE = "可执行"
    NOT_EXECUTABLE = "不可执行"
    COMPONENT_MISSING = "组件缺失"
    EXPECTED_MISMATCH = "预期不一致"
    STEP_INSUFFICIENT = "步骤不足"
    DESCRIPTION_UNCLEAR = "描述不清"
    DUPLICATE = "重复"


class TestStep(BaseModel):
    """单个测试步骤"""
    index: int = Field(description="步骤序号")
    action: str = Field(description="操作指令,如 click/input/wait/assert")
    description: str = Field(description="步骤描述,如'点击【通用工具】菜单'")
    target: Optional[str] = Field(default=None, description="目标元素选择器或文本")
    params: dict[str, Any] = Field(default_factory=dict, description="操作参数")
    expected: Optional[str] = Field(default=None, description="本步骤预期结果")


class TestCase(BaseModel):
    """测试用例完整模型"""
    case_id: str = Field(description="用例编号,如 TC_组件窗口_基础布局")
    name: str = Field(description="用例名称")
    category: str = Field(default="", description="一级目录")
    sub_category: str = Field(default="", description="二级目录")
    requirement_id: str = Field(default="", description="需求ID")
    remarks: str = Field(default="", description="备注")
    macro_precondition: str = Field(default="", description="外部大前提/前置环境")
    inner_precondition: str = Field(default="", description="内部前置条件")
    step_type: str = Field(default="", description="步骤类型/操作步骤名称")
    operation_desc: str = Field(default="", description="操作描述文本")
    params: str = Field(default="", description="参数")
    expected_result: str = Field(default="", description="整体预期结果")
    # 解析后拆分出的独立步骤
    parsed_steps: list[TestStep] = Field(default_factory=list, description="AI解析后的步骤列表")
    # 原始行数据
    raw_data: dict[str, Any] = Field(default_factory=dict)


class StepExecutionResult(BaseModel):
    """单步执行结果"""
    step_index: int
    status: str  # "passed" | "failed" | "skipped"
    duration_ms: int
    screenshot_path: Optional[str] = None
    error_message: Optional[str] = None
    actual_result: str = ""
    ai_analysis: str = ""


class CaseExecutionResult(BaseModel):
    """用例执行结果"""
    case: TestCase
    passed: bool
    reason: str = ""
    tags: list[str] = Field(default_factory=list)
    step_results: list[StepExecutionResult] = Field(default_factory=list)
    total_duration_ms: int = 0
    screenshots: list[str] = Field(default_factory=list)
    ai_suggestion: str = ""  # AI 建议如何修复
    executed_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class CleaningReport(BaseModel):
    """清洗报告"""
    title: str = "测试用例清洗报告"
    generated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    total_cases: int = 0
    passed_count: int = 0
    failed_count: int = 0
    not_executable_count: int = 0
    tag_statistics: dict[str, int] = Field(default_factory=dict)
    results: list[CaseExecutionResult] = Field(default_factory=list)
    summary: str = ""
    suggestions: list[str] = Field(default_factory=list)


class PlaywrightAction(BaseModel):
    """AI 生成的 Playwright 操作指令"""
    action_type: str = Field(description="操作类型: navigate/click/dblclick/input/wait/screenshot/assert/scroll/hover/select")
    target: str = Field(description="目标元素描述或选择器")
    value: Optional[str] = Field(default=None, description="输入值或参数")
    description: str = Field(default="", description="操作说明")
    timeout: int = Field(default=10000, description="超时毫秒")
