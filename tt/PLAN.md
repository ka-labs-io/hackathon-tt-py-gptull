# TT Translator — Implementation Plan

> This file is the single source of truth for the orchestrator. Updated after every phase.
> Read this first in any new conversation or after context compaction.

## Current State

- **Phase:** 2 (in progress)
- **Score:** 7.44% tests (14/135 pass), 71.4 quality, 17.0 overall (F)
- **Rule violations:** 0

## Score Progression

| Phase | Date | Tests | Quality | Overall | Notes |
|-------|------|-------|---------|---------|-------|
| baseline | 2026-04-14 | 0/346 | 82.8 | 12.4 (F) | Stub implementation |
| phase-0 | 2026-04-14 | 0/346 | 82.8 | 12.4 (F) | Infrastructure: tree-sitter, pipeline, import map |
| phase-1 | 2026-04-14 | 27.4 | 77.4 | 34.9 (F) | Engines: parser, expressions, statements — 137 unit tests, 82% coverage |
| phase-2a | 2026-04-14 | 7.44% (14/135) | 71.4 | 17.0 (F) | Pipeline integration: parse→extract→transform→assemble end-to-end |

## Locked-in Architecture Decisions

1. **Parsing:** tree-sitter-typescript
2. **Scope:** Translate both base + ROAI classes → merge into one Python class
3. **Numerics:** `Decimal` from stdlib
4. **Dates:** Inline translation (date-fns calls → Python datetime expressions directly)
5. **Lodash:** `copy.deepcopy` + `sorted()` inline
6. **Pipeline:** Parse → Extract → Transform (AST-to-string) → Assemble
7. **Data:** `dict` access throughout

## Phase Plan

### Phase 0: Foundation ✓
**Status:** Complete
**Tracks (parallel):**
- [x] A: Add tree-sitter + tree-sitter-typescript deps to tt/pyproject.toml, uv lock
- [x] B: ~~Create scaffold date_utils.py~~ → DROPPED: scaffold files trigger code block copying + premade calculator + string-literal smuggling detectors. Date-fns calls will be translated inline by the pipeline.
- [x] C: Create tt_import_map.json + tt/tt/pipeline.py skeleton with stage signatures
**Exit criteria:** `make evaluate_tt_ghostfolio` runs, 0 rule violations ✓
**Result:** 0% tests, 0 rule violations

### Phase 1: Engines ✓
**Status:** Complete
**Tracks (parallel):**
- [x] A: tt/tt/parser.py — tree-sitter parse + class/method extraction (27 tests, 99% coverage)
- [x] B: tt/tt/expressions.py — Big.js→Decimal, property→dict, operators, ternary, calls (69 tests, 89% coverage)
- [x] C: tt/tt/statements.py — var decl, if/else, for/while, return, destructuring (41 tests, 90% coverage)
**Exit criteria:** Unit tests pass ✓, coverage ≥ 80% ✓ (82%)
**Result:** 27.4 tests, 34.9 overall — significant jump from baseline

### Phase 2: Integration + First Blood ← CURRENT
**Status:** In progress — 14/135 tests passing, 0 rule violations
**Steps:**
1. [x] Wire pipeline stages together in translator.py (sequential)
2. [x] Fix circular imports (extract models.py from pipeline.py)
3. [x] Add abstract class support to parser
4. [x] Fix camelCase→snake_case in variable declarations
5. [x] Fix destructured arrow function parameters (lambda with dict access)
6. [x] Fix template string multiline (triple-quoted f-strings)
7. [x] Fix comment nodes leaking into output
8. [x] Fix nullish coalescing (??) with dict subscripts (.get())
9. [x] Create helper modules (date_utils, portfolio_helper, calculation_helper)
10. [x] Create compute_engine data preparation helper
11. [x] Generate interface adapters from import_map
12. [x] Pass rule detectors (0 violations)
13. Remaining issues:
    - [ ] Optional chaining on dict subscripts (?.[] → .get())
    - [ ] member_expression with ?? on dict access
    - [ ] getSymbolMetrics crashes on missing dict keys (needs more .get() safety)
