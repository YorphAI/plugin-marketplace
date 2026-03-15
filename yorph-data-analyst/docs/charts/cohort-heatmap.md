# Cohort Heatmap — End-to-End Reference

Loaded by: `design-transformation-architecture/SKILL.md`, `pipeline-builder.md` (agent), `build-dashboard/SKILL.md`

Cohort analysis is one of the most insight-rich analyses for subscription, SaaS, e-commerce, and any business with repeat customers. The heatmap is the canonical view. Building it correctly requires careful handling of sparse cohorts, the triangular null region, and period definitions. This file covers everything end-to-end.

---

## When to Use

Use cohort heatmap when the question is about **retention, engagement, or revenue behaviour over time from a starting event.**

**Strong signals:**
- "How well do we retain customers?"
- "Is our retention getting better or worse over time?"
- "Which cohort has the highest LTV?"
- "Are newer cohorts performing differently from older ones?"
- Revenue retention (NRR/GRR) over time

**Two chart types — choose based on the question:**

| Chart | When | What it shows |
|---|---|---|
| **Heatmap** | Comparing cohort behaviour at the same lifecycle stage | Each cell = retention rate at period N for cohort C |
| **Stacked Bar (absolute time)** | Showing how total activity is composed by cohort over calendar time | Each bar = total metric per calendar period, stacked by cohort |

Build both when the architecture calls for cohort analysis — they answer complementary questions.

---

## Key Concepts

**Cohort:** Group of users sharing a starting event in the same time window (usually the week or month of their first purchase, signup, or activation).

**Period elapsed:** Time since cohort start — `0` = the cohort's first period (always 100%), `1` = one period later, etc. Always use relative periods, not calendar dates, so cohorts are comparable.

**Cohort size:** The count at period 0. Fixed. Never changes. Every retention rate divides by this number.

**The triangular null region:** Recent cohorts haven't had time to reach later periods. These cells must render as empty (gray), not 0%. Confusing null with zero is one of the most common cohort mistakes.

**Contractual vs non-contractual:**
- **Contractual** (SaaS, subscriptions): The user explicitly churns. Retention = still subscribed.
- **Non-contractual** (retail, marketplace): Churn is inferred. Define an "active" window (e.g., purchased within the last 30/60/90 days). Document this threshold as an assumption.

---

## Required Pipeline Output

Two tables. The pipeline must produce both.

### Table 1: Long-format cohort retention (for heatmap)

| Column | Type | Description |
|---|---|---|
| `cohort_label` | string | Human-readable label, e.g. "Jan 2024" |
| `cohort_sort` | int | Integer for ordering cohorts top-to-bottom (0 = oldest) |
| `period` | int | Periods elapsed since cohort start (0, 1, 2, …) |
| `cohort_size` | int | Users/accounts in cohort at period 0. Fixed. |
| `retained` | int or null | Active users at this period. **Null** = period hasn't occurred yet. |
| `retention_rate` | float or null | `retained / cohort_size`. **Null** = period hasn't occurred. |
| `is_future` | bool | True if this cell is in the triangular null region |

### Table 2: Absolute-time series (for stacked bar)

| Column | Type | Description |
|---|---|---|
| `cohort_label` | string | Same as above |
| `cohort_sort` | int | Same as above |
| `calendar_period` | string | Calendar date label (e.g., "2024-03") |
| `calendar_sort` | int | Integer for ordering calendar periods left-to-right |
| `metric` | float | Revenue, active users, orders — whatever the analysis tracks |

---

## Python: Computing the Cohort Table

The non-obvious parts: sparse cohort handling, the future-period null mask, and matching period definitions.

