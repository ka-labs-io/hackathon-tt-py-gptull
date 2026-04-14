Review the translated Python output for quality issues and suggest translator improvements.

## Steps

1. Read the translated output at `translations/ghostfolio_pytx/app/implementation/portfolio/calculator/roai/portfolio_calculator.py`.

2. Run `pyright` on the translated file:
   ```
   cd translations/ghostfolio_pytx && uv run pyright app/implementation/portfolio/calculator/roai/portfolio_calculator.py
   ```
   Collect all type errors.

3. Run `ruff check` on the translated file:
   ```
   cd translations/ghostfolio_pytx && uv run ruff check app/implementation/portfolio/calculator/roai/portfolio_calculator.py
   ```
   Collect all lint violations.

4. Read the file and assess against these quality criteria:
   - **Idiomatic Python**: frozen dataclasses over mutable dicts, StrEnum over string literals, Protocols over ABCs, list comprehensions over imperative loops
   - **Naming**: snake_case, domain-driven names, self-documenting (no comments needed)
   - **Typing**: strict types everywhere, no `Any`, no bare `except`, explicit return types
   - **Structure**: small single-purpose functions, low cyclomatic complexity, one return per function
   - **Artifacts**: leftover TypeScript syntax, untranslated variable names (camelCase), dead code, hardcoded values that should come from translation

5. Cross-reference with the TypeScript source at `projects/ghostfolio/apps/api/src/app/portfolio/calculator/roai/portfolio-calculator.ts` to identify:
   - TS constructs that were translated but could be more idiomatic
   - TS constructs that were dropped or stubbed
   - Opportunities for cleaner mapping (e.g. Big.js → Decimal)

6. Print a structured report:
   ```
   ## Output Quality Review

   **pyright**: N errors, N warnings
   **ruff**: N violations

   ### Type errors (fix these first)
   - line:col — description → suggested fix

   ### Idiom issues (improve output quality score)
   | Line | Issue | Current | Suggested |
   |------|-------|---------|-----------|
   | 42   | mutable dict | dict(...) | @dataclass(frozen=True) |

   ### Translator improvements
   For each issue above that stems from the translator (not hand-edits):
   - Which translation pass produces the problematic output
   - What the pass should generate instead
   - Whether this is a new pass or a fix to an existing one
   ```

7. Prioritize issues by their likely impact on the code quality score (12% of competition).

## Rules

- Do not modify any files — this is a read-only analysis skill.
- If additional translated files exist beyond the main calculator, review those too.
- Skip issues that would be fixed by passing more tests (e.g. stub methods) — focus on quality of code that already exists.
- Keep the report under 60 lines.
