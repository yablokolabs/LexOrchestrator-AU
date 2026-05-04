# Contributing to LexOrchestrator-AU

## Development Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
```

## Code Quality

Before submitting changes, ensure all checks pass:

```bash
# Format
ruff format src/ tests/

# Lint
ruff check src/ tests/ --fix

# Type check
mypy src/lexorchestrator_au/ --ignore-missing-imports

# Security scan
bandit -r src/lexorchestrator_au/ -c pyproject.toml

# Tests
pytest tests/ -v --cov=lexorchestrator_au
```

## Project Conventions

- **Python 3.11+** with full type annotations
- **Pydantic v2** for all data models and configuration
- **SQLAlchemy 2.0** async patterns throughout
- **Structured JSON logging** via `StructuredLogFormatter`
- **Ruff** for linting and formatting (replaces black, isort, flake8)
- **Mypy strict mode** for type checking

## Branch Strategy

- `main` — stable, all CI checks pass
- Feature branches — `feature/<description>`
- Bug fixes — `fix/<description>`

## Pull Request Checklist

- [ ] All tests pass (`pytest tests/ -v`)
- [ ] Linting passes (`ruff check src/ tests/`)
- [ ] Type checking passes (`mypy src/lexorchestrator_au/`)
- [ ] New functionality includes tests
- [ ] Documentation updated if applicable
- [ ] No secrets or credentials in code

## Architecture Notes

- **Adapters** implement the `LLMAdapter` Protocol and must include `aclose()` for resource cleanup
- **Circuit breakers** use `asyncio.Lock` for concurrency safety
- **Configuration** uses `pydantic-settings` with production safety validators
- **RAG pipeline** uses HNSW vector index (not IVFFlat) for better empty-table and filtered-query support
