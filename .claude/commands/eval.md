Run the full evaluation pipeline and produce a structured failure analysis.

## Steps

1. Run `make evaluate_tt_ghostfolio` and capture the full output (this translates, spins up the server, runs tests, and scores).
2. Parse the test results. For each failing test, extract:
   - Test name and file (e.g. `test_btcusd.py::test_get_performance`)
   - The assertion that failed and the actual vs expected values
   - The error type (AssertionError, KeyError, TypeError, ImportError, etc.)
3. Categorize every failure into one of these root causes:
   - **missing-rule**: No translation pass handles the TS construct yet
   - **wrong-mapping**: A pass exists but produces incorrect Python
   - **import-error**: Missing or wrong import in translated output
   - **type-error**: Type mismatch in translated code
   - **runtime-error**: Translated code crashes (AttributeError, KeyError, etc.)
   - **stub-return**: Method returns a stub/zero value instead of computed result
4. Print a compact dashboard:
   ```
   Tests: XX/113 passing (XX/346 points)
   Code quality: <grade> (output) / <grade> (translator)
   Overall score: XX.X
   ```
5. Print a failure table sorted by estimated fix effort (easiest first):
   ```
   | # | Category       | Count | Example test                  | Root cause summary            |
   |---|----------------|-------|-------------------------------|-------------------------------|
   | 1 | stub-return    |    42 | test_no_orders::test_perf     | get_performance returns zeros |
   ```
6. For the top 3 highest-impact failure groups (most tests fixed per effort), suggest a concrete next step: which TS construct to look at, which translation pass to add or fix.

## Rules

- Do not modify any files — this is a read-only analysis skill.
- If the server fails to start, report the startup error and suggest a fix before retrying.
- If `make evaluate_tt_ghostfolio` times out, fall back to `make scoring` for just the score, and run `pytest projecttests/ghostfolio_api/ -x --tb=short` separately for failure details.
- Keep the total output concise — no more than 60 lines of dashboard + table + recommendations.
