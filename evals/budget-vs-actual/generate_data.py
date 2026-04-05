"""
Budget vs. Actual Eval — Data Generator

Simulates a B2B company with:
- 6 products, ~40 customers
- Monthly grain: customer × product × month
- Full fiscal year (Jan–Dec 2024)
- Budgeted and actual sales & COGS
- Intentional budget gaps:
  1. Customers in actuals with NO budget (new wins mid-year)
  2. Customers in budget with NO actuals (deals that fell through)
  3. Customers with budget for some months but gaps in others (mid-year forecast additions)
- Otherwise clean data

Run: python3 generate_data.py
"""

import csv
import random
import os
from collections import defaultdict

random.seed(42)

OUT_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(OUT_DIR, exist_ok=True)

# ─────────────────────────────────────────────
# Products
# ─────────────────────────────────────────────

PRODUCTS = [
    # name, avg_unit_price, avg_cogs_pct (of revenue), seasonality_profile
    ("SKU-A", 1200, 0.55, "flat"),          # Core product, steady
    ("SKU-B", 800, 0.60, "h2_heavy"),       # Back-half loaded
    ("SKU-C", 3500, 0.45, "flat"),          # Premium, high margin
    ("SKU-D", 450, 0.65, "seasonal_q4"),    # Consumable, Q4 spike
    ("SKU-E", 2000, 0.50, "front_loaded"),  # Project-based, H1 heavy
    ("SKU-F", 600, 0.70, "flat"),           # Low margin commodity
]

def seasonality_multiplier(profile, month):
    """Monthly seasonality multiplier."""
    if profile == "flat":
        return 1.0 + random.gauss(0, 0.03)
    elif profile == "h2_heavy":
        return 0.7 if month <= 6 else 1.3 + (month - 6) * 0.03
    elif profile == "seasonal_q4":
        if month <= 9:
            return 0.8 + random.gauss(0, 0.05)
        elif month == 10:
            return 1.2
        elif month == 11:
            return 1.5
        else:
            return 1.8
    elif profile == "front_loaded":
        return 1.3 - (month - 1) * 0.05
    return 1.0

# ─────────────────────────────────────────────
# Customers
# ─────────────────────────────────────────────

SEGMENTS = ["Enterprise", "Mid-Market", "SMB"]

