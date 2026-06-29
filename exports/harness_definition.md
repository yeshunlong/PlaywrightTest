# 同花顺远航版测试用例清洗 Harness

**版本**: 1.0.0 | **导出时间**: 2026-06-29T11:49:33.143986+00:00

> 基于 Playwright + AI 的测试用例自动化执行与清洗框架

---

## 1. 架构概览

Playwright 自动化浏览器 → 操作同花顺远航版客户端 → AI 分析结果

## 2. 核心组件

### 2.1 浏览器引擎

| 属性 | 值 |
|------|------|
| 框架 | Playwright (async) |
| 浏览器 | Chromium |
| 模式 | desktop_webview |
| 连接方式 | 通过 Chromium 连接到客户端内嵌 WebView |

### 2.2 AI 引擎

| 属性 | 值 |
|------|------|
| 服务商 | openai |
| 模型 | gpt-4o |
| 温度 | 0.1 |
| API类型 | OpenAI 兼容 API |

**AI 的 4 个角色**:
- 步骤解析: 自然语言 → 结构化操作步骤
- 操作生成: 结构化步骤 → Playwright 操作指令
- 结果分析: 截图 + 日志 → 通过/失败 + 清洗标签
- 报告摘要: 统计数据 → 自然语言分析报告

### 2.3 操作执行器

支持的操作类型:

- `click`: 点击 UI 元素，支持 text/role/menuitem 定位
- `dblclick`: 双击 UI 元素
- `input`: 文本输入
- `wait`: 等待，毫秒级
- `screenshot`: 全页截图
- `assert`: 断言元素存在/文本匹配
- `scroll`: 页面滚动
- `hover`: 鼠标悬停
- `resize`: 窗口尺寸调整
- `observe`: 截图 + AI 视觉分析

元素定位策略:

- **text**: 按文本内容匹配元素
- **role**: 按 WAI-ARIA 语义角色匹配
- **selector**: CSS/XPath 精确选择器

## 3. 执行配置

### Playwright
- 无头模式: False
- 超时: 30000ms
- 每步等待: 1000ms
- 视口: 1280×800

### 执行策略
- 最大并发: 1
- 最大重试: 2
- 成功截图: True
- 失败截图: True

## 4. 执行流水线

### 阶段 1: Excel 解析
- **输入**: 布局与显示.xlsx
- **输出**: TestCase[] 结构化用例列表
- **工具**: openpyxl
- **说明**: 读取 Excel，自动识别列头，映射为结构化 TestCase 对象

### 阶段 2: AI 步骤解析
- **输入**: TestCase（自然语言描述）
- **输出**: TestCase（含 parsed_steps 结构化步骤）
- **工具**: LLMClient → step_parse prompt
- **说明**: LLM 将操作描述拆分为独立的结构化步骤

### 阶段 3: 操作指令生成
- **输入**: 结构化步骤
- **输出**: PlaywrightAction[] 操作指令列表
- **工具**: LLMClient → action_gen prompt, ActionGenerator (规则降级)
- **说明**: AI 生成 + 规则引擎降级的双重操作生成策略

### 阶段 4: Playwright 执行
- **输入**: PlaywrightAction[]
- **输出**: StepExecutionResult[] + 截图
- **工具**: PlaywrightRunner, Chromium
- **说明**: 在真实客户端上逐步执行操作，截图留证

### 阶段 5: AI 结果分析
- **输入**: 执行日志 + 截图 + 预期结果
- **输出**: CaseExecutionResult (passed/failed + tags + suggestion)
- **工具**: LLMClient → result_analysis prompt
- **说明**: AI 综合判断用例是否通过，生成清洗标签和修复建议

### 阶段 6: 报告生成
- **输入**: CaseExecutionResult[]
- **输出**: cleaned_cases.xlsx + cleaning_report.md + cleaning_report.html
- **工具**: openpyxl, ReportGenerator
- **说明**: 生成三种格式的清洗报告

## 5. 运行方式

### demo 模式
演示模式，零外部依赖
**依赖**: Python 3.10+, pip install -r requirements.txt
**命令**: `python main.py demo`
**输出**: outputs/cleaned_cases.xlsx, outputs/cleaning_report.md, outputs/cleaning_report.html

### full 模式
完整模式，真实执行 + AI 分析
**依赖**: Python 3.10+, OpenAI API Key, 同花顺远航版客户端, playwright install chromium
**命令**: `export OPENAI_API_KEY=sk-xxx && python main.py full`
**输出**: 同 demo + outputs/screenshots/ + outputs/ai_interaction_log.json
