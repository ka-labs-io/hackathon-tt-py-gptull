# Phase 3 Briefing: getSymbolMetrics

> Read this before starting Phase 3. Contains full algorithm spec, translator gaps, and test priorities.

## Method Stats

- **880 lines**, ~50 local variables, cyclomatic complexity ~50
- Returns `SymbolMetrics` with **28 properties** (Big decimals + date-keyed maps)
- Self-contained: no service calls inside — all data passed in by `computeSnapshot()`

## Algorithm (6 phases)

### Phase 1: Validation (lines ~196–302)
- Filter `this.activities` by symbol; return zero metrics if empty
- Detect CASH assets via assetSubClass
- Extract market prices at start/end dates; MANUAL dataSource uses activity unitPrice as fallback
- Missing prices after first activity → return error state

### Phase 2: Synthetic Order Injection (lines ~304–333)
- Inject synthetic "start" order at `start` date with `unitPriceAtStartDate`
- Inject synthetic "end" order at `end` date with `unitPriceAtEndDate`
- Group actual + synthetic orders by date into `ordersByDate` map

### Phase 3: Time Series Expansion (lines ~344–382)
- Iterate chartDates (sorted keys of chartDateMap) from start to end
- If date in ordersByDate → assign market data to orders
- Otherwise → synthesize pseudo-order (BUY, zero quantity) with market data
- Forward-fill `lastUnitPrice`

### Phase 4: Temporal Ordering (lines ~385–405)
- Sort all orders by date; start orders get -1ms, end orders get +1ms (stable sort)
- Identify indices of start/end synthetic orders

### Phase 5: Main Loop (lines ~410–779) — for each order:
1. **DIVIDEND/INTEREST/LIABILITY**: qty × unitPrice, apply exchange rate, accumulate totals
2. **Start order price**: use next order's price if first, else unitPriceAtStartDate
3. **Base currency prices**: unitPrice × exchangeRate (current vs order-date for currency effect)
4. **Market prices**: unitPriceFromMarketData × exchangeRate
5. **Investment before transaction**: totalUnits × marketPrice
6. **BUY**: qty × unitPrice × factor(+1), accumulate for average price
7. **SELL**: average cost basis × qty × factor(-1), compute gross performance from sell
8. **Update totals**: totalInvestment, totalUnits, initialValue, fees
9. **Time-weighted investment**: differenceInDays × investmentValue, accumulate

### Phase 6: Final Calculations (lines ~781–930)
- Gross/net performance = performance - performanceAtStartDate - fees
- Time-weighted average = sumOfTimeWeightedInvestments / totalInvestmentDays
- Percentages = performance / timeWeightedAverage
- Date range maps: for each of [1d, 1y, 5y, max, mtd, wtd, ytd] + yearly intervals

## Output Structure (SymbolMetrics)

**Date-keyed maps** (9): `currentValues`, `currentValuesWithCurrencyEffect`, `netPerformanceValues`, `netPerformanceValuesWithCurrencyEffect`, `investmentValuesAccumulated`, `investmentValuesAccumulatedWithCurrencyEffect`, `investmentValuesWithCurrencyEffect`, `timeWeightedInvestmentValues`, `timeWeightedInvestmentValuesWithCurrencyEffect`

**Range-keyed maps** (2): `netPerformancePercentageWithCurrencyEffectMap`, `netPerformanceWithCurrencyEffectMap`

**Aggregate Big decimals**: grossPerformance, netPerformance, totalInvestment, timeWeightedInvestment, initialValue (each with WithCurrencyEffect variant), feesWithCurrencyEffect

**Dividend/Interest/Liability totals**: totalDividend, totalInterest, totalLiabilities (each with InBaseCurrency variant)

**Flags**: `hasErrors` (boolean)

## Critical Translator Gaps

These patterns appear in getSymbolMetrics but may not be handled by Phase 1 engines:

