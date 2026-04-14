Trace a failing test back to the TypeScript source and produce a fix plan for the translator.

Usage: `/trace-failure <test_name_or_pattern>`

If `$ARGUMENTS` is empty, pick the single highest-impact failing test from the most recent test run (re-run `pytest projecttests/ghostfolio_api/ --tb=line -q` if needed).

## Steps

1. **Find the test**: Locate the test in `projecttests/ghostfolio_api/` matching `$ARGUMENTS`. Read the test function body to understand what API endpoint it calls, what input data it uses, and what assertion it makes.

2. **Trace the call chain**: Follow the test's client call (e.g. `client.get_performance()`) through:
   - `projecttests/ghostfolio_api/client.py` — which HTTP endpoint does it hit?
   - `translations/ghostfolio_pytx/app/wrapper/portfolio/portfolio_controller.py` — which controller method handles it?
   - `translations/ghostfolio_pytx/app/wrapper/portfolio/portfolio_service.py` — what does the service call?
   - `translations/ghostfolio_pytx/app/wrapper/portfolio/calculator/portfolio_calculator.py` — what abstract method must the implementation provide?
   - `translations/ghostfolio_pytx/app/implementation/portfolio/calculator/roai/portfolio_calculator.py` — what does the current implementation return?

3. **Find the TS source**: Read the corresponding TypeScript logic in `projects/ghostfolio/apps/api/src/app/portfolio/calculator/roai/portfolio-calculator.ts` (and parent classes if needed). Identify the exact TS code block that computes the expected value.

4. **Identify the gap**: Compare what the TS source does vs what the translated Python does. Pinpoint:
   - Which TS constructs are not translated (or mistranslated)
   - What the correct Python output should look like
   - Which translation pass in `tt/tt/translator.py` is responsible (or missing)

5. **Produce the fix plan** in this format:
   ```
   ## Trace: <test_name>

   **Expected**: <what the test asserts>
   **Actual**: <what the implementation returns>
   **TS source**: <file:line range> — <brief description of the logic>

   ### Gap
   <1-3 sentences: what's missing or wrong in the translation>

   ### Fix
   - **Pass**: <new or existing pass name in translator.py>
   - **TS pattern**: `<regex or literal TS pattern to match>`
   - **Python output**: `<what it should generate>`
   - **Estimated impact**: fixes ~N tests in <test_file(s)>
   ```

## Rules

- Do not modify any files — this is a read-only analysis skill.
- If the test name matches multiple tests, trace the simplest one first and note the others.
- Always show the actual TS source lines, not a summary — the user needs to see the exact pattern.
- Keep the output under 80 lines.
