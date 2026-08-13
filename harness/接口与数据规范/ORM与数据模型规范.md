# ORM 与数据模型规范

本文档约束 ORM 模型、服务、仓储绑定和数据对象转换规则。

## 模型规则

- 数据库模型继承 `CustomModel`。
- 模型类使用 `Model` 后缀。
- 模型必须标注 `__struct_type__`。
- `__struct_type__` 指向的服务层 data schema 必须继承 `BaseStruct`。
- 模型只用于持久化读写，不直接返回给 controller。
- 表名默认由基类按类名转换；只有兼容既有表时才覆盖。

## 服务规则

- ORM 服务默认继承 `CustomService[Model]`。
- 每个具体 ORM 服务必须通过内部 `_Repository` 显式绑定模型。
- `_Repository` 继承 `SQLAlchemyAsyncRepository[Model]`，并设置 `model_type: type[Model] = Model`。
- 服务类设置 `repository_type = _Repository`。
- 不依赖泛型推断替代 repository 绑定。

示例：

```python
class UserService(CustomService[UserModel]):
    """User database service."""

    class _Repository(SQLAlchemyAsyncRepository[UserModel]):
        """User model repository."""

        model_type: type[UserModel] = UserModel

    repository_type = _Repository
```

## 数据边界

- 数据库读写使用 `CustomModel`。
- 服务层传递使用 `BaseStruct` 系列。
- 模型转 schema 使用 `to_struct()`。
- schema 转模型使用 `from_struct()`。
- service 不向 controller 返回数据库模型。
- controller 不直接创建会话、仓储或模型查询。

## 查询规则

- 分页查询必须校验 `limit` 和 `offset`。
- 排序字段必须白名单约束。
- 复杂查询可放入 repository；简单 CRUD 不强制新增独立 repository 文件。
- 查询返回后先转换为服务层 schema，再转换为对外 VO。
- 不为方便展示而在 controller 中补查询逻辑。