def generate_customers():
    """Generate ~40 customers with different profiles."""
    customers = []
    cust_id = 1

    # 30 existing customers (in budget)
    for i in range(30):
        segment = random.choices(SEGMENTS, weights=[0.25, 0.45, 0.30])[0]
        size_mult = {"Enterprise": 3.0, "Mid-Market": 1.0, "SMB": 0.3}[segment]

        # Each customer buys 1-4 products
        n_products = random.choices([1, 2, 3, 4], weights=[0.2, 0.35, 0.30, 0.15])[0]
        product_indices = random.sample(range(6), n_products)

        # Monthly volume per product (units)
        product_volumes = {}
        for pi in product_indices:
            base_vol = max(1, int(random.uniform(3, 30) * size_mult))
            product_volumes[pi] = base_vol

        customers.append({
            "customer_id": f"C-{cust_id:03d}",
            "customer_name": f"Customer {cust_id}",
            "segment": segment,
            "product_volumes": product_volumes,
            "in_budget": True,
            "in_actuals": True,
            "budget_gap_type": None,
            "notes": "budgeted and active",
        })
        cust_id += 1

    # 3 customers budgeted but deals fell through (in budget, NOT in actuals)
    for i in range(3):
        segment = random.choice(["Enterprise", "Mid-Market"])
        size_mult = {"Enterprise": 3.0, "Mid-Market": 1.0}[segment]
        n_products = random.randint(1, 3)
        product_indices = random.sample(range(6), n_products)
        product_volumes = {pi: max(1, int(random.uniform(5, 25) * size_mult)) for pi in product_indices}

        customers.append({
            "customer_id": f"C-{cust_id:03d}",
            "customer_name": f"Customer {cust_id}",
            "segment": segment,
            "product_volumes": product_volumes,
            "in_budget": True,
            "in_actuals": False,
            "budget_gap_type": "budgeted_no_actuals",
            "notes": "deal fell through — budgeted revenue never materialized",
        })
        cust_id += 1

    # 5 customers NOT in budget but appear in actuals (new wins)
    for i in range(5):
        segment = random.choices(SEGMENTS, weights=[0.15, 0.40, 0.45])[0]
        size_mult = {"Enterprise": 3.0, "Mid-Market": 1.0, "SMB": 0.3}[segment]
        n_products = random.randint(1, 3)
        product_indices = random.sample(range(6), n_products)
        product_volumes = {pi: max(1, int(random.uniform(3, 20) * size_mult)) for pi in product_indices}

        # Start month — they were won mid-year
        start_month = random.randint(3, 9)

        customers.append({
            "customer_id": f"C-{cust_id:03d}",
            "customer_name": f"Customer {cust_id}",
            "segment": segment,
            "product_volumes": product_volumes,
            "in_budget": False,
            "in_actuals": True,
            "actuals_start_month": start_month,
            "budget_gap_type": "unbudgeted_new_win",
            "notes": f"new win starting month {start_month} — no budget exists",
        })
        cust_id += 1

    # 4 of the existing 30 customers get partial budget gaps
    # (budget exists for some months, missing for others)
    partial_gap_indices = random.sample(range(30), 4)
    for idx in partial_gap_indices:
        gap_type = random.choice(["added_mid_year", "dropped_mid_year", "sporadic_gaps"])
        customers[idx]["budget_gap_type"] = gap_type
        if gap_type == "added_mid_year":
            customers[idx]["budget_start_month"] = random.randint(4, 7)
            customers[idx]["notes"] = f"added to budget starting month {customers[idx]['budget_start_month']}"
        elif gap_type == "dropped_mid_year":
            customers[idx]["budget_end_month"] = random.randint(6, 9)
            customers[idx]["notes"] = f"dropped from budget after month {customers[idx]['budget_end_month']}"
        elif gap_type == "sporadic_gaps":
            # 3-4 random months missing from budget
            missing = sorted(random.sample(range(1, 13), random.randint(3, 4)))
            customers[idx]["budget_missing_months"] = missing
            customers[idx]["notes"] = f"budget missing for months {missing}"

    return customers

CUSTOMERS = generate_customers()

# ─────────────────────────────────────────────
# Generate budget data
# ─────────────────────────────────────────────

def generate_budget():
    """Budget was set at the start of the year.
    Uses planned volumes and standard pricing."""
    rows = []

    for cust in CUSTOMERS:
        if not cust["in_budget"]:
            continue

        for month in range(1, 13):
            # Check partial gaps
            gap = cust.get("budget_gap_type")
            if gap == "added_mid_year" and month < cust.get("budget_start_month", 1):
                continue
            if gap == "dropped_mid_year" and month > cust.get("budget_end_month", 12):
                continue
            if gap == "sporadic_gaps" and month in cust.get("budget_missing_months", []):
                continue

            for pi, base_vol in cust["product_volumes"].items():
                prod_name, avg_price, cogs_pct, season_profile = PRODUCTS[pi]

                # Budget uses planned seasonality (slightly idealized)
                season = seasonality_multiplier(season_profile, month)
                planned_units = max(1, int(base_vol * season))

                # Budget pricing: standard list, no negotiation variance
                unit_price = avg_price
                revenue = planned_units * unit_price
                cogs = round(revenue * cogs_pct, 2)

                rows.append({
                    "customer_id": cust["customer_id"],
                    "customer_name": cust["customer_name"],
                    "segment": cust["segment"],
                    "product": prod_name,
                    "month": month,
                    "budgeted_units": planned_units,
                    "budgeted_unit_price": unit_price,
                    "budgeted_revenue": round(revenue, 2),
                    "budgeted_cogs": cogs,
                    "budgeted_gross_profit": round(revenue - cogs, 2),
                })

    return rows

# ─────────────────────────────────────────────
# Generate actual data
# ─────────────────────────────────────────────

