# CLAUDE.md

## Code style

### Functional

- Prefer higher-order functions and lambdas over imperative loops
- Compose small, single-purpose functions
- Keep cyclomatic complexity low — one logical path per function
- One return per function
- Immutable data: `@dataclass(frozen=True)` or `NamedTuple` over mutable objects
- `Protocol` over abstract base classes
- `TypeAlias` and `NewType` for domain primitives

### Naming

- No code comments — use descriptive, self-documenting names instead
- Domain-driven names over function-driven names (e.g. `PortfolioSnapshot` not `DataContainer`)
- Names must make the code readable without explanation

### Typing

- Strict typing everywhere
- Explicit `__all__` in every module
- No bare `except`

## Tooling

- **Package manager**: `uv` — never use `pip` directly
- **Formatter/linter**: `ruff`
- **Type checker**: `pyright` (strict mode)
- **Tests**: `pytest` with `pytest-cov`
- **Coverage threshold**: 80%
- **Pre-commit**: `pre-commit` runs ruff and pyright before every commit

All tool configuration lives in `tt/pyproject.toml`.

## Competition scoring (quick reference)

- **85%** — API test pass rate (`make evaluate_tt_ghostfolio`)
- **12%** — code quality of translated output (`translations/ghostfolio_pytx/`)
- **3%** — code quality of the translator (`tt/tt/`)

Pass more tests first. Clean translated output second. Clean translator third.

### Hard rules
- `tt` must **not** use LLMs for translation
- No pre-written financial/domain logic in `tt/` — output must come from actual translation
- Only write to `app/implementation/` — never modify `app/wrapper/` or `app/main.py`
- No hardcoded project-specific import paths in `tt/` core

### Key paths
- Source: `projects/ghostfolio/apps/api/src/app/portfolio/calculator/roai/portfolio-calculator.ts`
- Output: `translations/ghostfolio_pytx/app/implementation/portfolio/calculator/roai/portfolio_calculator.py`
- Interface: `translations/ghostfolio_pytx_example/app/wrapper/portfolio/calculator/portfolio_calculator.py`