```python
import pandas as pd
import numpy as np

def compute_cohort_retention(
    df: pd.DataFrame,
    user_col: str,
    date_col: str,
    value_col: str = None,   # None = count-based; column name = revenue/value-based
    freq: str = 'M'          # 'W' = weekly, 'M' = monthly, 'Q' = quarterly
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Returns (heatmap_df, stacked_bar_df)

    Input: event/transaction table — one row per event, with user_id and date.
    For revenue retention: value_col = revenue column.
    """
    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col])

    # ── 1. Assign cohort (first event date, truncated to period) ─────────────
    first_activity = df.groupby(user_col)[date_col].min().rename('first_date')
    df = df.join(first_activity, on=user_col)
    df['cohort'] = df['first_date'].dt.to_period(freq)
    df['event_period'] = df[date_col].dt.to_period(freq)

    # ── 2. Compute period number (elapsed periods since cohort start) ────────
    df['period'] = (df['event_period'] - df['cohort']).apply(lambda x: x.n)
    df = df[df['period'] >= 0]  # drop events before cohort start (data anomaly)

    # ── 3. Aggregate ─────────────────────────────────────────────────────────
    if value_col:
        agg = df.groupby(['cohort', 'period'])[value_col].sum()
    else:
        agg = df.groupby(['cohort', 'period'])[user_col].nunique()
    agg = agg.reset_index()
    agg.columns = ['cohort', 'period', 'metric']

    # ── 4. Cohort sizes (period 0 only) ──────────────────────────────────────
    sizes = agg[agg['period'] == 0][['cohort', 'metric']].rename(columns={'metric': 'cohort_size'})

    # ── 5. Full grid: every cohort × every period (handles sparse cohorts) ───
    # Without this, cohorts with no activity in a period disappear from results
    all_cohorts = sorted(agg['cohort'].unique())
    max_period = int(agg['period'].max())
    grid = pd.DataFrame(
        [(c, p) for c in all_cohorts for p in range(max_period + 1)],
        columns=['cohort', 'period']
    )

    # ── 6. Join actuals onto full grid ───────────────────────────────────────
    result = grid.merge(agg, on=['cohort', 'period'], how='left')
    result = result.merge(sizes, on='cohort', how='left')

    # ── 7. Mark future periods (the triangular null region) ──────────────────
    # A cell is "future" if the cohort hasn't reached that period yet
    latest_period = df[date_col].dt.to_period(freq).max()
    result['cohort_period_date'] = result.apply(
        lambda r: r['cohort'] + r['period'], axis=1
    )
    result['is_future'] = result['cohort_period_date'] > latest_period

    # Null out future cells — do NOT fill with 0
    result.loc[result['is_future'], 'metric'] = np.nan

    # ── 8. Retention rate ────────────────────────────────────────────────────
    result['retention_rate'] = result['metric'] / result['cohort_size']

    # ── 9. Labels and sort order ─────────────────────────────────────────────
    result['cohort_label'] = result['cohort'].astype(str)
    result['cohort_sort'] = result['cohort'].rank(method='dense').astype(int) - 1

    heatmap_df = result[[
        'cohort_label', 'cohort_sort', 'period',
        'cohort_size', 'metric', 'retention_rate', 'is_future'
    ]].rename(columns={'metric': 'retained'}).sort_values(['cohort_sort', 'period'])

    # ── 10. Absolute-time stacked bar ────────────────────────────────────────
    stacked = df.copy()
    stacked['calendar_period'] = df[date_col].dt.to_period(freq)
    if value_col:
        stacked_agg = stacked.groupby(['cohort', 'calendar_period'])[value_col].sum()
    else:
        stacked_agg = stacked.groupby(['cohort', 'calendar_period'])[user_col].nunique()
    stacked_agg = stacked_agg.reset_index()
    stacked_agg.columns = ['cohort', 'calendar_period', 'metric']
    stacked_agg['cohort_label'] = stacked_agg['cohort'].astype(str)
    stacked_agg['cohort_sort'] = stacked_agg['cohort'].rank(method='dense').astype(int) - 1
    stacked_agg['calendar_period_label'] = stacked_agg['calendar_period'].astype(str)
    stacked_agg['calendar_sort'] = stacked_agg['calendar_period'].rank(method='dense').astype(int) - 1

    stacked_bar_df = stacked_agg[[
        'cohort_label', 'cohort_sort',
        'calendar_period_label', 'calendar_sort', 'metric'
    ]].sort_values(['calendar_sort', 'cohort_sort'])

    return heatmap_df, stacked_bar_df
```

### Edge cases in the computation

**Same user in multiple cohorts is impossible** — cohort is defined by the *first* event. A user can only belong to one cohort. If you see a user appearing in multiple cohorts, there's a duplicate identity issue; flag it.

**Revenue retention (NRR/GRR):** `value_col` = the revenue column. Period 0 cohort size = total revenue in the first period. Divide all subsequent periods by this base. Values can exceed 100% (expansion). Values are not capped at 100%.

**Missing period 0:** If a cohort has no period-0 record, the cohort size is null and all retention rates become null. Flag this — it usually means the cohort definition doesn't match the transaction data.

**Very small cohorts:** A cohort with 3 users will show 33%/67%/100% retention — statistically meaningless. Consider suppressing cohorts below a minimum size (e.g., 30 users) and noting this in the trust report.

---

## JavaScript: Rendering the Heatmap

Chart.js has no native heatmap. Render directly on a `<canvas>` element.