def generate_actuals():
    """Actuals diverge from budget in realistic ways:
    - Volume variance (demand was different than planned)
    - Price variance (negotiated discounts, price adjustments)
    - COGS variance (input cost changes, supplier issues)
    - Some customers start/stop mid-year
    """
    rows = []

    # Track some macro effects
    # Input cost inflation hits in H2 — COGS runs ~5% above plan
    # One product (SKU-D) has a supply issue in Q3 — COGS spikes 15%
    # Enterprise customers negotiate ~3-8% price concessions vs. list

    for cust in CUSTOMERS:
        if not cust["in_actuals"]:
            continue

        start_month = cust.get("actuals_start_month", 1)

        for month in range(start_month, 13):
            for pi, base_vol in cust["product_volumes"].items():
                prod_name, avg_price, base_cogs_pct, season_profile = PRODUCTS[pi]

                # Actual volume: budget volume with realistic variance
                season = seasonality_multiplier(season_profile, month)
                planned_units = max(1, int(base_vol * season))

                # Volume variance: actual demand differs by ±15-25%
                volume_variance = random.gauss(1.0, 0.12)
                actual_units = max(0, int(planned_units * volume_variance))

                if actual_units == 0:
                    continue  # no sales this month

                # Price variance: enterprise customers negotiate discounts
                price_adj = 1.0
                if cust["segment"] == "Enterprise":
                    price_adj = 1.0 - random.uniform(0.03, 0.08)
                elif cust["segment"] == "Mid-Market":
                    price_adj = 1.0 - random.uniform(0.00, 0.04)
                # Occasional small price increases for high-demand periods
                if season_profile == "seasonal_q4" and month >= 11:
                    price_adj *= 1.03  # slight premium in peak

                actual_unit_price = round(avg_price * price_adj, 2)
                actual_revenue = round(actual_units * actual_unit_price, 2)

                # COGS variance
                cogs_adj = 1.0
                # H2 input cost inflation
                if month >= 7:
                    cogs_adj *= 1.05
                # SKU-D supply issue in Q3
                if prod_name == "SKU-D" and 7 <= month <= 9:
                    cogs_adj *= 1.15
                # Random supplier variance
                cogs_adj *= random.uniform(0.97, 1.03)

                actual_cogs_pct = base_cogs_pct * cogs_adj
                actual_cogs = round(actual_revenue * actual_cogs_pct, 2)

                rows.append({
                    "customer_id": cust["customer_id"],
                    "customer_name": cust["customer_name"],
                    "segment": cust["segment"],
                    "product": prod_name,
                    "month": month,
                    "actual_units": actual_units,
                    "actual_unit_price": actual_unit_price,
                    "actual_revenue": round(actual_revenue, 2),
                    "actual_cogs": actual_cogs,
                    "actual_gross_profit": round(actual_revenue - actual_cogs, 2),
                })

    return rows

# ─────────────────────────────────────────────
# Generate customer master
# ─────────────────────────────────────────────

def generate_customer_master():
    rows = []
    for cust in CUSTOMERS:
        rows.append({
            "customer_id": cust["customer_id"],
            "customer_name": cust["customer_name"],
            "segment": cust["segment"],
            "products": ", ".join(PRODUCTS[pi][0] for pi in sorted(cust["product_volumes"].keys())),
            "in_budget": cust["in_budget"],
            "in_actuals": cust["in_actuals"],
            "budget_gap_type": cust.get("budget_gap_type") or "none",
            "notes": cust["notes"],
        })
    return rows

# ─────────────────────────────────────────────
# Run
# ─────────────────────────────────────────────

print("Generating budget data...")
budget_rows = generate_budget()

print("Generating actual data...")
actual_rows = generate_actuals()

print("Generating customer master...")
customer_rows = generate_customer_master()

# Write budget.csv
with open(os.path.join(OUT_DIR, "budget.csv"), "w", newline="") as f:
    fields = ["customer_id", "customer_name", "segment", "product", "month",
              "budgeted_units", "budgeted_unit_price", "budgeted_revenue",
              "budgeted_cogs", "budgeted_gross_profit"]
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    w.writerows(budget_rows)
print(f"budget.csv: {len(budget_rows):,} rows")

