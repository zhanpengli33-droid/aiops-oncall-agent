# AIOps OnCall Agent 项目包装规格

## 目标

将现有 OnCall Agent 项目的对外表述与简历中的“智能 OnCall 运维 Agent 系统”保持一致，去掉“轻量级”和 `lightweight` 表述，同时不将个人模拟项目包装为真实企业生产系统。

## 对外命名

- GitHub 仓库名：`aiops-oncall-agent`
- README 主标题：`Intelligent OnCall Agent System`
- README 副标题：`基于 LangGraph + MCP 的智能运维告警诊断系统`
- Python 发行包名：`aiops-oncall-agent`
- Python 导入包名继续使用 `oncall_agent`，不修改已有代码导入和命令行入口。

## 项目简介

README 开场介绍使用：

> 基于 LangGraph + MCP 构建的智能 OnCall 运维 Agent 系统，通过 Planner、Executor、Replanner 工作流串联告警解析、日志与监控工具调用、根因分析及处置建议生成。

GitHub 仓库简介使用：

> An intelligent OnCall Agent system built with LangGraph and MCP for alert triage, tool-driven diagnosis, root-cause analysis, and remediation recommendations.

GitHub Topics 设置为：`aiops`、`langgraph`、`mcp`、`agent`、`incident-response`、`python`。

## 修改范围

1. 修改 `README.md` 的标题、开场介绍和目录树中的项目名。
2. 修改 `pyproject.toml` 的发行包名和项目简介。
3. 修改 `src/oncall_agent/__init__.py` 的包说明，去掉 `Lightweight`。
4. 将 GitHub 仓库和本地项目目录都重命名为 `aiops-oncall-agent`。
5. 同步更新 Git remote、GitHub 简介和 Topics。

## 边界

- 保留 README 中“使用本地模拟告警、日志和监控数据，未接入企业内部系统”的真实性声明。
- 不修改 LangGraph 工作流、MCP 工具、评估逻辑或测试数据。
- 不添加“生产级”、“大规模落地”或企业实际效益等无法由仓库支撑的描述。

## 验收标准

- README、项目元数据和源码包说明中不再出现 `lightweight`、`轻量级` 或 `轻量` 的对外表述。
- 现有 12 项测试全部通过。
- GitHub 仓库保持公开，新地址为 `https://github.com/zhanpengli33-droid/aiops-oncall-agent`。
- 本地目录、Git remote、GitHub 仓库名、README 和项目元数据命名一致。
