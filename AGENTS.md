# KLT - KoboToolbox Data Pipeline

## Commands
- **Run pipeline**: `uv run klt`
- **Tests**: `uv run pytest` (all), `uv run pytest tests/test_file.py::test_name` (single), `uv run pytest-watcher` (watch mode)
- **Format/lint**: `uv run ruff check --fix && uv run ruff format`
- **Pre-commit**: `pre-commit run --all-files`

## Code Style
- **Imports**: Organize as stdlib, third-party (dlt, loguru, requests, etc.), local (from klt...). Use relative imports for internal modules (`..logging`, `..rest_client`)
- **Formatting**: Ruff for all formatting and linting; pre-commit enforces trailing whitespace, EOF fixes, TOML/YAML validation, and typo checks
- **Type hints**: Optional but preferred for function signatures and public APIs; use `|` for unions (e.g., `Session | CachedSession | None`)
- **Naming**: snake_case for functions/variables; factory pattern: `make_resource_*()`, `make_*_client()`; test fixtures: `*_builder`, `*_stub`, `*_factory`
- **Error handling**: Let exceptions bubble up; use loguru logger for info/debug messages via `http_log` hooks
- **Resources**: Use `@dlt.resource` decorator with `primary_key`, `name`, and `parallelized` parameters; apply `.add_filter()` for data filtering
- **Incremental hints**: Define via `dlt.sources.incremental()` with `cursor_path`, `initial_value`, `on_cursor_value_missing` ("include" or "raise")
- **Tests**: Pytest fixtures from conftest (pipeline, builders, stubs, quality); arrange-act-assert pattern with docstrings; use `rest_client_stub.set_for_path()` for API mocking
- **DLT pipeline config**: Use `pipelines_dir="./dlt_pipelines"`, `write_disposition="merge"`, `progress="log"`

## Project Structure
- `src/klt/`: Pipeline code (resources, models, REST client, CLI, logging)
- `tests/`: Test suite with fixtures in `tests/fixtures/` (builders, stubs, pipeline, quality)
- `.dlt/config.toml`: DLT configuration and secrets
- `pytest.ini`: Pytest config with import mode and warning filters

## Git Workflow
- **IMPORTANT**: Never create commits, issues, pull requests, merge PRs, or merge branches without explicit user confirmation
- Always draft the commit message or PR description first and wait for user approval before executing
- When asked to commit changes, follow these steps:
  1. Run `git status` and `git diff` to show what will be committed
  2. Draft a commit message and present it to the user
  3. Wait for confirmation before running `git commit`
- When asked to create a PR:
  1. Draft the PR title and body based on the PR template
  2. Present the draft to the user
  3. Wait for confirmation before running `gh pr create`
- When asked to merge a PR or branch:
  1. Show the PR/branch details and changes
  2. Present merge strategy (squash, merge commit, rebase) and confirm with user
  3. Wait for explicit confirmation before running merge commands

## Tools
- When working with DLT pipelines, querying pipeline metadata, or analyzing data, use the `dlt` MCP tools
