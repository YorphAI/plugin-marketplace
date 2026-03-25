"""
B2B Quarterly Attribution Eval — Data Generator

Simulates a B2B SaaS company with:
- 8 products, 5 channels, ~25 sales reps, ~600 customers
- 26 weeks (Q3 + Q4 2024, weeks 1-26 = Jul 1 to Dec 29)
- Contract-based pricing with annual renewals
- Price elasticity (product-level + per-customer deviation)
- Churn with reason categories
- Channel-specific tech costs with mid-Q4 cloud cost spike
- New customer acquisition + seat expansion
- Sales rep productivity (ramp time for new hires)

Run: python3 generate_data.py
"""

import csv
import random
import datetime
import os
from collections import Counter

random.seed(2024)

OUT_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(OUT_DIR, exist_ok=True)

# ─────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────

WEEK_START = datetime.date(2024, 7, 1)  # Week 1 = Q3 start
NUM_WEEKS = 26  # Q3 (weeks 1-13) + Q4 (weeks 14-26)

def week_date(w):
    """Return the Monday of week w (1-indexed)."""
    return WEEK_START + datetime.timedelta(weeks=w - 1)

# ─────────────────────────────────────────────
# Products
# ─────────────────────────────────────────────

PRODUCTS = [
    # name, base_list_price (monthly per seat), base_elasticity, volume_weight
    ("Product 1", 120, -0.5, 1.0),   # Core platform — inelastic, high volume
    ("Product 2", 85, -0.8, 0.8),    # Collaboration tool — moderate
    ("Product 3", 200, -0.4, 0.5),   # Analytics suite — inelastic, +5% value capture
    ("Product 4", 45, -1.2, 1.2),    # Entry-level tool — elastic, high volume
    ("Product 5", 150, -0.6, 0.6),   # Security module — inelastic
    ("Product 6", 95, -1.4, 0.7),    # Data connector — elastic, -10.5% competitive response
    ("Product 7", 180, -0.3, 0.3),   # Enterprise API — very inelastic, low volume
    ("Product 8", 60, -1.0, 0.9),    # Reporting tool — moderate elasticity
]

# List price changes. Customers only see them at contract renewal.
PRICE_CHANGES = [
    # (product_index, effective_week, new_list_price, old_list_price, reason)
    (0, 14, 128, 120, "cost pass-through"),        # Product 1: +6.7% at Q4 start
    (2, 16, 210, 200, "value capture"),             # Product 3: +5% after feature release
    (5, 15, 85, 95, "competitive response"),        # Product 6: -10.5% to defend share
]

# ─────────────────────────────────────────────
# Channels
# ─────────────────────────────────────────────

CHANNELS = [
    # name, discount_mean, discount_std, avg_deal_seats, new_logos_per_week, segment_weights
    ("Direct Sales", 0.15, 0.03, 40, 1.5, {"Enterprise": 0.6, "Mid-Market": 0.35, "SMB": 0.05}),
    ("Partner", 0.15, 0.02, 25, 2.0, {"Enterprise": 0.2, "Mid-Market": 0.5, "SMB": 0.3}),
    ("Inside Sales", 0.08, 0.02, 15, 3.0, {"Enterprise": 0.05, "Mid-Market": 0.4, "SMB": 0.55}),
    ("Self-Serve", 0.0, 0.0, 5, 5.0, {"Enterprise": 0.0, "Mid-Market": 0.1, "SMB": 0.9}),
    ("Strategic", 0.20, 0.03, 150, 0.4, {"Enterprise": 0.95, "Mid-Market": 0.05, "SMB": 0.0}),
]

SEGMENTS = ["Enterprise", "Mid-Market", "SMB"]

# ─────────────────────────────────────────────
# Sales Reps
# ─────────────────────────────────────────────