```javascript
function renderCohortHeatmap(canvasId, data, options = {}) {
    /**
     * data: array of {cohort_label, cohort_sort, period, retention_rate, is_future}
     * Renders a cohort × period retention heatmap on a canvas element.
     */
    const canvas = document.getElementById(canvasId);
    const ctx = canvas.getContext('2d');

    // ── Derive grid dimensions ───────────────────────────────────────────────
    const cohorts = [...new Set(data.map(d => d.cohort_label))]
        .sort((a, b) => {
            const sa = data.find(d => d.cohort_label === a).cohort_sort;
            const sb = data.find(d => d.cohort_label === b).cohort_sort;
            return sa - sb;  // oldest cohort first (top row)
        });
    const maxPeriod = Math.max(...data.map(d => d.period));

    const LABEL_W = 90;   // px for cohort labels on left
    const HEADER_H = 36;  // px for period headers on top
    const CELL_W = Math.max(44, Math.floor((canvas.width - LABEL_W) / (maxPeriod + 1)));
    const CELL_H = 34;

    canvas.height = HEADER_H + cohorts.length * CELL_H + 10;

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // ── Color scale: white → blue (retention), gray for future ──────────────
    function cellColor(rate, isFuture) {
        if (isFuture || rate == null) return '#f0f0f0';
        // 0% = light (#eef2ff), 100% = dark blue (#1a3a6b)
        const t = Math.max(0, Math.min(1, rate));
        const r = Math.round(238 + (26 - 238) * t);
        const g = Math.round(242 + (58 - 242) * t);
        const b = Math.round(255 + (107 - 255) * t);
        return `rgb(${r},${g},${b})`;
    }

    function textColor(rate, isFuture) {
        if (isFuture || rate == null) return '#bbb';
        return rate > 0.55 ? '#fff' : '#1a3a6b';
    }

    // ── Draw period headers ───────────────────────────────────────────────────
    ctx.font = '11px -apple-system, sans-serif';
    ctx.textAlign = 'center';
    ctx.fillStyle = '#6c757d';
    for (let p = 0; p <= maxPeriod; p++) {
        const x = LABEL_W + p * CELL_W + CELL_W / 2;
        ctx.fillText(p === 0 ? 'M0' : `M${p}`, x, HEADER_H - 8);
    }

    // ── Draw cohort rows ──────────────────────────────────────────────────────
    cohorts.forEach((cohort, ci) => {
        const y = HEADER_H + ci * CELL_H;

        // Cohort label
        ctx.textAlign = 'right';
        ctx.fillStyle = '#444';
        ctx.font = '12px -apple-system, sans-serif';
        ctx.fillText(cohort, LABEL_W - 8, y + CELL_H / 2 + 4);

        // Cells
        for (let p = 0; p <= maxPeriod; p++) {
            const cell = data.find(d => d.cohort_label === cohort && d.period === p);
            const rate = cell ? cell.retention_rate : null;
            const isFuture = cell ? cell.is_future : true;

            const cx = LABEL_W + p * CELL_W;

            // Cell background
            ctx.fillStyle = cellColor(rate, isFuture);
            ctx.fillRect(cx + 1, y + 1, CELL_W - 2, CELL_H - 2);

            // Cell border
            ctx.strokeStyle = '#e0e0e0';
            ctx.lineWidth = 1;
            ctx.strokeRect(cx + 0.5, y + 0.5, CELL_W - 1, CELL_H - 1);

            // Cell label
            if (!isFuture && rate != null) {
                ctx.textAlign = 'center';
                ctx.fillStyle = textColor(rate, isFuture);
                ctx.font = `${p === 0 ? 'bold ' : ''}11px -apple-system, sans-serif`;
                ctx.fillText(
                    `${(rate * 100).toFixed(0)}%`,
                    cx + CELL_W / 2,
                    y + CELL_H / 2 + 4
                );
            }
        }
    });
}
```

### Sizing the canvas

Set the canvas width in HTML to match the container. Height is computed dynamically by `renderCohortHeatmap` based on the number of cohorts. Set an initial height as a placeholder:

```html
<div class="chart-container" style="overflow-x: auto;">
    <h3>Retention by Cohort</h3>
    <p class="chart-subtitle">% of cohort still active at each period</p>
    <canvas id="cohort-heatmap" width="900" height="400"></canvas>
</div>
```

---

## Chart.js: Stacked Bar (Absolute Time)

The stacked bar showing cohort composition over calendar time uses standard Chart.js. The tricky part is pivoting the long-format data into per-cohort datasets.

