---
name: waterfall-chart
description: Load this skill when the analysis involves a waterfall, bridge, or walk chart — for financial attribution, variance decomposition, or any visualization where sequential deltas explain the change between two totals. Contains the required data shape (label, value, bar_type, sort_order), floating bar computation, Chart.js rendering pattern, closure validation, and common pitfalls.
---

# Waterfall Chart — End-to-End Reference

Waterfall charts are one of the most powerful charts for financial and attribution analysis and also one of the most technically tricky to build correctly. This file covers everything: when to use it, how to structure the pipeline data, how to compute the floating bar values, and how to render it in Chart.js.

---

## When to Use

Use a waterfall whenever the story is "here's where we started, here's what moved it, here's where we ended up."

**Strong signals:**
- Budget vs actual variance bridge (how did we get from budget to actual?)
- YoY / MoM revenue walk (what drove the change?)
- PVM bridge (price, volume, mix contributions)
- Attribution analysis (which drivers explain the metric change?)
- P&L bridge (revenue − COGS − OpEx = EBIT, shown as bars)
- Any time the word "bridge" or "walk" is used by the user

**Prefer waterfall over bar chart when:**
- The x-axis represents drivers, factors, or deltas — not independent categories
- You have a starting value and an ending value and want to show the path between them
- Any bar represents a *change* rather than an *absolute level*

---

## The Three Waterfall Types

Understanding which type you're building determines the pipeline computation.

### Type 1: Delta Walk (most common)
Starts at zero. Each bar is a delta (positive or negative). Final bar is the net total.

```
0 → [+Price Effect] → [−Volume Effect] → [+Mix Effect] → Net Total
```

Use for: PVM bridge, attribution analysis, driver decomposition.

### Type 2: Absolute Level Walk
Starts at a real value (e.g., prior year revenue = $10M). Each bar is a delta. Final bar lands at the new absolute level.

```
Prior Year ($10M) → [+New Customers] → [−Churn] → [+Upsell] → Current Year ($12M)
```

Use for: YoY or period-over-period revenue walks. The first and last bars are anchored totals; middle bars are deltas.

### Type 3: Decomposition Walk (P&L style)
Every bar is an absolute component that stacks or subtracts to reach a final result. No "running total" — each bar contributes directly.

```
Revenue ($20M) → [−COGS ($8M)] → [−OpEx ($5M)] → [−Tax ($2M)] → Net Income ($5M)
```

Use for: P&L waterfalls, margin bridges.

---

## Required Pipeline Output

**The pipeline must produce a flat table with exactly these columns:**

| Column | Type | Description |
|---|---|---|
| `label` | string | Bar label shown on x-axis |
| `value` | float | The delta amount (positive or negative). For total/subtotal bars in Type 2/3, this is the absolute level. |
| `bar_type` | string | `increase`, `decrease`, `total`, `subtotal` |
| `sort_order` | int | Explicit ordering (never rely on row order) |

The `running_start` and `running_end` values are **computed from this table**, not stored in it. Compute them in Python before embedding in the dashboard.

### Pipeline output example (PVM bridge)

```
label,value,bar_type,sort_order
Budget Revenue,1000000,total,1
Price Effect,50000,increase,2
Volume Effect,-80000,decrease,3
Mix Effect,30000,increase,4
FX Effect,-20000,decrease,5
Actual Revenue,980000,total,6
```

### Pipeline output example (YoY walk)

```
label,value,bar_type,sort_order
Prior Year Revenue,10000000,total,1
New Customers,800000,increase,2
Expansion Revenue,400000,increase,3
Churn,-600000,decrease,4
Price Changes,200000,increase,5
Current Year Revenue,10800000,total,6
```

---

## Python: Computing Floating Bar Values

This is the most critical and non-obvious step. Chart.js floating bars require `[low, high]` for each bar. You must compute these before embedding.