# Write actuals.csv
with open(os.path.join(OUT_DIR, "actuals.csv"), "w", newline="") as f:
    fields = ["customer_id", "customer_name", "segment", "product", "month",
              "actual_units", "actual_unit_price", "actual_revenue",
              "actual_cogs", "actual_gross_profit"]
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    w.writerows(actual_rows)
print(f"actuals.csv: {len(actual_rows):,} rows")

# Write customers.csv
with open(os.path.join(OUT_DIR, "customers.csv"), "w", newline="") as f:
    fields = ["customer_id", "customer_name", "segment", "products",
              "in_budget", "in_actuals", "budget_gap_type", "notes"]
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    w.writerows(customer_rows)
print(f"customers.csv: {len(customer_rows)} rows")

# ── Summary ──
print("\n── Summary ──")
total_budget_rev = sum(r["budgeted_revenue"] for r in budget_rows)
total_actual_rev = sum(r["actual_revenue"] for r in actual_rows)
total_budget_cogs = sum(r["budgeted_cogs"] for r in budget_rows)
total_actual_cogs = sum(r["actual_cogs"] for r in actual_rows)
total_budget_gp = total_budget_rev - total_budget_cogs
total_actual_gp = total_actual_rev - total_actual_cogs

print(f"Budget Revenue:  ${total_budget_rev:,.0f}")
print(f"Actual Revenue:  ${total_actual_rev:,.0f}")
print(f"Revenue Variance: ${total_actual_rev - total_budget_rev:,.0f} ({(total_actual_rev - total_budget_rev)/total_budget_rev*100:+.1f}%)")
print(f"Budget COGS:     ${total_budget_cogs:,.0f}")
print(f"Actual COGS:     ${total_actual_cogs:,.0f}")
print(f"COGS Variance:   ${total_actual_cogs - total_budget_cogs:,.0f} ({(total_actual_cogs - total_budget_cogs)/total_budget_cogs*100:+.1f}%)")
print(f"Budget GP:       ${total_budget_gp:,.0f} ({total_budget_gp/total_budget_rev*100:.1f}%)")
print(f"Actual GP:       ${total_actual_gp:,.0f} ({total_actual_gp/total_actual_rev*100:.1f}%)")

# Budget gap breakdown
budgeted_only = [c for c in CUSTOMERS if c["in_budget"] and not c["in_actuals"]]
actual_only = [c for c in CUSTOMERS if not c["in_budget"] and c["in_actuals"]]
partial = [c for c in CUSTOMERS if c.get("budget_gap_type") in ("added_mid_year", "dropped_mid_year", "sporadic_gaps")]

print(f"\nBudget Gap Analysis:")
print(f"  Budgeted customers with no actuals (fell through): {len(budgeted_only)}")
for c in budgeted_only:
    rev = sum(r["budgeted_revenue"] for r in budget_rows if r["customer_id"] == c["customer_id"])
    print(f"    {c['customer_id']} ({c['segment']}): ${rev:,.0f} budgeted, never materialized")

print(f"  Unbudgeted customers (new wins): {len(actual_only)}")
for c in actual_only:
    rev = sum(r["actual_revenue"] for r in actual_rows if r["customer_id"] == c["customer_id"])
    print(f"    {c['customer_id']} ({c['segment']}): ${rev:,.0f} actual, not in budget")

print(f"  Partial budget gaps: {len(partial)}")
for c in partial:
    print(f"    {c['customer_id']}: {c['notes']}")

# Per-product summary
print("\n── By Product ──")
for pi, (prod_name, _, _, _) in enumerate(PRODUCTS):
    b_rev = sum(r["budgeted_revenue"] for r in budget_rows if r["product"] == prod_name)
    a_rev = sum(r["actual_revenue"] for r in actual_rows if r["product"] == prod_name)
    if b_rev > 0:
        print(f"  {prod_name}: Budget=${b_rev:,.0f}, Actual=${a_rev:,.0f} ({(a_rev-b_rev)/b_rev*100:+.1f}%)")
    else:
        print(f"  {prod_name}: Budget=$0, Actual=${a_rev:,.0f}")

print("\nDone!")
