# AI 测试用例清洗 Skill

## 概述

这是一个结合 **AI 大语言模型（LLM）** 与 **Playwright 自动化测试框架** 的测试用例清洗工程。

核心思路：**让 AI 代替人工去"跑"一遍测试用例**，通过真实执行来验证用例的可执行性、准确性和完整性。

## 适用场景

- 历史测试用例库质量审计
- 版本升级后用例有效性验证
- 测试用例重构前的现状评估
- 大规模用例库的自动化清洗

## 清洗能力

| 清洗维度 | 说明 | AI 角色 | Playwright 角色 |
|---------|------|---------|----------------|
| **可执行性检查** | 验证用例步骤能否在当前版本中完整执行 | 分析失败原因 | 执行操作、捕获异常 |
| **组件存在性** | 检测用例引用的 UI 组件是否存在 | 判断组件是否已下线 | 尝试定位元素 |
| **预期一致性** | 验证预期结果与当前版本实际表现一致 | 对比截图与描述 | 截图记录实际界面 |
| **步骤完整性** | 检查操作步骤是否足够清晰、完整 | 评估描述质量 | 执行失败时反馈 |
| **描述清晰度** | 检查用例描述是否存在歧义 | 语言理解能力 | 执行误解导致的失败 |
| **重复检测** | 识别语义相似的重复用例 | 语义相似度分析 | - |

## 工作流程

```
Excel 用例文件
      |
      v
[1. 解析模块] ─── openpyxl 读取 Excel, 提取结构化用例
      |
      v
[2. AI 分析模块] ─── LLM 生成 Playwright 操作指令
      |                LLM 分析步骤清晰度和完整性
      v
[3. 执行引擎] ─── Playwright 连接客户端
      |            逐用例执行操作（点击、输入、截图）
      v
[4. 验证分析] ─── LLM 分析执行日志 + 截图
      |            判断通过/失败, 生成清洗标签
      v
[5. 报告生成] ─── Excel 清洗结果 + Markdown/HTML 报告
```

## 使用方式

### 快速演示（无需 API Key）

```bash
pip install -r requirements.txt
playwright install chromium
python main.py demo
```

### 完整运行（需要 API Key）

```bash
export OPENAI_API_KEY=sk-xxx
python main.py full
```

### 仅解析 Excel

```bash
python main.py parse
```

## 输出产物

| 文件 | 说明 |
|------|------|
| `outputs/cleaned_cases.xlsx` | 清洗后的测试用例（原格式+通过/失败/标签/建议） |
| `outputs/cleaning_report.md` | 清洗报告（Markdown） |
| `outputs/cleaning_report.html` | 清洗报告（HTML 网页版） |
| `outputs/screenshots/` | 执行过程中的截图 |

## 扩展性设计

### 对接不同 AI 服务

修改 `config.yaml` 中的 `ai` 配置即可切换：
- OpenAI GPT-4o
- DeepSeek (设置 `base_url: https://api.deepseek.com/v1`)
- 任何 OpenAI 兼容 API

### 适配不同应用

修改 `config.yaml` 中的 `app` 和 `playwright` 配置：
- 应用窗口标题
- 启动命令
- 视口大小
- 元素定位策略

## 局限性与注意事项

1. **客户端自动化限制**: 同花顺远航版是 Windows 桌面应用，Playwright 原生支持 Web 应用，对桌面应用的自动化需要通过 Chromium 启动嵌入浏览器或使用窗口句柄连接。当前 demo 通过 Playwright 连接到客户端内置的 WebView。

2. **AI 不确定性**: LLM 的输出具有概率性。通过设置低 temperature（0.1）和多次验证来降低不确定性。

3. **需要人工最终确认**: AI 给出的"通过/失败"判断和建议是需要人工复核的。建议将清洗结果作为第二意见，最终决策由测试工程师做出。

4. **规模限制**: 当前 demo 为单线程顺序执行。大规模用例清洗需要增加并行执行能力。
