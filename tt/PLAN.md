# TT Translator — Implementation Plan

> This file is the single source of truth for the orchestrator. Updated after every phase.
> Read this first in any new conversation or after context compaction.

## Current State

- **Phase:** 0 (not started)
- **Score:** 0/346 tests (0%), 82.8 quality, 12.4 overall (F)
- **Rule violations:** 0

## Score Progression

| Phase | Date | Tests | Quality | Overall | Notes |
|-------|------|-------|---------|---------|-------|
| baseline | 2026-04-14 | 0/346 | 82.8 | 12.4 (F) | Stub implementation |

## Locked-in Architecture Decisions

1. **Parsing:** tree-sitter-typescript
2. **Scope:** Translate both base + ROAI classes → merge into one Python class
3. **Numerics:** `Decimal` from stdlib
4. **Dates:** Thin helper module in scaffold (`date_utils.py`)
5. **Lodash:** `copy.deepcopy` + `sorted()` inline
6. **Pipeline:** Parse → Extract → Transform (AST-to-string) → Assemble
7. **Data:** `dict` access throughout

## Phase Plan

### Phase 0: Foundation ← CURRENT
**Status:** Not started
**Tracks (parallel):**
- [ ] A: Add tree-sitter + tree-sitter-typescript deps to tt/pyproject.toml, uv lock
- [ ] B: Create scaffold date_utils.py (format_date, is_before, difference_in_days, add_milliseconds, each_year_of_interval, is_this_year)
- [ ] C: Create tt_import_map.json + tt/tt/pipeline.py skeleton with stage signatures
**Exit criteria:** `make evaluate_tt_ghostfolio` runs, 0 rule violations
**Target score:** 0% tests (infrastructure only)

### Phase 1: Engines
**Status:** Blocked on Phase 0
**Tracks (parallel):**
- [ ] A: tt/tt/parser.py — tree-sitter parse + class/method extraction + unit tests
- [ ] B: tt/tt/expressions.py — Big.js→Decimal, property→dict, operators, ternary, calls + unit tests
- [ ] C: tt/tt/statements.py — var decl, if/else, for/while, return, destructuring + unit tests
**Exit criteria:** Unit tests pass, coverage ≥ 80%
**Target score:** 0% (still building)

### Phase 2: Integration + First Blood
**Status:** Blocked on Phase 1
**Steps:**
1. Wire pipeline stages together in translator.py (sequential)
2. Parallel tracks:
   - [ ] A: Translate calculateOverallPerformance → wire get_performance
   - [ ] B: Translate base class logic → wire get_holdings + get_investments
**Exit criteria:** First API tests pass
**Target score:** 10-30%

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
**Loop:** eval → diagnose failures → fix translator → merge → eval
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

(none currently)

## Orchestrator Protocol

After each phase:
1. Run /eval → update score progression table
2. Adjust phase plan based on results (reorder, add/remove tracks)
3. Surface decisions/problems to user if any
4. If nothing to address → compact context and continue automatically
5. If decisions needed → pause for user input
