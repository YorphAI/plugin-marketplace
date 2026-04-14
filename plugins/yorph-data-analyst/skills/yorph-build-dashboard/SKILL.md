---
name: yorph-build-dashboard
description: Produce a self-contained HTML dashboard using Chart.js that visualizes the analysis findings. Load this skill every time insights have been produced — it is a required part of the delivery phase alongside insights and trust-report. Also load it when the user asks to "show me a chart", "build a dashboard", "visualize this", "plot this", "graph this", "chart the results", or any request for visual representation of data. Every chart should support a named finding from the insights — no chart exists without a reason.
---

# Skill: Visualizations

Produce a **single self-contained HTML file** using Chart.js. Data is embedded as JS variables — no server, no external dependencies beyond CDN-loaded Chart.js. The dashboard tells the story of the insights; every chart is there for a reason.

## Complex chart references

Some charts have their own dedicated shared skill covering full rendering implementations. Load these before building the relevant chart:

- **Waterfall / bridge / walk** → load the `yorph-waterfall-chart` skill — floating bar setup, connector lines, value labels, closure validation, and common pitfalls. Do not attempt to build a waterfall from scratch; use that reference.
- **Cohort heatmap + stacked bar** → load the `yorph-cohort-heatmap-chart` skill — canvas-based heatmap rendering, stacked bar for absolute time, color scale, null cell handling, and annotations. Always build both charts together.

---

## Dashboard Anatomy

Every dashboard follows this layout. Sections are ordered by importance — the user sees the most important things first.

```
┌─────────────────────────────────────────────┐
│  Header: title, subtitle (data period/scope)│
├─────────────────────────────────────────────┤
│  KPI Row: 3–5 headline numbers              │
├─────────────────────────────────────────────┤
│  Chart Grid: 1–4 charts in a responsive grid│
├─────────────────────────────────────────────┤
│  Data Table (optional): sortable detail view│
├─────────────────────────────────────────────┤
│  Footer: data freshness, caveats            │
└─────────────────────────────────────────────┘
```

**Mandatory sections:** Header, KPI Row, at least one chart.
**Optional:** Data table (include only when the user needs to inspect rows, not just the story).

---

## Base HTML Template

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dashboard Title</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.5.1" integrity="sha384-jb8JQMbMoBUzgWatfe6COACi2ljcDdZQ2OxczGA3bGNeWe+6DChMTBJemed7ZnvJ" crossorigin="anonymous"></script>
    <script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns@3.0.0" integrity="sha384-cVMg8E3QFwTvGCDuK+ET4PD341jF3W8nO1auiXfuZNQkzbUUiBGLsIQUE+b1mxws" crossorigin="anonymous"></script>
    <style>/* see CSS section below */</style>
</head>
<body>
<div class="dashboard-container">
    <header class="dashboard-header">
        <div>
            <h1>Dashboard Title</h1>
            <p class="dashboard-subtitle">Period · Scope · Key caveat if any</p>
        </div>
    </header>

    <section class="kpi-row"><!-- KPI cards --></section>
    <section class="chart-row"><!-- Charts --></section>
    <!-- optional: <section class="table-section"> -->

    <footer class="dashboard-footer">
        Data as of: <span id="data-date"></span> · <span id="caveat"></span>
    </footer>
</div>
<script>
    // ── DATA (pre-aggregated, never embed raw rows) ──────────────────────────
    const KPIS = { /* key: {value, prev, format} */ };
    const CHART_DATA = { /* named datasets per chart */ };

    // ── COLORS ───────────────────────────────────────────────────────────────
    const COLORS = ['#4C72B0','#DD8452','#55A868','#C44E52','#8172B3','#937860'];
    const POS = '#28a745', NEG = '#dc3545';

    // ── INIT ─────────────────────────────────────────────────────────────────
    document.addEventListener('DOMContentLoaded', () => {
        renderKPIs();
        renderCharts();
    });
</script>
</body>
</html>
```

---

## Data Embedding Rules

Pre-aggregate in Python before embedding. Never embed raw rows.

| Dataset size | Strategy |
|---|---|
| < 1,000 rows | Embed directly |
| 1,000–10,000 | Pre-aggregate for charts; embed only if table needed |
| > 10,000 | Pre-aggregate only. No raw embed. |

```javascript
// DO: pre-aggregate in Python, embed summaries
const CHART_DATA = {
    monthly_revenue: [
        { month: '2024-01', revenue: 150000, orders: 1200 },
        ...  // 12 rows, not 50,000
    ]
};