| Pattern | Frequency | Example | Python Translation |
|---------|-----------|---------|-------------------|
| Optional chaining `?.` on nested dict | 40+ | `marketSymbolMap[date]?.[symbol]` | `.get(date, {}).get(symbol)` |
| Nullish coalescing `??` | 40+ | `fee ?? new Big(0)` | `fee if fee is not None else Decimal(0)` |
| `.toFixed(n)` | 15+ | `value.toFixed(2)` | `f"{value:.2f}"` or `quantize()` |
| `.toNumber()` | 10+ | `big.toNumber()` | `float(decimal_val)` |
| `.abs()` | few | `value.abs()` | `abs(decimal_val)` |
| `.at(-1)` on arrays | 2 | `orders.at(-1)` | `orders[-1]` |
| `instanceof Big` | 1 | `value instanceof Big` | `isinstance(value, Decimal)` |
| Template literals `${}` | 15+ | debug logging | f-strings |
| String date comparison | 4 | `dateString < startDateString` | Same in Python (ISO format) |
| `Object.keys().sort()` | 1 | | `sorted(dict.keys())` |

## External Helpers to Translate/Inline

1. **`getFactor(type)`** — returns 1 for BUY, -1 for SELL, 0 otherwise (from `portfolio.helper.ts`)
2. **`getIntervalFromDateRange(dateRange)`** — returns `{start, end}` for range strings like '1y', 'max' (from `calculation-helper`)

## Big.js Operations Used

`.mul()`, `.div()`, `.plus()`, `.minus()`, `.add()`, `.eq()`, `.gt()`, `.gte()`, `.lt()`, `.lte()`, `.abs()`, `.toNumber()`, `.toFixed(n)` — all map to Python `Decimal`

## date-fns Operations Used

- `format(date, DATE_FORMAT)` → `date.strftime("%Y-%m-%d")`
- `differenceInDays(d1, d2)` → `(d1 - d2).days`
- `eachYearOfInterval({start, end})` → list comprehension over year range
- `addMilliseconds(date, ms)` → `date + timedelta(milliseconds=ms)`
- `isThisYear(date)` → `date.year == datetime.now().year`

## lodash Operations Used

- `cloneDeep(array)` → `copy.deepcopy(array)`
- `sortBy(array, fn)` → `sorted(array, key=fn)`

## Test Priority (what to target for max score)

| Endpoint | Total Tests | Currently Passing | Gap |
|----------|-------------|-------------------|-----|
| Investments | 25 | ~18 | 7 (quick win) |
| Performance | 26 | ~8 | 18 (biggest swing, needs getSymbolMetrics) |
| Holdings | 23 | ~6 | 17 (high value) |
| Details | 15 | ~4 | 11 (needs performance first) |
| Dividends | 10 | ~3 | 7 |
| Report | 9 | ~3 | 6 (skip for now) |

**Phase 3 unlocks Performance + Details = 41 tests combined = biggest score jump possible.**

## Investments Quick Wins (7 failing tests, independent of Phase 3)

The `get_investments(group_by)` endpoint already passes 18/25 tests. The 7 failures are:

### What's failing and how to fix

**1. Monthly grouping (2 tests)**
- Tests like `test_investments_by_month` expect investments aggregated by month
- Group historicalData's `investmentValueWithCurrencyEffect` by `YYYY-MM` prefix
- Return dates as `YYYY-MM-01`, values summed per month

**2. Yearly grouping (2 tests)**
- Same as monthly but group by `YYYY` prefix, return dates as `YYYY-01-01`

**3. Daily/ungrouped investments (1-2 tests)**
- Return per-transaction-point investment values (one entry per date with activity)
- Must include sells as negative investment values

**4. Currency effect field (cross-cutting)**
- Grouping must use `investmentValueWithCurrencyEffect`, NOT `totalInvestment`
- Wrong field = wrong grouped values even if grouping logic is correct

**5. Sells as negative (cross-cutting)**
- Sales must record as negative investment (e.g., `-151.6`)
- If only summing buys, grouped totals will be too high

### Implementation approach
The fix is in the translated `get_investments()` method — it needs to:
1. Access `self.snapshot.historicalData` (or equivalent from computeSnapshot)
2. For each entry, extract `investmentValueWithCurrencyEffect`
3. If `group_by == "month"`: aggregate by `YYYY-MM`, return as `YYYY-MM-01`
4. If `group_by == "year"`: aggregate by `YYYY`, return as `YYYY-01-01`
5. If no grouping: return daily values from transaction points
