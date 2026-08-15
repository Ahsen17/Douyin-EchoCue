# Git Project Management Standards

This document defines constraints for branch, commit, and Git metadata related project management workflows. Command entry points, tests, and quality checks follow the Project Command Standards and Testing Standards respectively.

## Branch Strategy

- Before starting a new milestone, feature, or larger change, create an independent feature branch from the current baseline.
- Do not develop feature changes directly on the main branch or long-lived shared branches.
- Branch names should express the work scope, preferably using prefixes such as `feature/`, `fix/`, or `docs/`.
- A branch should contain only changes that belong to the same milestone or feature scope.
- If unrelated work appears on the current branch, split it out or pause before expanding the review scope further.

## Atomic Commits

- Split implementation into reviewable atomic subtasks, where each subtask contains one clear behavior or documentation goal.
- After completing each atomic subtask, run tests and quality checks that match the change scope before committing.
- Use a separate commit for each atomic subtask, and avoid mixing unrelated changes, formatting, refactoring, and feature work in the same commit.
- Commit messages should accurately describe the subtask result and should not use vague descriptions whose intent cannot be traced.
- If a commit must include both production code and tests, the tests should cover only behavior introduced or changed by that commit.

## Execution Environment Limits

- If the current execution environment cannot create branches, run required services, or write Git metadata, stop the commit action and state the limitation.
- When Git metadata is read-only, the Docker daemon is inaccessible, or required local services are unavailable, do not fabricate validation results.
- Branching, validation, and commit actions that require full project permissions should be performed in an environment with the corresponding permissions.
