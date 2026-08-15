# ORM and Data Model Standards

This document defines constraints for ORM models, database services, repository binding, and persistence data boundaries.

## Model Rules

- Database models inherit from `CustomModel`.
- Model classes use the `Model` suffix.
- Models must annotate `__struct_type__`.
- The service-layer data schema referenced by `__struct_type__` must inherit from `BaseStruct`.
- Models are used only for persistence reads and writes, and do not cross domain data boundaries directly.
- Table names are derived by the base class from class names by default; override them only for compatibility with existing tables.

## Database Service

- Database services inherit from `CustomService[Model]` by default.
- `service.py` only expresses ORM/database services and does not carry pure business workflow orchestration.
- Each concrete database service must explicitly bind its model through an internal `_Repository`.
- `_Repository` inherits from `SQLAlchemyAsyncRepository[Model]` and sets `model_type: type[Model] = Model`.
- Database service classes set `repository_type = _Repository`.
- Do not rely on generic inference as a substitute for repository binding.

Example:

```python
class UserService(CustomService[UserModel]):
    """User database service."""

    class _Repository(SQLAlchemyAsyncRepository[UserModel]):
        """User model repository."""

        model_type: type[UserModel] = UserModel

    repository_type = _Repository
```

## Data Boundaries

- Database reads and writes use `CustomModel`.
- Domain-boundary transfer uses the `BaseStruct` family.
- Convert models to schemas with `to_struct()`.
- Convert schemas to models with `from_struct()`.
- Database services do not return database models to controllers.
- Controllers do not create sessions, repositories, or model queries directly.

## Query Rules

- Paginated queries must validate `limit` and `offset`.
- Sorting fields must be constrained by an allowlist.
- Complex queries may belong in repositories; simple CRUD does not require a separate repository file.
- After query results are returned, convert them first to domain schemas and then to external VOs.
- Do not add query logic in controllers for display convenience.
