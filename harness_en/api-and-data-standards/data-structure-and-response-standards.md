# Data Structure and Response Standards

This document defines constraints for data structures, request and response handling, pagination, and Pydantic model usage boundaries. ORM details are governed by the ORM and Data Model Standards.

## Default Choices

- Regular data structures inherit from `BaseStruct` by default.
- HTTP request parameters and external response fields inherit from `CamelizedBaseStruct` by default.
- Requests and responses use `GenericResponse` by default.
- Paginated responses use `GenericResponse[Pagination]` by default.
- Database persistence models inherit from `CustomModel` by default; see the ORM and Data Model Standards for specific rules.
- `pydantic.BaseModel` is not the default choice and is used only when it provides clear benefits or is required by external dependencies.

## Naming Conventions

- Database model: `UserModel`.
- Service-layer data structure: `UserStruct`.
- Create input: `UserCreate`.
- Update input: `UserUpdate`.
- External presentation object: `UserVO`.
- Service class: `UserService`.

For the same entity, split schemas by creation, update, service-layer transfer, external presentation, and database persistence.

## Request and Service-Layer Structures

- Request body and query parameter schemas inherit from `CamelizedBaseStruct` by default.
- Path parameter names remain consistent with route placeholders and still use lower snake case.
- External HTTP fields use camel case by default for both frontend input parameters and response output.
- Create inputs do not include database-maintained fields such as `id`, `created_at`, and `updated_at`.
- Update inputs should clearly distinguish between "do not update" and "update to empty".
- Service-layer transfer objects use `BaseStruct` and do not depend on HTTP response structures.
- Services do not return database models to controllers.

## External Presentation and Responses

- API external presentation objects use the `VO` suffix and inherit from `CamelizedBaseStruct`.
- VOs do not directly reuse database models.
- VOs do not expose passwords, tokens, connection strings, internal states, soft-delete markers, or other sensitive fields.
- Return a single object with `GenericResponse[UserVO]`.
- Return non-paginated lists with `GenericResponse[list[UserVO]]`.
- Return paginated data with `GenericResponse[Pagination]`.
- Error responses are converted by the centralized exception handling layer.

## Pagination Structure

- `Pagination.data` is always the current page data list.
- `Pagination.length` is the actual number of items returned on the current page.
- `Pagination.next_offset` is the offset for the next page.
- Even when there is no next page, `next_offset` remains an `int` and returns `offset + length`.
- `Pagination.total` may be `None`.
- Accurate `total` queries are not required by default; query exact `total` only when the frontend explicitly needs page count or total count.

## Pydantic Boundaries

Allowed scenarios for using `pydantic.BaseModel`:

- A third-party dependency explicitly requires it.
- A framework integration boundary must use it.
- Complex validation, field constraints, or ecosystem reuse provides clear benefits.

When using Pydantic, convert explicitly to and from the `BaseStruct` family. Do not use Pydantic as the default schema base class.

## Time Fields

- Time fields uniformly use timezone-aware `datetime`.
- External time output must not lose timezone information.
- Tests should also construct times with fixed timezone-aware values.