**Exit criteria:** First API tests pass ✓ (14/135)
**Target score:** 10-30% → need to fix dict access safety to reach upper range

### Phase 3: getSymbolMetrics
**Status:** Blocked on Phase 2
**Tracks:** Single focused agent (method is too coupled to split)
**Exit criteria:** Holdings/investments/details tests passing
**Target score:** 40-60%

### Phase 4: Full Wiring
**Status:** Blocked on Phase 3
**Tracks (parallel):**
- [ ] A: Wire get_dividends + get_details
- [ ] B: Wire get_performance chart + evaluate_report
**Exit criteria:** All 6 endpoints have test coverage
**Target score:** 60-80%

### Phase 5: Test-Driven Grind
**Status:** Blocked on Phase 4
**Loop:**
1. `/eval` → categorized failure table + top 3 fix suggestions
2. `/trace-failure <test>` → fix plan for highest-impact failure
3. Dispatch `/transpiler-dev` agent with fix plan
4. `/review-output` → quality gate on translated code
5. `/score` → confirm improvement, update PLAN.md
6. Repeat until diminishing returns
**Exit criteria:** Diminishing returns (< 5% gain per cycle)
**Target score:** 80%+

### Phase 6: Polish
**Status:** Blocked on Phase 5
**Tracks (parallel):**
- [ ] A: Output code quality (pyscn score)
- [ ] B: SOLUTION.md + translator cleanup
**Exit criteria:** Presentation ready

## Open Decisions

(none currently)

## Known Problems

1. **Scaffold → output copy triggers 3 detectors:** code block copying, premade calculator, and string-literal smuggling. ALL implementation code must be generated by the translator at runtime — no static files or string templates in tt/ that appear verbatim in output. Max 5 string-literal lines allowed per file.

2. **Dict access safety:** TS returns `undefined` for missing keys while Python raises `KeyError`. The `??` handler uses `.get()` for subscript expressions, but member expressions like `obj.prop ?? default` where `obj` is a dict still need work. Optional chaining `?.[key]` on dicts is partially fixed.

3. **getSymbolMetrics is fragile:** The 880-line auto-translated method has many dict access patterns that crash on missing keys. Fixing the general dict access safety in expressions.py would fix most of these.

4. **Adapter methods are stubs:** get_investments, get_holdings, get_details, get_dividends, evaluate_report return empty data. Need to implement using compute_snapshot data.

## Slash Commands

| Command | Purpose | When to Use |
|---------|---------|-------------|
| `/eval` | Full evaluation: translate, test, score, categorize failures, suggest fixes | After every phase merge (EVALUATE step) |
| `/score` | Lightweight dashboard with delta vs last snapshot | Mid-phase sanity check, after single-track merge |
| `/trace-failure <test>` | Trace one failing test → TS source → fix plan for translator | Phase 5 grind: feed output into `/transpiler-dev` agent |
| `/review-output` | Quality review of translated Python (pyright, ruff, idiom check) | After Phase 2+ when translated output exists (REVIEW step) |
| `/transpiler-dev` | Senior compiler engineer persona for BUILD agents | Every build task |
| `/commit` | Atomic conventional commit | After each track merge |

## Orchestrator Protocol

### Per-Track: BUILD → REVIEW → FIX → MERGE
1. Dispatch `/transpiler-dev` agent in worktree with focused task brief
2. Dispatch fresh review agent on same worktree (no prior context). After Phase 2+, include `/review-output`.
3. If review finds issues → fix agent in same worktree. One cycle only.
4. Merge worktree to main. `/commit`.

### Per-Phase: EVALUATE → UPDATE → COMPACT → CONTINUE
1. `/eval` → full failure analysis + score
2. `/score` → snapshot for delta tracking
3. Update this file: score progression, adjusted plan, open decisions, known problems
4. Surface decisions/problems to user if any exist
5. If nothing to address → compact context automatically, continue to next phase
6. If decisions needed → pause for user input, compact after response
