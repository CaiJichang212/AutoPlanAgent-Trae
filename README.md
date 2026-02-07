# AutoPlanAgent - 自动化数据分析智能体

AutoPlanAgent 是一个基于 **LangGraph** 构建的高级数据分析智能体系统。它能够深度理解用户的自然语言需求，自动拆解分析任务，并在用户确认后自主执行 SQL 查询、Python 数据处理和专业可视化，最终产出结构化的分析报告。

## 🌟 核心特性

- **自主规划 (Autonomous Planning)**: 能够将复杂的分析目标（如“分析光伏行业过去两年的财务表现”）自动拆解为数据提取、清洗、探索性分析和可视化等具体步骤。
- **人机协作 (Human-in-the-loop)**: 在计划生成后自动进入中断状态，等待用户审查和反馈，确保分析路径符合预期。
- **多模型支持 (Multi-LLM Support)**: 内置对 ModelScope、SiliconFlow 及 OpenAI 兼容接口的支持，支持 Qwen、QwQ 等前沿大模型。
- **工具增强 (Tool-Augmented)**: 
  - **SQL 查询**: 自动感知数据库 Schema，生成并执行高效的 MySQL 查询。
  - **Python 分析**: 利用 Pandas、NumPy 等库进行统计建模、趋势分析及复杂逻辑计算。
  - **专业可视化**: 使用 Matplotlib 和 Seaborn 生成适配中文显示的高质量图表。
- **状态持久化 (Persistence)**: 基于 LangGraph 的 Checkpointer 机制，支持任务中断恢复、多轮对话反馈及状态追踪。
- **自动化报告 (Auto-Reporting)**: 自动汇总各步骤执行结果，生成包含关键发现、业务建议和图表附录的结构化 Markdown 报告。

## 🏗️ 项目架构

项目采用 LangGraph 的有向无环图 (DAG) 模型进行流转控制，核心逻辑如下：

```mermaid
graph TD
    Start((开始)) --> Understand[任务理解]
    Understand --> Plan[任务拆解与规划]
    Plan --> WaitConfirm{等待用户确认}
    WaitConfirm --> Feedback[处理用户反馈]
    
    Feedback -- 修改建议 --> Plan
    Feedback -- 确认通过 --> Execute[执行计划步骤]
    
    Execute --> Check{检查执行状态}
    Check -- 剩余步骤 --> Execute
    Check -- 执行出错 --> End((结束))
    Check -- 全部完成 --> Report[生成最终报告]
    
    Report --> End
```

### 核心模块说明
- **`agent/graph.py`**: 定义 LangGraph 状态机、节点流转逻辑及中断策略。
- **`agent/nodes/`**: 包含理解 (Understanding)、规划 (Planning)、执行 (Execution)、反馈 (Feedback) 和报告 (Reporting) 的具体业务逻辑。
- **`agent/tools/`**: 
    - `db_tools.py`: 数据库连接、Schema 获取及 SQL 执行。
    - `analysis_tools.py`: Python REPL 环境，用于数据处理和建模。
    - `viz_tools.py`: 自动化绘图工具，支持中文字体适配。
- **`agent/state.py`**: 定义智能体的全局状态 Schema (TypedDict)。
- **`agent/utils.py`**: 包含多模型加载、日志配置及文本处理工具。

## 🚀 快速开始

### 1. 环境安装

克隆仓库并安装依赖：

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

在项目根目录创建 `.env` 文件，配置你的 API 密钥和数据库信息：

```env
# 模型配置 (三选一或组合使用)
MODELSCOPE_API_KEYS=key1,key2
SILICONFLOW_API_KEYS=key1,key2
OPENAI_API_KEY=your_openai_key
OPENAI_API_BASE=https://api.openai.com/v1

# 默认使用的模型名称
MODEL_NAME=Qwen/Qwen3-30B-A3B-Instruct-2507

# 数据库配置 (目前仅支持 MySQL)
DATABASE_URL=mysql+pymysql://user:password@localhost:3306/your_db

# 可选：搜索增强
TAVILY_API_KEY=your_tavily_key
```

### 3. 数据准备

本项目提供了示例光伏行业财务数据脚本：

```bash
# 方案 A：写入本地模拟数据到 MySQL
python data/prepare_pv_data.py

# 方案 B：通过 AkShare 抓取真实光伏财务数据并写入
pip install akshare
python data/load_pv_financials_akshare.py --pv-table pv_financials
```

### 4. 运行 Agent

#### 命令行测试 (CLI)
```bash
# 运行演示脚本，模拟“启动-确认-执行”完整流程
python test_agent.py
```

#### RESTful API 服务
```bash
# 启动 FastAPI 服务
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```
服务启动后，访问 `http://127.0.0.1:8000/docs` 查看 Swagger API 文档。

**主要接口：**
- `POST /tasks/start`: 提交初始需求，返回 `thread_id` 和初步计划。
- `POST /tasks/feedback`: 提交用户反馈（如“同意”或“修改步骤”）。
- `GET /tasks/{thread_id}/status`: 查询任务当前执行状态及结果。

## 📂 目录结构

```text
├── agent/
│   ├── nodes/          # 状态机节点逻辑
│   ├── prompts/        # LLM 提示词模板 (text 格式)
│   ├── tools/          # Agent 工具集 (SQL, Python, Viz)
│   ├── graph.py        # LangGraph 工作流定义
│   ├── state.py        # 状态 Schema 定义
│   └── utils.py        # 多模型适配与工具函数
├── data/               # 数据加载与初始化脚本
├── logs/               # 运行日志
├── reports/            # 生成的报告及图表
│   └── images/         # 自动生成的图表 (.png)
├── templates/          # 报告 Markdown 模板
├── app.py              # FastAPI 应用入口
├── test_agent.py       # 命令行集成测试脚本
└── requirements.txt    # 依赖列表
```

## 📊 示例演示

**用户需求**: *"分析隆基绿能最近两年的净利润增长情况，并绘制趋势图。"*

1. **理解阶段**: 识别出需要查询 `pv_financials` 表，过滤条件为 `company_name='隆基绿能'`。
2. **规划阶段**: 
   - Step 1: `sql_query` 获取财务报表数据。
   - Step 2: `python_analysis` 计算净利润增长率。
   - Step 3: `visualizer` 绘制折线趋势图。
3. **反馈阶段**: 暂停并展示计划，用户输入 "OK" 后继续。
4. **执行阶段**: 自动调用对应工具，处理 MySQL 结果并生成图片。
5. **报告阶段**: 汇总所有执行结果，在 `reports/` 目录下生成一份完整的 Markdown 报告。
