Run the scoring pipeline and display a compact competition dashboard.

## Steps

1. Run `make scoring` and capture the output. This runs:
   - `evaluate/scoring/successfultests.py` — test pass rate and weighted score
   - `evaluate/scoring/codequality.py` — code quality grades for translated output and translator
   - `evaluate/scoring/overall.py` — combined score

2. If a previous score snapshot exists at `.claude/last-score.json`, load it for comparison.

3. Print the dashboard:
   ```
   ===== COMPETITION SCOREBOARD =====

   Tests:      XX/113 passing   (XXX/346 points)   [+N / -N since last]
   Quality:    Output: <grade>   Translator: <grade>
   Overall:    XX.X / 100                           [+X.X since last]

   Breakdown (85/12/3):
     Test score:       XX.X / 85
     Output quality:   XX.X / 12
     Translator quality: XX.X / 3
   ==================================
   ```

4. Save the current scores to `.claude/last-score.json` for future diffs:
   ```json
   {
     "timestamp": "<ISO datetime>",
     "tests_passing": N,
     "tests_total": 113,
     "test_points": N,
     "test_points_total": 346,
     "output_quality_grade": "<A-F>",
     "translator_quality_grade": "<A-F>",
     "overall_score": N.N
   }
   ```

5. If the score decreased, flag it with a warning and suggest running `/eval` to investigate.

## Rules

- Only modify `.claude/last-score.json` — no other file writes.
- If `make scoring` fails because no test results exist, tell the user to run `/eval` first.
- Keep the output under 20 lines.
