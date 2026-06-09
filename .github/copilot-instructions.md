## Repository Copilot Notes

### Testing

- Always run unit tests using the project virtual environment interpreter.
- From repository root, use: `.venv/bin/python -m pytest ...`
- Do not run tests with system Python, to avoid importing stale site-packages instead of workspace source code.
