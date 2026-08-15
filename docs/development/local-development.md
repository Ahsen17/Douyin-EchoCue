# 本地开发启动

本文档描述 M1 阶段的本地启动、数据库迁移和健康检查流程。

## 前置条件

- Python 3.12。
- `uv`。
- Docker。
- Docker Compose v2，可通过 `docker compose version` 验证。

## 使用已有 PostgreSQL 容器

如果 PostgreSQL 已经在 Docker 中启动，先确认 `config.yaml` 中的连接串可用：

```yaml
alchemy:
  url: "postgresql+asyncpg://ahsen:ahsen@localhost:5432/aigc"
```

然后执行：

```bash
make sync
uv run app database upgrade
uv run app run
```

健康检查：

```bash
curl http://localhost:8000/system/health
```

## 使用项目 Compose

启动 PostgreSQL：

```bash
docker compose up -d postgres
```

执行数据库迁移：

```bash
uv run app database upgrade
```

启动主后端：

```bash
uv run app run
```

也可以构建并启动 Compose 中的主后端：

```bash
docker compose up --build app
```

## 环境变量覆盖

默认配置仍从 `config.yaml` 读取。需要在不同运行环境覆盖配置时，优先使用环境变量：

| 环境变量 | 对应配置 |
| --- | --- |
| `AIGC_APP_HOST` | `app.host` |
| `AIGC_APP_PORT` | `app.port` |
| `AIGC_APP_REQUEST_MAX_BODY_SIZE_MB` | `app.request_max_body_size_mb` |
| `AIGC_ALCHEMY_URL` | `alchemy.url` |
| `AIGC_ALCHEMY_ECHO` | `alchemy.echo` |
| `AIGC_ALCHEMY_POOL_DISABLED` | `alchemy.pool_disabled` |
| `AIGC_REDIS_DSN` | `redis.dsn` |
| `AIGC_LOGGING_LEVEL` | `logging.level` |
| `AIGC_LOGGING_FORMAT` | `logging.format` |
| `AIGC_LOGGING_FILE_ENABLED` | `logging.file.enabled` |
| `AIGC_LOGGING_FILE_PATH` | `logging.file.path` |
| `AIGC_AUTH_SESSION_COOKIE_SECURE` | `auth.session_cookie_secure` |

布尔值支持 `1`、`true`、`yes`、`on` 和 `0`、`false`、`no`、`off`。

## M1 验收

完成 M1 收尾时至少验证：

```bash
uv run app database upgrade
uv run app run
curl http://localhost:8000/system/health
```

健康检查响应应为 `GenericResponse` 结构，`message` 为 `ok`。