def generate_reps():
    reps = []
    rep_id = 1
    channel_rep_counts = {
        "Direct Sales": 6, "Partner": 4, "Inside Sales": 7,
        "Self-Serve": 3, "Strategic": 4,
    }
    for ch_name, count in channel_rep_counts.items():
        for i in range(count):
            if random.random() < 0.25:
                hire_week = random.randint(1, 20)  # hired during our window
                tenure = "new"
            else:
                hire_week = -random.randint(26, 150)  # hired before window
                tenure = "tenured"

            annual_quota = {
                "Direct Sales": 800000, "Partner": 600000, "Inside Sales": 500000,
                "Self-Serve": 400000, "Strategic": 1500000,
            }[ch_name]

            reps.append({
                "rep_id": f"REP-{rep_id:03d}",
                "rep_name": f"Rep {rep_id}",
                "channel": ch_name,
                "hire_week": hire_week,
                "annual_quota": annual_quota,
                "tenure": tenure,
                "base_productivity": random.uniform(0.8, 1.2) if tenure == "tenured" else random.uniform(0.4, 0.7),
            })
            rep_id += 1
    return reps

REPS = generate_reps()

def rep_productivity(rep, week):
    """New reps ramp over 12 weeks from hire date."""
    if rep["tenure"] == "tenured":
        return rep["base_productivity"]
    weeks_since_hire = week - rep["hire_week"]
    if weeks_since_hire < 0:
        return 0.0
    ramp = min(1.0, weeks_since_hire / 12.0)
    return rep["base_productivity"] + (1.0 - rep["base_productivity"]) * ramp

# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def get_current_list_price(product_idx, week):
    price = PRODUCTS[product_idx][1]
    for pi, w, new_p, old_p, reason in PRICE_CHANGES:
        if pi == product_idx and week >= w:
            price = new_p
    return price

def renewal_week_for_month(renewal_month):
    """Convert renewal month to week in our 26-week window. None if outside."""
    month_to_first_week = {7: 1, 8: 5, 9: 9, 10: 14, 11: 18, 12: 23}
    if renewal_month in month_to_first_week:
        return month_to_first_week[renewal_month] + random.randint(0, 3)
    return None

# ─────────────────────────────────────────────
# Churn
# ─────────────────────────────────────────────

CHURN_REASONS = ["competitive loss", "budget cuts", "product fit", "built in-house", "acquired/shut down"]
CHURN_REASON_WEIGHTS_Q3 = [0.30, 0.15, 0.25, 0.15, 0.15]
CHURN_REASON_WEIGHTS_Q4 = [0.25, 0.35, 0.15, 0.10, 0.15]  # budget cuts spike Q4
BASE_WEEKLY_CHURN_PROB = 0.0015  # ~7.5% annualized

# ─────────────────────────────────────────────
# Initial customer base
# ─────────────────────────────────────────────

def generate_initial_customers():
    customers = []
    cust_id = 1
    base_counts = {"Direct Sales": 80, "Partner": 100, "Inside Sales": 120, "Self-Serve": 180, "Strategic": 20}

    for ch_idx, (ch_name, disc_mean, disc_std, avg_seats, _, seg_weights) in enumerate(CHANNELS):
        n_customers = base_counts[ch_name]
        channel_reps = [r for r in REPS if r["channel"] == ch_name and r["hire_week"] < 1]

        for _ in range(n_customers):
            product_idx = random.choices(range(8), weights=[p[3] for p in PRODUCTS])[0]
            segment = random.choices(SEGMENTS, weights=[seg_weights[s] for s in SEGMENTS])[0]

            seat_mult = {"Enterprise": 3.0, "Mid-Market": 1.0, "SMB": 0.3}[segment]
            seats = max(1, int(avg_seats * seat_mult * random.uniform(0.5, 1.5)))

            renewal_month = random.randint(1, 12)
            discount = max(0, min(0.35, random.gauss(disc_mean, disc_std)))
            cust_elasticity = PRODUCTS[product_idx][2] + random.gauss(0, 0.15)

            rep = random.choice(channel_reps) if channel_reps else None

            customers.append({
                "customer_id": f"CUST-{cust_id:04d}",
                "product": PRODUCTS[product_idx][0],
                "product_idx": product_idx,
                "channel": ch_name,
                "segment": segment,
                "seats": seats,
                "seats_initial": seats,
                "renewal_month": renewal_month,
                "discount": round(discount, 4),
                "elasticity": round(cust_elasticity, 3),
                "acquisition_week": 1 - random.randint(13, 150),
                "rep_id": rep["rep_id"] if rep else "REP-000",
                "churned": False,
                "churn_week": None,
                "churn_reason": None,
                "locked_list_price": PRODUCTS[product_idx][1],
                "seat_growth_rate": random.gauss(0.003, 0.008),
            })
            cust_id += 1

    return customers, cust_id

