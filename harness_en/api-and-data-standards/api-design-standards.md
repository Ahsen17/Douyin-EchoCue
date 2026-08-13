# API Design Standards

This document defines constraints for HTTP API paths, methods, parameters, responses, and error boundaries. Project APIs explicitly follow RESTful style and should model around resources first. Data structure details are governed by the Data Structure and Response Standards.

## RESTful Principles

- APIs are modeled around resources.
- Paths express resource hierarchy, and HTTP methods express operation semantics.
- Regular CRUD does not use verbs in paths.
- Non-resource actions must be rare exceptions and expressed through action sub-resources.
- Do not customize non-resource interfaces for a single page or frontend component.

## Route Naming

- Paths use lowercase kebab case, for example `/user-profiles`.
- Resource paths use nouns, not verbs.
- Collection resources use plural semantics.
- Sub-resources are expressed through hierarchy, for example `/users/{user_id}/sessions`.
- Login-state APIs are modeled as session resources, for example `POST /auth/session` and `DELETE /auth/session`.
- System-level APIs belong in independent controllers, for example `/health`.
- Do not expose internal implementation details, database table names, or third-party platform details in paths.

## HTTP Methods

- `GET`: Query resources and produce no business side effects.
- `POST`: Create resources; use it for non-resource actions only when they cannot be modeled as resources.
- `PUT`: Replace a resource as a whole.
- `PATCH`: Update part of a resource.
- `DELETE`: Delete or deactivate a resource.

For actions that do not naturally map to resource CRUD, use clear action sub-resources such as `/tasks/{task_id}/cancellation`; avoid verb paths such as `/cancel-task`.

## Route Declarations

- Controllers inherit from `litestar.Controller`.
- Every route declares `path`, `operation_id`, and `summary`.
- `operation_id` uses the `domain:action` format, for example `system:health`.
- Controller return types annotate the specific `GenericResponse` generic.
- Controllers do not manually concatenate response dictionaries.

## Parameter Rules

- Path parameters express resource identifiers.
- Query parameters express filtering, sorting, pagination, and lightweight switches.
- Request bodies express create, update, or complex operation payloads.
- External fields in request bodies and query parameters use camel case by default.
- Path parameters and route placeholders remain lower snake case.
- Pagination parameters are uniformly `limit` and `offset`.
- `limit` must be greater than 0, and `offset` must not be less than 0.
- Sorting fields must be constrained by an allowlist; do not directly trust external field names.

## Response Rules

- Successful responses uniformly use `GenericResponse`.
- Paginated responses uniformly use `GenericResponse[Pagination]`.
- External fields use camel case by default.
- Responses must not expose internal exceptions, connection strings, secrets, stack information, or local paths.
- Empty result lists return an empty list, not `None`.

## Error Boundaries

- Business errors are converted by the centralized exception handling layer.
- Controllers do not manually assemble error dictionaries.
- Error messages should express understandable reasons for callers without leaking internal implementation.
- When stable error codes are required, group them by domain and keep them backward compatible.
