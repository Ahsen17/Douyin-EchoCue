# Douyin-EchoCue

[![Python](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/)
[![Framework](https://img.shields.io/badge/framework-Litestar-20232a.svg)](https://litestar.dev/)
[![Package Manager](https://img.shields.io/badge/package%20manager-uv-654ff0.svg)](https://docs.astral.sh/uv/)
[![Code Style](https://img.shields.io/badge/code%20style-ruff-46a2f1.svg)](https://docs.astral.sh/ruff/)
[![License](https://img.shields.io/badge/license-Apache--2.0-green.svg)](LICENSE)

[English](README.md) | 简体中文

Douyin-EchoCue 是一个面向抖音主播的弹幕互动回复和提词助手，基于 Python 3.12 和 Litestar 构建，
结合 SQLAlchemy、Redis session、结构化配置、数据库迁移以及项目封装的开发命令。

## 特性

- 通过 `app = "echocue.asgi:entrypoint"` 暴露 Litestar 应用命令入口。
- 使用 `src` 布局，并明确划分 base、shared、server、controller、domain、database 等边界。
- 通过 `Config.get()` 从 `config.yaml` 加载类型化配置，并支持运行时环境变量覆盖。
- 集成 SQLAlchemy 数据库能力，并通过项目 CLI 暴露迁移命令。
- Makefile 封装依赖同步、代码检查、测试、覆盖率和 Docker Compose 维护命令。
- 自动化测试位于 `tests`，并按被测包结构镜像组织。

## 环境要求

- Python 3.12
- uv
- Docker，用于本地 Compose 运行环境
- PostgreSQL，用于本地或容器化数据库运行环境

## 快速开始

安装依赖：

```bash
make install
```

查看项目命令：

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

默认配置从 `config.yaml` 加载。启动应用前，可以在本地配置文件中调整数据库配置，或使用配置层支持的
运行时环境变量覆盖。

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

只操作单个服务：

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
构建完成后，可以用下面的命令查看 Docker 管理的镜像：

```bash
docker images
```

## 常用命令

```bash
make sync          # 同步依赖
make fix           # 执行 Ruff 自动修复
make lint          # 执行代码检查和类型检查
make test          # 运行测试
make coverage      # 运行测试并生成覆盖率报告
make check         # 执行格式修复、代码检查和测试
make check-all     # 执行完整本地质量门禁
```

## 项目结构

```text
src/echocue/
  base/        基础 schema、配置和常量
  shared/      跨领域响应、上下文、日志和数据基础能力
  server/      Litestar 装配、插件、中间件、日志和 OpenAPI 设置
  controller/  HTTP 控制器和路由聚合
  core/        业务领域模块
  auth/        认证领域
  db/          数据库迁移和数据库资源
  lib/         轻量纯工具
tests/                自动化测试
.codex/harness/       中文工程规范
.codex/harness_en/    英文工程规范
```

## 配置

应用配置集中在 `Config.get()`，默认读取 `config.yaml`。配置层支持的运行时覆盖通过 `ECHOCUE_*`
环境变量提供。

不要提交本地密钥、生产凭据、私有连接串或机器相关配置。

## 测试

运行默认测试：

```bash
make test
```

运行覆盖率：

```bash
make coverage
```

API 测试应使用 Litestar 测试工具，不直接启动外部网络服务。数据库、Redis 和文件系统资源应通过 fixture
隔离。

## 开发规范

项目变更必须遵守 `harness/` 或 `harness_en/` 下的工程规范。修改规范本身时，需要同步维护中英文版本。

提交变更前，按影响范围运行可行的最高强度校验：

```bash
make check
```

涉及共享抽象、数据库行为、类型或响应结构时，还应运行：

```bash
make type-check
make coverage
```

## 许可证

本项目使用 [Apache License 2.0](LICENSE) 许可证。