# ─────────────────────────────────────────────
# Main simulation
# ─────────────────────────────────────────────

def simulate():
    customers, next_cust_id = generate_initial_customers()
    weekly_revenue_rows = []
    churn_events = []
    cust_noise = {c["customer_id"]: 0.0 for c in customers}

    for week in range(1, NUM_WEEKS + 1):
        is_q4 = week >= 14
        week_date_str = week_date(week).isoformat()
        churn_reason_weights = CHURN_REASON_WEIGHTS_Q4 if is_q4 else CHURN_REASON_WEIGHTS_Q3

        # ── Existing customers ──
        for cust in customers:
            if cust["churned"]:
                continue

            renewal_wk = renewal_week_for_month(cust["renewal_month"])
            is_renewal = (renewal_wk is not None and renewal_wk == week)

            if is_renewal:
                new_list = get_current_list_price(cust["product_idx"], week)
                old_list = cust["locked_list_price"]
                price_change_pct = (new_list - old_list) / old_list if old_list > 0 else 0

                if price_change_pct > 0:
                    # Elasticity-driven churn at renewal
                    elast_churn_prob = abs(cust["elasticity"]) * price_change_pct * 0.5
                    if random.random() < elast_churn_prob:
                        cust["churned"] = True
                        cust["churn_week"] = week
                        cust["churn_reason"] = random.choices(
                            ["competitive loss", "budget cuts", "product fit"],
                            weights=[0.5, 0.3, 0.2]
                        )[0]
                        churn_events.append({
                            "customer_id": cust["customer_id"],
                            "churn_week": week,
                            "churn_date": week_date_str,
                            "reason": cust["churn_reason"],
                            "product": cust["product"],
                            "channel": cust["channel"],
                            "seats_at_churn": cust["seats"],
                            "final_weekly_revenue": round(cust["seats"] * old_list * (1 - cust["discount"]) / 4.33, 2),
                        })
                        continue

                    # Surviving customers may reduce seats
                    seat_reduction_pct = abs(cust["elasticity"]) * price_change_pct * 0.3
                    seats_lost = int(cust["seats"] * seat_reduction_pct)
                    cust["seats"] = max(1, cust["seats"] - seats_lost)

                elif price_change_pct < 0:
                    # Price decrease → slight expansion
                    seat_gain_pct = abs(cust["elasticity"]) * abs(price_change_pct) * 0.2
                    seats_gained = max(0, int(cust["seats"] * seat_gain_pct))
                    cust["seats"] += seats_gained

                cust["locked_list_price"] = new_list

            # Base churn (non-renewal)
            if not is_renewal:
                churn_prob = BASE_WEEKLY_CHURN_PROB
                if is_q4:
                    churn_prob *= 1.3
                if cust["segment"] == "SMB":
                    churn_prob *= 1.5
                elif cust["segment"] == "Enterprise":
                    churn_prob *= 0.6

                if random.random() < churn_prob:
                    cust["churned"] = True
                    cust["churn_week"] = week
                    cust["churn_reason"] = random.choices(CHURN_REASONS, weights=churn_reason_weights)[0]
                    churn_events.append({
                        "customer_id": cust["customer_id"],
                        "churn_week": week,
                        "churn_date": week_date_str,
                        "reason": cust["churn_reason"],
                        "product": cust["product"],
                        "channel": cust["channel"],
                        "seats_at_churn": cust["seats"],
                        "final_weekly_revenue": round(cust["seats"] * cust["locked_list_price"] * (1 - cust["discount"]) / 4.33, 2),
                    })
                    continue

            # Organic seat growth/contraction
            if random.random() < 0.08:
                seat_delta = int(cust["seats"] * cust["seat_growth_rate"] * random.uniform(0.5, 3.0))
                if seat_delta != 0:
                    cust["seats"] = max(1, cust["seats"] + seat_delta)

            # Weekly revenue
            monthly_per_seat = cust["locked_list_price"] * (1 - cust["discount"])
            weekly_per_seat = monthly_per_seat / 4.33

            # Autocorrelated noise (AR(1) with mean reversion)
            prev_noise = cust_noise.get(cust["customer_id"], 0.0)
            new_noise = 0.7 * prev_noise + random.gauss(0, 0.03)
            new_noise = max(-0.15, min(0.15, new_noise))
            cust_noise[cust["customer_id"]] = new_noise

            revenue = round(cust["seats"] * weekly_per_seat * (1.0 + new_noise), 2)
            weekly_revenue_rows.append({
                "week": week,
                "week_date": week_date_str,
                "customer_id": cust["customer_id"],
                "product": cust["product"],
                "channel": cust["channel"],
                "segment": cust["segment"],
                "rep_id": cust["rep_id"],
                "seats": cust["seats"],
                "unit_price_monthly": round(monthly_per_seat, 2),
                "list_price_monthly": cust["locked_list_price"],
                "discount_pct": round(cust["discount"], 4),
                "revenue": max(0, revenue),
            })

        # ── New customer acquisition ──
        for ch_idx, (ch_name, disc_mean, disc_std, avg_seats, base_new_rate, seg_weights) in enumerate(CHANNELS):
            channel_reps = [r for r in REPS if r["channel"] == ch_name]
            active_reps = [r for r in channel_reps if r["hire_week"] <= week]
            if not active_reps:
                continue

            avg_prod = sum(rep_productivity(r, week) for r in active_reps) / len(active_reps)
            expected_new = base_new_rate * avg_prod

            # Strategic and Direct are lumpy
            if ch_name in ("Strategic", "Direct Sales"):
                n_new = 0 if random.random() < 0.6 else random.randint(1, int(expected_new * 2.5) + 1)
            else:
                n_new = int(random.expovariate(1.0 / max(0.1, expected_new)))
                n_new = min(n_new, int(expected_new * 3))

            for _ in range(n_new):
                product_idx = random.choices(range(8), weights=[p[3] for p in PRODUCTS])[0]

                # Product 6 price cut attracts extra new logos
                if week >= 15 and random.random() < 0.15:
                    product_idx = 5

                segment = random.choices(SEGMENTS, weights=[seg_weights[s] for s in SEGMENTS])[0]
                seat_mult = {"Enterprise": 3.0, "Mid-Market": 1.0, "SMB": 0.3}[segment]
                seats = max(1, int(avg_seats * seat_mult * random.uniform(0.4, 1.6)))

                discount = max(0, min(0.35, random.gauss(disc_mean, disc_std)))
                cust_elasticity = PRODUCTS[product_idx][2] + random.gauss(0, 0.15)
                rep = random.choice(active_reps)
                current_list_price = get_current_list_price(product_idx, week)

                new_cust = {
                    "customer_id": f"CUST-{next_cust_id:04d}",
                    "product": PRODUCTS[product_idx][0],
                    "product_idx": product_idx,
                    "channel": ch_name,
                    "segment": segment,
                    "seats": seats,
                    "seats_initial": seats,
                    "renewal_month": (WEEK_START + datetime.timedelta(weeks=week - 1)).month,
                    "discount": round(discount, 4),
                    "elasticity": round(cust_elasticity, 3),
                    "acquisition_week": week,
                    "rep_id": rep["rep_id"],
                    "churned": False,
                    "churn_week": None,
                    "churn_reason": None,
                    "locked_list_price": current_list_price,
                    "seat_growth_rate": random.gauss(0.003, 0.008),
                }
                customers.append(new_cust)
                cust_noise[new_cust["customer_id"]] = 0.0
                next_cust_id += 1

                # Revenue for first week
                monthly_per_seat = current_list_price * (1 - discount)
                revenue = round(seats * monthly_per_seat / 4.33, 2)
                weekly_revenue_rows.append({
                    "week": week,
                    "week_date": week_date_str,
                    "customer_id": new_cust["customer_id"],
                    "product": new_cust["product"],
                    "channel": ch_name,
                    "segment": segment,
                    "rep_id": rep["rep_id"],
                    "seats": seats,
                    "unit_price_monthly": round(monthly_per_seat, 2),
                    "list_price_monthly": current_list_price,
                    "discount_pct": round(discount, 4),
                    "revenue": revenue,
                })

    return customers, weekly_revenue_rows, churn_events