// DON'T: embed raw transaction rows
```

Chart performance limits: line charts ≤500 points/series, bar charts ≤50 categories, scatter ≤1,000 points.

---

## KPI Cards

Show 3–5 numbers. Always include period-over-period change where meaningful.

```javascript
function renderKPI(id, value, prev, format) {
    document.getElementById(id).textContent = fmt(value, format);
    if (prev != null && prev !== 0) {
        const pct = ((value - prev) / Math.abs(prev)) * 100;
        const el = document.getElementById(id + '-change');
        el.textContent = `${pct >= 0 ? '+' : ''}${pct.toFixed(1)}% vs prior`;
        el.className = `kpi-change ${pct >= 0 ? 'positive' : 'negative'}`;
    }
}

function fmt(v, format) {
    if (format === 'currency') return v >= 1e6 ? `$${(v/1e6).toFixed(1)}M` : v >= 1e3 ? `$${(v/1e3).toFixed(1)}K` : `$${v.toFixed(0)}`;
    if (format === 'percent') return `${v.toFixed(1)}%`;
    if (format === 'number')  return v >= 1e6 ? `${(v/1e6).toFixed(1)}M` : v >= 1e3 ? `${(v/1e3).toFixed(1)}K` : v.toLocaleString();
    return String(v);
}
```

---

## Chart Planning

Before writing any HTML, plan the dashboard by reviewing four inputs:

1. **Glimpse output** — column names, types, cardinality, null rates, and value ranges. This tells you what's actually computable.
2. **Pipeline step outputs** — what columns, groupings, and aggregations the pipeline produced. You can only chart what exists in the output.
3. **User's goal and language** — the words they used ("why did revenue drop", "show me retention", "compare regions") are strong signals for chart type.
4. **Insights already surfaced** — each chart should visualize one of the named insights. If an insight has no supporting chart, add one. If a chart has no supporting insight, cut it.

### Planning discipline

For each chart you plan, write out:
- **What it shows**: the specific pipeline output being visualized
- **Which insight it supports**: the named finding from the insights step
- **Why this chart type**: one sentence on why this type is more appropriate than a generic bar or line

Cap at **3–5 charts**. More charts fragment attention. If you have 6 candidate charts, cut the weakest two.

### Prefer specialized charts over generic ones

When a specialized chart fits, use it. It is almost always more compelling than a generic bar or line. Default to specialized; fall back to bar/line only when the data doesn't justify it.

| Situation | Prefer | Instead of |
|---|---|---|
| Metric changed — what drove it? | Waterfall | Grouped bar |
| Conversion through ordered stages | Funnel | Horizontal bar |
| What factors matter most, and in which direction? | Tornado | Sorted bar |
| User retention across cohorts | Cohort Heatmap + Stacked Bar | Multiple line chart |
| How do entities flow between groups? | Sankey | Stacked bar |
| Compare entities on many dimensions | Radar | Multiple bar charts |
| Single variable distribution shape | Histogram | Bar chart |
| Distribution across multiple groups | Box Plot | Overlapping histograms |

### Anti-patterns — never do these

- **Line chart for discrete, unordered categories** (e.g., product names, regions). Use bar chart.
- **Overlapping histograms for group comparison.** Colors merge and the chart becomes unreadable. Use Box Plot.
- **Bar chart for distribution shape.** If the question is "what does the spread look like?", use Histogram or Box Plot.
- **Stacked Area with >5 series or non-additive metrics.** The lower bands become unreadable. Use a small-multiple line chart or filter to top N series.
- **Pie or Donut charts.** Never. Human eyes cannot compare arc lengths accurately. Use a ranked horizontal bar chart instead.
- **Multi-line chart with >5 series and no filtering.** The chart becomes a spaghetti plot. Filter to top N or key series; annotate the most important one.
- **Double-axis combo charts when the two metrics aren't causally related.** Dual axes imply a relationship. Only use combo (bar + line) when the secondary metric explains the primary (e.g., revenue bars + conversion rate line).

---

## Chart Selection

Choose the most specific chart type that fits the analytical intent.

### Sequential stage drop-off → **Funnel**
Ordered stages with a metric that decreases (users, sessions, leads). Prefer over Bar when semantics are "stage progression." Label the biggest drop-off stage with the drop percentage.

### Start-to-end bridge via additive/subtractive deltas → **Waterfall**
Variance bridges, budget walks, attribution analysis. When the x-axis represents drivers or time periods and each bar is a delta, Waterfall is almost always the right choice. Users love Waterfall for anything financial or attribution-related. → Load the `yorph-waterfall-chart` skill.

### Sensitivity / directional impact drivers → **Tornado**
When the question is "what matters most" and sign matters. Drivers on Y, impact magnitude on X. Prefer over a sorted bar chart whenever both positive and negative drivers are present.

### Flow between groups → **Sankey**
Source → target relationships (stage transitions, traffic sources, channel attribution). Prefer over Stacked Bar when movement or path is the story, not composition.

### Pairwise relationships among peers → **Chord**
Symmetric transfers or handoffs between categories. Only appropriate when the bidirectionality matters; otherwise use Sankey.

### Multi-metric entity comparison → **Radar**
Comparing teams, models, vendors across many scaled metrics. Cap at ≤20 metrics. All axes must be on comparable scales; do not use Radar when units differ drastically across dimensions.

### Distribution analysis
- Single variable shape → **Histogram** — not a bar chart of grouped counts
- Distribution across groups → **Box Plot** — not overlapping histograms (they become unreadable with >2 groups)

### Correlation between two numerics → **Scatter Plot**
Avoid if >10k points and not pre-aggregated. Add a trend line when the correlation direction is part of the insight.

### Time / ordered trend
- One metric, ≤50 x-values → **Bar Chart** (preferred over Line for fewer data points)
- One metric, >50 x-values → **Line Chart**
- Magnitude/volume emphasis → **Area Chart**
- Two metrics, comparable scale → **Double Line Chart**
- Mixed units/scales (e.g. revenue + rate) → **Combo** (bar + line) — only when the two metrics are causally related
- Components summing to a meaningful total over time → **Stacked Area** (≤5 series only; more series makes lower bands unreadable)

### Categorical comparison / ranking
- Single metric by category → **Bar Chart** (flip to horizontal if >8 categories or labels are long)
- Totals + composition → **Stacked Bar**
- Never use Line chart for unordered categories (product names, regions, segments)

### Cohort analysis → load the `yorph-cohort-heatmap-chart` skill
Always build both charts together — they answer complementary questions:
- Retention table (cohort × period elapsed × rate) → **Heatmap** (canvas rendered)
- Cohort contribution over absolute calendar time → **Stacked Bar** with cohort as series
Do not use a multi-line chart for cohort retention — lines overlap and the triangular null region becomes confusing.

### When data is high-cardinality or hard to chart cleanly → **Table**
A clean sortable table beats a cluttered chart. Use when there are >15 categories or the user needs to inspect individual rows.

---

## Annotations

Every chart should carry the insight, not just the data. The agent decides what to annotate based on the insight it supports.

**What to annotate:**
- Mark change-points on time series (a vertical line or shaded region with a label: "Checkout deploy")
- Label the largest bar/driver with its value and what it means
- On waterfall charts, label the net total bar and the two or three largest contributors
- On funnels, label the biggest drop-off stage with the drop percentage
- On retention heatmaps, call out the cohort with the worst/best retention

**How in Chart.js:** Use the annotation plugin, or draw directly on the canvas via `afterDraw`. For simplicity, a text overlay div positioned over the chart works well and requires no extra library.

```javascript
// Simple text annotation overlay approach
// Position a div absolutely over the chart canvas
// Set in afterRender or just size it manually with known data
function addAnnotation(chartId, text, xPct, yPct) {
    const container = document.getElementById(chartId).parentElement;
    container.style.position = 'relative';
    const ann = document.createElement('div');
    ann.className = 'chart-annotation';
    ann.textContent = text;
    ann.style.cssText = `position:absolute;left:${xPct}%;top:${yPct}%;
        background:rgba(0,0,0,0.7);color:#fff;padding:3px 7px;
        border-radius:4px;font-size:11px;pointer-events:none;white-space:nowrap;`;
    container.appendChild(ann);
}
```

---

## Key Chart.js Patterns

### Line Chart
```javascript
new Chart(ctx, {
    type: 'line',
    data: { labels, datasets: datasets.map((ds, i) => ({
        label: ds.label, data: ds.data,
        borderColor: COLORS[i], backgroundColor: COLORS[i] + '20',
        borderWidth: 2, tension: 0.3, pointRadius: 3, pointHoverRadius: 6, fill: false,
    }))},
    options: {
        responsive: true, maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: { legend: { position: 'top' } },
        scales: { x: { grid: { display: false } }, y: { beginAtZero: true } }
    }
});
```

### Bar Chart (auto-flips to horizontal when >8 categories)
```javascript
const isHorizontal = labels.length > 8;
new Chart(ctx, {
    type: 'bar',
    data: { labels, datasets: [{ data, backgroundColor: COLORS.map(c => c + 'CC'), borderRadius: 4 }] },
    options: {
        responsive: true, maintainAspectRatio: false,
        indexAxis: isHorizontal ? 'y' : 'x',
        plugins: { legend: { display: false } },
    }
});
```

### Waterfall
See the `yorph-waterfall-chart` skill — full floating bar implementation, connector lines, value labels, Python computation, and closure validation. Do not implement from scratch.

### Heatmap (built on custom canvas rendering, not native Chart.js)
```javascript
// Heatmaps are better rendered manually on a canvas than with Chart.js
// Use a simple grid draw with color interpolation
function drawHeatmap(canvasId, data, xLabels, yLabels, minVal, maxVal) {
    const canvas = document.getElementById(canvasId);
    const ctx = canvas.getContext('2d');
    const cellW = canvas.width / xLabels.length;
    const cellH = canvas.height / yLabels.length;
    data.forEach((row, yi) => {
        row.forEach((val, xi) => {
            const t = (val - minVal) / (maxVal - minVal);
            ctx.fillStyle = `rgba(76, 114, 176, ${t.toFixed(2)})`;
            ctx.fillRect(xi * cellW, yi * cellH, cellW, cellH);
            ctx.fillStyle = t > 0.5 ? '#fff' : '#333';
            ctx.fillText(val != null ? (val * 100).toFixed(0) + '%' : '', xi * cellW + cellW/2, yi * cellH + cellH/2);
        });
    });
}
```

---

## CSS Design System

```css
:root {
    --bg-primary: #f8f9fa; --bg-card: #ffffff; --bg-header: #1a1a2e;
    --text-primary: #212529; --text-secondary: #6c757d; --text-on-dark: #ffffff;
    --positive: #28a745; --negative: #dc3545; --neutral: #6c757d;
    --gap: 16px; --radius: 8px;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: var(--bg-primary); color: var(--text-primary); line-height: 1.5; }
