# TestAgent Client

> Python Agent 核心 - 基于 AgentScope 的智能任务执行引擎

## 概述

TestAgent Client 是 TestAgent 项目的 Python Agent 核心组件，基于 AgentScope 框架实现 ReActAgent，支持多 LLM 提供商、MCP 协议集成和可扩展的技能系统。

## 架构

```
┌─────────────────────────────────────────────────────────┐
│                  Node.js Server                         │
│            (进程管理 / SSE 流 / WebSocket)               │
└───────────────────────┬─────────────────────────────────┘
                        │ subprocess
┌───────────────────────▼─────────────────────────────────┐
│              Python Agent (ReActAgent)                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   主循环     │  │   Hook 系统  │  │   规划系统   │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└───────────────────────┬─────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────┐
│                    工具层                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   基础工具   │  │  MCP 工具    │  │  Skill 工具  │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────┘
```

## 核心特性

### 多 LLM 提供商支持

| 提供商 | 模型示例 |
|--------|----------|
| DashScope | qwen-max, qwen-plus |
| OpenAI | gpt-4, gpt-3.5-turbo |
| Anthropic | claude-3-opus, claude-3-sonnet |
| Gemini | gemini-pro |
| Ollama | llama2, mistral |

### 三层工具体系

1. **基础工具** - 始终可用
   - `execute_shell` - 跨平台命令执行
   - `read_file` / `write_file` / `edit_file` - 文件操作
   - `glob_files` / `grep_files` - 文件搜索
   - `web_fetch` - HTTP 请求

2. **MCP 工具** - 通过 MCP 协议连接外部服务
   - 在 `.testagent/settings.json` 中配置
   - 支持任意 MCP Server

3. **Skill 工具** - 领域专业知识
   - 位于 `.testagent/skills/` 目录
   - 每个 Skill 包含 `SKILL.md` 元数据 + `tools/` 工具代码

### 实时事件推送

通过 Hook 系统将 Agent 执行过程实时推送到 Server：
- 增量文本输出
- 工具调用事件
- 工具执行结果

### 多步骤规划

支持复杂任务的子任务分解与执行：
- `create_plan` - 创建执行计划
- `update_subtask_state` - 更新子任务状态
- `finish_plan` - 完成计划

## 目录结构

```
Client/
├── agent/                      # Agent 核心
│   ├── coordinator_main.py    # 统一入口点 (支持 direct/coordinator 模式)
│   ├── main.py                # 旧入口 (已废弃，重定向到 coordinator_main)
│   ├── args.py                # CLI 参数定义
│   ├── hook.py                # 事件推送系统
│   ├── model.py               # LLM 适配器
│   ├── mcp_loader.py          # MCP 连接管理
│   ├── settings_loader.py     # 配置加载
│   ├── tool_registry.py       # 工具注册与管理
│   ├── tool_groups.py         # 工具组定义
│   ├── coordinator/           # Coordinator 系统
│   │   ├── coordinator.py    # 主协调器
│   │   ├── task_planner.py   # 任务规划
│   │   ├── phase_scheduler.py # Phase 调度
│   │   ├── result_evaluator.py # 结果评估
│   │   └── error_recovery.py # 错误恢复
│   ├── worker/                # Worker 执行框架
│   │   ├── worker_loader.py  # Worker 加载器
│   │   ├── worker_runner.py  # Worker 执行器
│   │   └── modes/            # 执行模式 (react/single/loop)
│   ├── plan/                  # 规划系统
│   │   └── plan_to_hint.py   # 规划提示生成
│   ├── tool/                  # 工具实现
│   │   ├── base/             # 基础工具
│   │   └── utils.py          # 工具辅助函数
│   ├── common/                # 通用模块
│   │   ├── logger.py         # 日志系统
│   │   ├── test_models.py    # 测试数据模型
│   │   ├── report_generator.py # 报告生成
│   │   └── engines/          # 测试执行引擎
│   └── utils/                 # 工具函数
├── server/                    # Node.js Server
│   ├── src/
│   │   ├── agent/            # Agent 进程管理
│   │   ├── modules/          # 功能模块
│   │   └── config/           # 配置
│   ├── start-dev.ps1         # PowerShell 启动脚本 (UTF-8 编码)
│   └── .env.example          # 环境变量模板
├── .testagent/                # 配置与扩展
│   ├── settings.example.json # 配置模板
│   ├── agents/               # Worker Agent 定义
│   │   ├── planner.md       # 规划 Agent
│   │   ├── executor.md      # 执行 Agent
│   │   ├── analyzer.md      # 分析 Agent
│   │   ├── reporter.md      # 报告 Agent
│   │   └── validator.md     # 验证 Agent
│   ├── skills/               # 技能扩展
│   ├── commands/             # 命令扩展
│   └── rules/                # 规则定义
├── prompts/                   # 系统提示词
│   ├── system_prompt.md
│   └── coordinator/          # Coordinator 提示词
├── frontend/                  # Vue 前端 (开发中)
├── storage/                   # 数据存储
├── scripts/                   # 脚本工具
├── .venv/                     # Python 虚拟环境 (gitignore)
├── docker-compose.yml         # Docker 服务 (PostgreSQL, Redis)
├── cli.py                     # CLI 入口
└── requirements.txt           # Python 依赖
```