# ─────────────────────────────────────────────
# Channel Costs
# ─────────────────────────────────────────────

def generate_channel_costs():
    """Weekly tech/infra costs. Cloud cost spike from week 20 for tech-heavy channels."""
    rows = []
    base_weekly_costs = {
        "Direct Sales": {"hosting": 8000, "tooling": 12000, "support_platform": 5000},
        "Partner": {"hosting": 6000, "tooling": 8000, "partner_portal": 10000},
        "Inside Sales": {"hosting": 15000, "tooling": 18000, "support_platform": 8000},
        "Self-Serve": {"hosting": 35000, "tooling": 10000, "support_platform": 3000},
        "Strategic": {"hosting": 5000, "tooling": 6000, "dedicated_infra": 20000},
    }

    for week in range(1, NUM_WEEKS + 1):
        week_date_str = week_date(week).isoformat()
        for ch_name, costs in base_weekly_costs.items():
            for cost_cat, base_amt in costs.items():
                inflation = 1.0 + 0.003 * week  # ~15% annualized

                cloud_spike = 1.0
                if week >= 20 and cost_cat == "hosting":
                    spike_pct = {"Self-Serve": 0.22, "Inside Sales": 0.18,
                                 "Direct Sales": 0.08, "Partner": 0.06, "Strategic": 0.10}
                    cloud_spike = 1.0 + spike_pct.get(ch_name, 0.05)

                amount = base_amt * inflation * cloud_spike * random.uniform(0.95, 1.05)
                rows.append({
                    "week": week, "week_date": week_date_str,
                    "channel": ch_name, "cost_category": cost_cat,
                    "amount": round(amount, 2),
                })
    return rows