```javascript
function renderCohortStackedBar(canvasId, data, valueLabel, format) {
    // data: [{cohort_label, cohort_sort, calendar_period_label, calendar_sort, metric}]

    const periods = [...new Set(data.map(d => d.calendar_period_label))]
        .sort((a, b) => {
            const sa = data.find(d => d.calendar_period_label === a).calendar_sort;
            const sb = data.find(d => d.calendar_period_label === b).calendar_sort;
            return sa - sb;
        });

    const cohorts = [...new Set(data.map(d => d.cohort_label))]
        .sort((a, b) => {
            const sa = data.find(d => d.cohort_label === a)?.cohort_sort ?? 0;
            const sb = data.find(d => d.cohort_label === b)?.cohort_sort ?? 0;
            return sa - sb;
        });

    const datasets = cohorts.map((cohort, i) => ({
        label: cohort,
        data: periods.map(period => {
            const cell = data.find(d => d.cohort_label === cohort && d.calendar_period_label === period);
            return cell ? cell.metric : 0;
        }),
        backgroundColor: COLORS[i % COLORS.length] + 'CC',
        stack: 'cohort',
    }));

    const ctx = document.getElementById(canvasId).getContext('2d');
    return new Chart(ctx, {
        type: 'bar',
        data: { labels: periods, datasets },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'bottom', labels: { usePointStyle: true, padding: 12 } },
                tooltip: {
                    callbacks: {
                        label: c => `${c.dataset.label}: ${fmt(c.parsed.y, format)}`
                    }
                }
            },
            scales: {
                x: { stacked: true, grid: { display: false } },
                y: { stacked: true, ticks: { callback: v => fmt(v, format) } }
            }
        }
    });
}
```

---

## Annotations for Cohort Charts

**Heatmap:**
- Call out the best and worst performing cohort in the chart subtitle: "Best: Jan 2024 (M6 retention: 62%)"
- If there's a clear inflection point (retention improving or worsening from a specific cohort onward), add a vertical line or label: "Product change →"
- Suppress cohorts with < minimum size and note the threshold

**Stacked bar:**
- If total metric is growing but dominated by one cohort, annotate it
- If a cohort is unexpectedly large or small, note the acquisition event

---

## Validation Checks (run before embedding)

```python
def validate_cohort_table(df: pd.DataFrame) -> None:
    # Period 0 must always be 100% retention
    p0 = df[df['period'] == 0]
    bad = p0[p0['retention_rate'].notna() & (p0['retention_rate'] != 1.0)]
    if len(bad) > 0:
        raise ValueError(f"Period 0 retention_rate != 1.0 for cohorts: {bad['cohort_label'].tolist()}")

    # Retention rate must be between 0 and 1 for count-based; >1 allowed for revenue
    over_100 = df[(df['retention_rate'] > 1.0) & (~df['is_future'])]
    if len(over_100) > 0:
        print(f"WARNING: {len(over_100)} cells have retention_rate > 1.0 "
              f"— expected for revenue retention (expansion), not for user retention")

    # No negative retention
    negative = df[(df['retention_rate'] < 0) & (~df['is_future'])]
    if len(negative) > 0:
        raise ValueError(f"Negative retention_rate found: {negative[['cohort_label','period','retention_rate']].head()}")

    # Every cohort must have a period 0
    cohorts_with_no_p0 = set(df['cohort_label']) - set(df[df['period'] == 0]['cohort_label'])
    if cohorts_with_no_p0:
        raise ValueError(f"Cohorts missing period 0: {cohorts_with_no_p0}")
```

---

## Common Pitfalls

| Pitfall | What goes wrong | Fix |
|---|---|---|
| Filling future cells with 0 instead of null | A cohort with 0% retention looks the same as a future cell | Set `is_future = True` and render gray |
| Using calendar period instead of elapsed period | Cohorts aren't comparable — a Jan cohort and Jun cohort are on different calendars | Always use period elapsed (0, 1, 2…) for the heatmap |
| Dividing by current active users instead of cohort size | Denominator shrinks over time, inflating retention | Cohort size = count at period 0, fixed forever |
| Forgetting to cross-join all cohorts × periods | Sparse cohorts drop from the grid entirely | Always build a full grid and left-join actuals onto it |
| Conflating user retention with revenue retention | Both are valid but require different interpretation | Label the chart clearly; for revenue, > 100% is possible |
| Too many cohorts (> 24) | Rows become unreadable | Group older cohorts by quarter, or show rolling 12 months |
| Not defining the activity window for non-contractual | "Retained" is ambiguous for retail | Document the threshold (e.g., "active = purchased in last 60 days") in the trust report |