.dashboard-container { max-width: 1400px; margin: 0 auto; padding: var(--gap); }
.dashboard-header { background: var(--bg-header); color: var(--text-on-dark);
    padding: 20px 24px; border-radius: var(--radius); margin-bottom: var(--gap); }
.dashboard-header h1 { font-size: 20px; font-weight: 600; }
.dashboard-subtitle { font-size: 13px; color: rgba(255,255,255,0.6); margin-top: 4px; }

/* KPI row */
.kpi-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: var(--gap); margin-bottom: var(--gap); }
.kpi-card { background: var(--bg-card); border-radius: var(--radius);
    padding: 20px 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
.kpi-label { font-size: 12px; color: var(--text-secondary); text-transform: uppercase;
    letter-spacing: 0.5px; margin-bottom: 4px; }
.kpi-value { font-size: 28px; font-weight: 700; margin-bottom: 4px; }
.kpi-change { font-size: 13px; font-weight: 500; }
.kpi-change.positive { color: var(--positive); }
.kpi-change.negative { color: var(--negative); }

/* Chart grid */
.chart-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(420px, 1fr));
    gap: var(--gap); margin-bottom: var(--gap); }
.chart-container { background: var(--bg-card); border-radius: var(--radius);
    padding: 20px 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); position: relative; }
