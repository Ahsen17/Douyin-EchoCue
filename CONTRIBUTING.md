# Contributing to Douyin-EchoCue

[English](CONTRIBUTING.md) | [简体中文](CONTRIBUTING_zh.md)

Thanks for contributing. This project accepts AI-assisted coding, but every contributor is responsible for the
final change quality, validation, and reviewability.

## Required Workflow

1. Fork the repository.
2. Clone your fork and create a dedicated branch.
3. Make the change in a focused scope.
4. Run the required checks before opening a PR.
5. Open the pull request from your fork to the upstream repository.

Direct PRs from branches on the upstream repository are not the normal contribution path.

## What Must Be True Before a PR

A PR should only be opened when the change is ready for review and the following conditions are met:

- The change is complete for its intended scope.
- The code is formatted and lint-clean.
- Relevant tests pass.
- Type checks pass when the change touches shared abstractions, database behavior, response structures, or other typed
  boundaries.
- Coverage is updated or reviewed when the change meaningfully affects shared or high-risk behavior.
- No secrets, local-only configuration, or unrelated work are included.
- The PR description explains the change and the validation that was run.

## Recommended Validation

- Documentation-only changes: `make check` when feasible.
- Ordinary code changes: `make test` and `make lint` when feasible.
- Changes involving types, shared abstractions, databases, or response structures: `make type-check` and `make coverage`
  when feasible.
- Larger or riskier changes: run the strongest feasible validation for the affected area before opening the PR.

## Branch and Commit Discipline

- Keep branches narrow in scope.
- Use atomic commits when practical.
- Avoid mixing unrelated refactors, formatting, and feature work in the same PR.

## AI-Assisted Work

AI-assisted implementation is allowed.

If you use AI tools:

- verify the generated code yourself,
- run the relevant checks,
- make sure the final PR reflects your own review and judgment.