```python
import pandas as pd

def compute_waterfall_bars(df: pd.DataFrame) -> pd.DataFrame:
    """
    Input: df with columns [label, value, bar_type, sort_order]
    Output: df with added columns [bar_low, bar_high, color]

    bar_type must be one of: 'increase', 'decrease', 'total', 'subtotal'
    - total/subtotal bars are anchored at 0 and span [0, value]
    - increase/decrease bars float: [running_start, running_start + value]
    """
    df = df.sort_values('sort_order').reset_index(drop=True)

    running = 0.0
    bar_lows = []
    bar_highs = []
    colors = []

    COLORS = {
        'increase':  '#55A868CC',   # green
        'decrease':  '#C44E52CC',   # red
        'total':     '#4C72B0CC',   # blue
        'subtotal':  '#8172B3CC',   # purple
    }

    for _, row in df.iterrows():
        btype = row['bar_type']
        val = row['value']

        if btype in ('total', 'subtotal'):
            # Anchored at 0 — reset the running total for what follows a subtotal
            low, high = (min(0, val), max(0, val))
            if btype == 'subtotal':
                running = val  # resume running total from subtotal level
        else:
            # Floating bar
            low  = running if val >= 0 else running + val
            high = running + val if val >= 0 else running
            running += val

        bar_lows.append(round(low, 4))
        bar_highs.append(round(high, 4))
        colors.append(COLORS[btype])

    df['bar_low']  = bar_lows
    df['bar_high'] = bar_highs
    df['color']    = colors
    return df
```

**Critical edge cases:**

- **Negative total bars** (e.g., a net loss): `low = value, high = 0`. The code above handles this with `min(0, val) / max(0, val)`.
- **Subtotals mid-walk**: Set `running = subtotal_value` after placing the subtotal bar so subsequent deltas float from the right base.
- **Very small deltas next to large totals**: The bar may be invisible. Consider labelling it with a minimum visible height and the actual value in the annotation.
- **Restatements / reclasses**: If the same cost gets reclassified mid-walk, you'll get a phantom up + down of equal size. Flag this in the trust report.

---

## Chart.js Rendering

Use the **floating bar** type: `y: [low, high]` per data point. This is native in Chart.js 4.x and is cleaner than the stacked-transparent-bar hack.

```javascript
function renderWaterfall(canvasId, data, valueFormat) {
    // data = output of compute_waterfall_bars(), embedded as JS array
    const ctx = document.getElementById(canvasId).getContext('2d');

    const chart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: data.map(d => d.label),
            datasets: [{
                data: data.map(d => ({ x: d.label, y: [d.bar_low, d.bar_high] })),
                backgroundColor: data.map(d => d.color),
                borderColor:     data.map(d => d.color.replace('CC', 'FF')),
                borderWidth: 1,
                borderRadius: 3,
                borderSkipped: false,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: (ctx) => {
                            const d = data[ctx.dataIndex];
                            const val = d.bar_type === 'total' || d.bar_type === 'subtotal'
                                ? d.value
                                : d.value;  // always show the delta, not the float bounds
                            const sign = d.value > 0 ? '+' : '';
                            return `${sign}${fmt(val, valueFormat)}`;
                        }
                    }
                }
            },
            scales: {
                x: { grid: { display: false } },
                y: {
                    ticks: { callback: v => fmt(v, valueFormat) },
                    grid: { color: 'rgba(0,0,0,0.05)' }
                }
            }
        },
        plugins: [{
            // Connector lines: draw a horizontal dotted line from bar_high of bar N to bar_low of bar N+1
            id: 'waterfall-connectors',
            afterDraw(chart) {
                const ctx = chart.ctx;
                const meta = chart.getDatasetMeta(0);
                ctx.save();
                ctx.setLineDash([4, 4]);
                ctx.strokeStyle = 'rgba(0,0,0,0.25)';
                ctx.lineWidth = 1;

                for (let i = 0; i < meta.data.length - 1; i++) {
                    const curr = meta.data[i];
                    const next = meta.data[i + 1];
                    const currData = data[i];
                    const nextData = data[i + 1];

                    // Connect end of current bar to start of next bar
                    // For increases: connect from bar_high; for decreases: connect from bar_low
                    // For totals: no connector going out (or into the next delta)
                    const yConnect = currData.bar_type === 'total' || currData.bar_type === 'subtotal'
                        ? chart.scales.y.getPixelForValue(currData.value)
                        : chart.scales.y.getPixelForValue(currData.bar_high);

                    const xStart = curr.x + curr.width / 2;
                    const xEnd   = next.x - next.width / 2;

                    ctx.beginPath();
                    ctx.moveTo(xStart, yConnect);
                    ctx.lineTo(xEnd, yConnect);
                    ctx.stroke();
                }
                ctx.restore();
            }
        }]
    });
    return chart;
}
```

