# ORM and Data Model Standards

This document defines constraints for ORM models, services, repository binding, and data object conversion.

## Model Rules

- Database models inherit from `CustomModel`.
- Model classes use the `Model` suffix.
- Models must annotate `__struct_type__`.
- The service-layer data schema referenced by `__struct_type__` must inherit from `BaseStruct`.
- Models are used only for persistence reads and writes, and are not returned directly to controllers.
- Table names are derived by the base class from class names by default; override them only for compatibility with existing tables.

## Service Rules

- ORM services inherit from `CustomService[Model]` by default.
- Each concrete ORM service must explicitly bind its model through an internal `_Repository`.
- `_Repository` inherits from `SQLAlchemyAsyncRepository[Model]` and sets `model_type: type[Model] = Model`.
- Service classes set `repository_type = _Repository`.
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
- Service-layer transfer uses the `BaseStruct` family.
- Convert models to schemas with `to_struct()`.
- Convert schemas to models with `from_struct()`.
- Services do not return database models to controllers.
- Controllers do not create sessions, repositories, or model queries directly.

## Query Rules

- Paginated queries must validate `limit` and `offset`.
- Sorting fields must be constrained by an allowlist.
- Complex queries may belong in repositories; simple CRUD does not require a separate repository file.
- After query results are returned, convert them first to service-layer schemas and then to external VOs.
- Do not add query logic in controllers for display convenience.
