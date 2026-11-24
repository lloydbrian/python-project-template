# ADR 0010: Service baseline: factory, health, request ID, JSON logs, typed settings

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-11-23 |
| **Decided by** | LBD |
## Context
v1's service template had only a CLI. Each project added health checks, logging and configuration differently, and some added them only after an incident.

## Decision
The `service` variant starts with:
- `create_app(settings)` factory, so tests build apps with explicit settings.
- `/health/live` (process up; trivial) and `/health/ready` (ready for traffic; extend for dependencies).
- Request-ID middleware: reuse a caller's `X-Request-ID` only if it matches `^[A-Za-z0-9._-]{1,64}$` (log-injection safe), else generate one; echo it on every response; log access lines inside the request context.
- JSON logging with the request ID (`LOG_JSON=false` for local readability).
- `pydantic-settings` with `Literal` and range-checked fields that fail at start-up; real environment variables win over `.env.<APP_ENV>`; secrets declared as `SecretStr`.

## Consequences
- Each behaviour has a test, and negative controls prove the settings validation, request-ID sanitising and health contract tests catch regressions.
- The smoke test runs the image read-only with all capabilities dropped and checks both endpoints and the request-ID echo.