# ─────────────────────────────────────────────
# Run
# ─────────────────────────────────────────────

print("Simulating...")
customers, weekly_revenue_rows, churn_events = simulate()
channel_cost_rows = generate_channel_costs()

# Write weekly_revenue.csv
with open(os.path.join(OUT_DIR, "weekly_revenue.csv"), "w", newline="") as f:
    fields = ["week", "week_date", "customer_id", "product", "channel", "segment", "rep_id",
              "seats", "unit_price_monthly", "list_price_monthly", "discount_pct", "revenue"]
    csv.DictWriter(f, fieldnames=fields).writeheader()
    csv.DictWriter(f, fieldnames=fields).writerows(weekly_revenue_rows)
print(f"weekly_revenue.csv: {len(weekly_revenue_rows):,} rows")

# Write customers.csv
with open(os.path.join(OUT_DIR, "customers.csv"), "w", newline="") as f:
    fields = ["customer_id", "product", "channel", "segment", "seats_initial", "renewal_month",
              "discount_pct", "acquisition_week", "acquisition_date", "rep_id", "status"]
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    for c in customers:
        acq_date = week_date(max(1, c["acquisition_week"])).isoformat() if c["acquisition_week"] >= 1 else "pre-period"
        w.writerow({
            "customer_id": c["customer_id"],
            "product": c["product"],
            "channel": c["channel"],
            "segment": c["segment"],
            "seats_initial": c["seats_initial"],
            "renewal_month": c["renewal_month"],
            "discount_pct": c["discount"],
            "acquisition_week": c["acquisition_week"],
            "acquisition_date": acq_date,
            "rep_id": c["rep_id"],
            "status": "churned" if c["churned"] else "active",
        })
print(f"customers.csv: {len(customers):,} rows")

# Write churn_events.csv
with open(os.path.join(OUT_DIR, "churn_events.csv"), "w", newline="") as f:
    fields = ["customer_id", "churn_week", "churn_date", "reason", "product", "channel",
              "seats_at_churn", "final_weekly_revenue"]
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    w.writerows(churn_events)
print(f"churn_events.csv: {len(churn_events):,} rows")