.chart-container h3 { font-size: 14px; font-weight: 600; margin-bottom: 4px; }
.chart-subtitle { font-size: 12px; color: var(--text-secondary); margin-bottom: 16px; }
.chart-container canvas { max-height: 300px; }

/* Table */
.table-section { background: var(--bg-card); border-radius: var(--radius);
    padding: 20px 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); overflow-x: auto; }
.data-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.data-table thead th { text-align: left; padding: 10px 12px;
    border-bottom: 2px solid #dee2e6; color: var(--text-secondary);
    font-weight: 600; font-size: 12px; text-transform: uppercase;
    letter-spacing: 0.5px; cursor: pointer; user-select: none; }
.data-table tbody td { padding: 10px 12px; border-bottom: 1px solid #f0f0f0; }
.data-table tbody tr:hover { background: #f8f9fa; }

/* Footer */
.dashboard-footer { text-align: center; font-size: 12px;
    color: var(--text-secondary); padding: 16px 0; }

/* Responsive */
@media (max-width: 768px) {
    .kpi-row { grid-template-columns: repeat(2, 1fr); }
    .chart-row { grid-template-columns: 1fr; }
}
@media print {
    body { background: white; }
    .dashboard-container { max-width: none; }
    .chart-container { break-inside: avoid; }
}
```

---

## Principles

- **One dashboard, one story.** Every chart must support a specific headline insight. If you can't name the insight a chart supports, cut the chart.
- **Lead with numbers.** KPI cards are the first thing the eye goes to. Make them count.
- **Annotate the insight, not just the data.** The chart title says what it shows; the annotation says what it means.
- **Each chart title is a sentence, not a label.** "Revenue by Month" is a label. "Revenue grew 23% driven by Q4 enterprise deals" is a title.
- **Pre-aggregate everything.** Never embed raw rows. Compute in Python, embed the summary.
- **Simpler is better.** A clean bar chart with a good annotation beats a complex multi-series chart every time for a non-technical audience.