### Value labels on bars

Add delta values directly on each bar. Positive deltas label above; negative deltas label below.

```javascript
plugins: [{
    id: 'waterfall-labels',
    afterDatasetsDraw(chart) {
        const ctx = chart.ctx;
        const meta = chart.getDatasetMeta(0);
        ctx.save();
        ctx.font = '11px -apple-system, sans-serif';
        ctx.textAlign = 'center';

        meta.data.forEach((bar, i) => {
            const d = data[i];
            const label = (d.value >= 0 ? '+' : '') + fmt(d.value, valueFormat);
            const yPos = d.value >= 0
                ? chart.scales.y.getPixelForValue(d.bar_high) - 6
                : chart.scales.y.getPixelForValue(d.bar_low) + 14;
            ctx.fillStyle = '#444';
            ctx.fillText(label, bar.x, yPos);
        });
        ctx.restore();
    }
}]
```

---

## Annotations for Waterfall

Always annotate:
1. **The net total** — state the net change as a sentence in the chart subtitle, e.g. "Net: −$20K (−2.0% vs budget)"
2. **The largest driver** — call it out with an arrow or label, e.g. "Volume decline drove 80% of the gap"
3. **Any unexpected direction** — if a normally-positive factor is negative (or vice versa), note it

The chart title should be a sentence: "Q1 Revenue came in $20K below budget, driven by volume decline" — not "Budget vs Actual Bridge."

---

## Common Pitfalls

| Pitfall | What goes wrong | Fix |
|---|---|---|
| Using `row.value` as the tooltip instead of the delta | Total bars show wrong values in tooltip | Always derive tooltip from `d.value`, never from `[bar_low, bar_high]` |
| Forgetting `borderSkipped: false` | Chart.js skips the border on one side of floating bars, looks wrong | Always set `borderSkipped: false` |
| Not sorting by `sort_order` before computing running total | Bars in wrong order, running total corrupted | Always sort before computing `bar_low / bar_high` |
| Subtotal resets running total to wrong value | Subsequent bars float from wrong base | After placing subtotal bar, set `running = subtotal_value` |
| Including both a "start" total and deltas that sum to a different "end" total | Walk doesn't close | Validate: `start + sum(deltas) == end` before rendering |
| Connector lines drawn incorrectly for negative bars | Connectors float in wrong place | Connect from `bar_low` (not `bar_high`) for decrease bars |
| Too many bars (>12) | Labels overlap, chart becomes unreadable | Group small drivers into an "Other" bucket |

### Validation check (always run before embedding)

```python
def validate_waterfall(df: pd.DataFrame) -> None:
    deltas = df[df['bar_type'].isin(['increase', 'decrease'])]['value'].sum()
    totals = df[df['bar_type'] == 'total']['value'].tolist()
    if len(totals) >= 2:
        expected_end = totals[0] + deltas
        actual_end   = totals[-1]
        if abs(expected_end - actual_end) > 0.01:
            raise ValueError(
                f"Waterfall doesn't close: start({totals[0]}) + deltas({deltas:.2f}) "
                f"= {expected_end:.2f} but end total = {actual_end:.2f}"
            )
```