# Write channel_costs.csv
with open(os.path.join(OUT_DIR, "channel_costs.csv"), "w", newline="") as f:
    fields = ["week", "week_date", "channel", "cost_category", "amount"]
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    w.writerows(channel_cost_rows)
print(f"channel_costs.csv: {len(channel_cost_rows):,} rows")

# Write sales_reps.csv
with open(os.path.join(OUT_DIR, "sales_reps.csv"), "w", newline="") as f:
    fields = ["rep_id", "rep_name", "channel", "hire_date", "annual_quota", "tenure"]
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    for r in REPS:
        hire_date = week_date(max(1, r["hire_week"])).isoformat() if r["hire_week"] >= 1 else "pre-period"
        w.writerow({
            "rep_id": r["rep_id"], "rep_name": r["rep_name"], "channel": r["channel"],
            "hire_date": hire_date, "annual_quota": r["annual_quota"], "tenure": r["tenure"],
        })
print(f"sales_reps.csv: {len(REPS)} rows")

# Write price_changes.csv
with open(os.path.join(OUT_DIR, "price_changes.csv"), "w", newline="") as f:
    fields = ["product", "effective_week", "effective_date", "old_list_price", "new_list_price",
              "change_pct", "reason"]
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    for pi, wk, new_p, old_p, reason in PRICE_CHANGES:
        w.writerow({
            "product": PRODUCTS[pi][0], "effective_week": wk,
            "effective_date": week_date(wk).isoformat(),
            "old_list_price": old_p, "new_list_price": new_p,
            "change_pct": round((new_p - old_p) / old_p * 100, 1),
            "reason": reason,
        })
print(f"price_changes.csv: {len(PRICE_CHANGES)} rows")

# ── Summary stats ──
print("\n── Summary ──")
q3_rev = sum(r["revenue"] for r in weekly_revenue_rows if r["week"] <= 13)
q4_rev = sum(r["revenue"] for r in weekly_revenue_rows if r["week"] > 13)
q3_custs = len(set(r["customer_id"] for r in weekly_revenue_rows if r["week"] <= 13))
q4_custs = len(set(r["customer_id"] for r in weekly_revenue_rows if r["week"] > 13))
q3_cost = sum(r["amount"] for r in channel_cost_rows if r["week"] <= 13)
q4_cost = sum(r["amount"] for r in channel_cost_rows if r["week"] > 13)
new_in_window = sum(1 for c in customers if c["acquisition_week"] >= 1)
churned_q3 = sum(1 for e in churn_events if e["churn_week"] <= 13)
churned_q4 = sum(1 for e in churn_events if e["churn_week"] > 13)

print(f"Q3 Revenue: ${q3_rev:,.0f}")
print(f"Q4 Revenue: ${q4_rev:,.0f}")
print(f"Q/Q Change: {(q4_rev - q3_rev) / q3_rev * 100:+.1f}%")
print(f"Q3 Active Customers: {q3_custs}")
print(f"Q4 Active Customers: {q4_custs}")
print(f"Q3 Channel Costs: ${q3_cost:,.0f}")
print(f"Q4 Channel Costs: ${q4_cost:,.0f}")
print(f"Cost Q/Q Change: {(q4_cost - q3_cost) / q3_cost * 100:+.1f}%")
print(f"New Customers (in-window): {new_in_window}")
print(f"Churned Q3: {churned_q3}, Q4: {churned_q4}")

q4_reasons = Counter(e["reason"] for e in churn_events if e["churn_week"] > 13)
print(f"Q4 Churn Reasons: {dict(q4_reasons)}")

# Channel mix
for ch in ["Direct Sales", "Partner", "Inside Sales", "Self-Serve", "Strategic"]:
    ch_q3 = sum(r["revenue"] for r in weekly_revenue_rows if r["week"] <= 13 and r["channel"] == ch)
    ch_q4 = sum(r["revenue"] for r in weekly_revenue_rows if r["week"] > 13 and r["channel"] == ch)
    print(f"  {ch}: Q3=${ch_q3:,.0f} → Q4=${ch_q4:,.0f} ({(ch_q4-ch_q3)/ch_q3*100:+.1f}%)" if ch_q3 > 0 else f"  {ch}: Q3=$0")

print("\nDone!")
