# Douyin-EchoCue

[![Python](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/)
[![Framework](https://img.shields.io/badge/framework-Litestar-20232a.svg)](https://litestar.dev/)
[![Package Manager](https://img.shields.io/badge/package%20manager-uv-654ff0.svg)](https://docs.astral.sh/uv/)
[![Code Style](https://img.shields.io/badge/code%20style-ruff-46a2f1.svg)](https://docs.astral.sh/ruff/)
[![License](https://img.shields.io/badge/license-Apache--2.0-green.svg)](LICENSE)

[English](README.md) | 简体中文

Douyin-EchoCue 是一个面向抖音直播场景的互动辅助工具，服务主播和运营团队。
它帮助把直播弹幕转成更快的回复、更统一的提词，以及更顺畅的现场互动节奏。

## 典型场景

- 主播在高弹幕量直播间里，需要快速获得自然的回复建议。
- 团队希望回复风格与直播间人设保持一致。
- 运营希望在不打断直播流程的前提下，提供结构化的互动支持。

## MVP Roadmap

- [x] M1 基础工程 - 后端骨架、PostgreSQL、Redis、Qdrant 和本地运行环境。
- [x] M2 接入与分类 - 直播状态、弹幕窗口和 lexicon gRPC。
- [x] M3 Workflow 主链路 - 触发、InterestAgent、ReplyAgent、审核和持久化。
- [ ] M4 账号权限服务 - 账号、权限上下文、登录和访问校验。
- [ ] M5 Web 管理端 - 主体档案、触发配置、规则和 Workflow 回放。
- [ ] M6 Windows client - Electron client、浮窗展示和推送联调。
- [ ] M7 观测能力 - Prometheus / OpenTelemetry 指标、链路和日志。
- [ ] M8 端到端验收 - 演示流程、种子数据和最终验证。

### 分布式服务

| 服务 | 作用 |
| --- | --- |
| `app` | 主后端，负责登录、Workflow 执行、持久化和向 client 推送结果。 |
| `lexicon` | 直播弹幕语义分类服务，负责互动类型识别和候选弹幕召回。 |
| `auth` | 账号与权限服务，负责凭据校验、账号上下文和访问决策。 |

## 环境要求

- Python 3.12
- uv
- Docker，用于本地 Compose 运行环境
- PostgreSQL，用于本地或容器化数据库环境

## 快速开始

安装依赖：

```bash
make install
```

查看可用项目命令：

```bash
make help
uv run app --help
uv run app database --help
```

本地启动应用：

```bash
uv run app run --host 127.0.0.1 --port 8000
```

访问健康检查：

```bash
curl http://127.0.0.1:8000/system/health
```

## 数据库

默认配置从 `config.yaml` 读取。启动应用前，可以在本地配置文件中调整数据库设置，或提供配置层支持的运行时环境变量。

通过项目 CLI 执行迁移：

```bash
uv run app database upgrade --no-prompt
```

常用检查命令：

```bash
uv run app database show-current-revision
uv run app database history
uv run app database check
```

## Docker Compose

构建并启动服务：

```bash
make compose-build
make compose-up
```

启动或操作单个服务：

```bash
make compose-up SERVICE=postgres
make compose-build SERVICE=app
make compose-logs SERVICE=app
```

停止服务：

```bash
make compose-down
```

Compose 中的 app 服务会基于 `Dockerfile` 构建本地镜像，数据库服务直接使用 PostgreSQL 镜像。
构建完成后，可以通过以下命令查看 Docker 管理的镜像：

```bash
docker images
```

## 常用命令

```bash
make sync          # 同步依赖
make fix           # 执行 Ruff 自动修复
make lint          # 运行 lint 和类型检查
make test          # 运行测试
make coverage      # 运行测试并生成覆盖率报告
make check         # 运行格式修复、lint 和测试
make check-all     # 运行完整本地质量门禁
```

## 许可证

本项目采用 [Apache License 2.0](LICENSE) 许可证。
