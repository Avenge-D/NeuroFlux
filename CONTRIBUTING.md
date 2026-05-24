# Contributing to NeuroFlux

Thank you for your interest in contributing! 🎉

## How to Contribute

### Reporting Bugs

Open a [GitHub Issue](../../issues/new?template=bug_report.md) with:
- A clear title and description
- Steps to reproduce
- Expected vs actual behaviour
- Relevant log output (redact any secrets!)

### Suggesting Features

Open a [Feature Request](../../issues/new?template=feature_request.md) with:
- A clear description of the problem you're solving
- Your proposed solution
- Any alternatives you've considered

### Submitting a Pull Request

1. **Fork** the repository and create a branch from `main`:
   ```bash
   git checkout -b feat/my-feature
   ```

2. **Make your changes** following the code style guidelines below.

3. **Test** your changes manually (and add automated tests if applicable).

4. **Commit** using [Conventional Commits](https://www.conventionalcommits.org/):
   ```
   feat: add Pexels video caching layer
   fix: handle empty search queries gracefully
   docs: update configuration reference
   ```

5. **Push** and open a Pull Request against `main`.

## Code Style Guidelines

- **Python 3.12+** — use `match/case`, `X | Y` union types, `asyncio` patterns
- **Type hints** everywhere — functions must be fully annotated
- **Structured logging** — use `logger.bind(component=...)` and pass key-value pairs; never use f-strings in log messages
- **No secrets in code** — all configuration must come from `config.py` / `.env`
- **Error handling** — let `tenacity` handle retries on external calls; always log the exception with `exc_info=True`

## Development Setup

```bash
git clone https://github.com/<your-username>/NeuroFlux.git
cd NeuroFlux
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env
# Fill in your API keys in .env
python -m orchestrator
```

## Questions?

Open a [Discussion](../../discussions) — we're happy to help.