## 快速开始

### 环境要求

- Python 3.12+
- Node.js 18+

### 安装

```bash
# 创建 Python 虚拟环境
python -m venv .venv

# 激活虚拟环境
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# Windows CMD:
.venv\Scripts\activate.bat
# Linux/macOS:
source .venv/bin/activate

# 安装 Python 依赖
pip install -r requirements.txt

# Node.js 依赖 (Server)
cd server
npm install
```

### 配置

```bash
# 复制配置模板
cp .testagent/settings.example.json .testagent/settings.json

# 复制环境变量配置
cd server
cp .env.example .env

# 编辑 .env 文件，配置数据库、API Key 等
```

### 运行

#### Windows PowerShell 编码设置

在 Windows PowerShell 中运行时，需要先设置 UTF-8 编码以正确显示中文：

```powershell
# 方式一：使用启动脚本（推荐）
cd server
.\start-dev.ps1

# 方式二：手动设置编码后运行
chcp 65001
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
npm run dev
```

#### 启动服务

```bash
# 1. 启动 PostgreSQL 和 Redis（使用 Docker）
docker-compose up -d

# 2. 初始化数据库
cd server
npx prisma migrate dev

# 3. 启动 Server
npm run dev
```

#### 直接运行 Agent (调试模式)

```bash
# 使用虚拟环境中的 Python
python agent/coordinator_main.py --query '{"content": "Hello"}' \
  --llmProvider dashscope \
  --modelName qwen-max \
  --apiKey YOUR_API_KEY \
  --workspace ./storage \
  --mode direct
```

#### Agent 执行模式

支持两种执行模式，通过 `--mode` 参数或 `AGENT_MODE` 环境变量切换：

| 模式 | 说明 |
|------|------|
| `direct` | 单 Agent 模式，使用单个 ReActAgent 处理所有请求（默认） |
| `coordinator` | 协调模式，使用 Coordinator 分解任务并调度多个 Worker |

## 配置说明

### settings.json

```json
{
  "mcpServers": {
    "server_name": {
      "command": "node",
      "args": ["path/to/server.js"],
      "env": {},
      "enabled": true,
      "group": "tool_group_name"
    }
  },
  "toolDisplay": {
    "names": { "tool_id": "显示名称" },
    "hidden": ["tool_id"]
  },
  "storage": {
    "rootPath": "./storage"
  },
  "vectorDb": {
    "backend": "chromadb",
    "persistDirectory": "./storage/vectordb"
  }
}
```

### CLI 参数

| 参数 | 说明 |
|------|------|
| `--query` | 用户消息 (JSON 格式) |
| `--llmProvider` | LLM 提供商 |
| `--modelName` | 模型名称 |
| `--apiKey` | API 密钥 |
| `--workspace` | 工作区根目录 |
| `--writePermission` | 写权限开关 |
| `--studio_url` | Server 回调地址 |
| `--conversation_id` | 会话 ID |
| `--reply_id` | 回复 ID |
| `--mode` | 执行模式：`direct`（单 Agent）或 `coordinator`（多 Worker 协调） |

## 扩展开发

### 添加 Skill

1. 创建目录 `.testagent/skills/your_skill/`
2. 创建 `SKILL.md` 定义元数据
3. 创建 `tools/` 目录并实现工具函数

```yaml
# SKILL.md
---
name: your-skill
description: 技能描述
version: 1.0.0
tools_dir: tools
---
```

```python
# tools/your_tool.py
from agent.tool.utils import ToolResponse

def your_tool(param: str) -> ToolResponse:
    """工具描述"""
    return ToolResponse(success=True, data="result")
```

### 添加 MCP Server

在 `settings.json` 的 `mcpServers` 中配置：

```json
{
  "your_server": {
    "command": "python",
    "args": ["-m", "your_mcp_server"],
    "enabled": true,
    "group": "your_tools"
  }
}
```

## 技术栈

- **Agent 框架**: AgentScope
- **数据验证**: Pydantic
- **HTTP 客户端**: Requests, HTTPX
- **向量数据库**: ChromaDB, Faiss
- **日志**: Loguru
- **Server**: Fastify, Prisma, Socket.IO

## 许可证

MIT License
