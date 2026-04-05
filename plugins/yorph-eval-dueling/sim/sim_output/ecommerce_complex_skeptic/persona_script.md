# Persona Script: Senior Data Engineer (skeptic)

> **Scenario:** ecommerce_complex  
> **Domain:** ecommerce  
> **Complexity:** complex

---

## Who this persona is

A senior data engineer who has been burned by incorrect semantic layers before. Trusts nothing that isn't validated with real SQL. Asks for proof — join cardinality queries, null rate checks, value distribution samples. Will argue about metric definitions and sometimes propose incorrect ones to see if the agent corrects them. Not hostile, just rigorous.

## Behavioural flags
- Uploads data dictionary: No
- Challenges join recommendations: Yes
- Tries to skip clarifying questions: No
- Preferred recommendation: Comprehensive

---

## Conversation Script

Paste each turn into Claude **in order**. Wait for the full response before sending the next.

### Turn 1 — Connect and immediately demand validation
**Phase:** `connect`

```
Connect to the simulation warehouse and profile everything. I want to see the actual row counts and null rates — not estimates.
```

> **Watch for:** Agent should connect and run profiler. It should report actual stats from get_context_summary. Watch for whether it shows confidence intervals or caveats about TABLESAMPLE.

### Turn 2 — Provide minimal context — force agent to infer
**Phase:** `clarify`

```
It's ecommerce data. Don't ask me what the grain is — figure it out from the data. Run whatever SQL you need.
```

> **Watch for:** Agent should call execute_validation_sql to check grain uniqueness on key tables before declaring a grain. Watch for whether it uses get_sample_slice or validation SQL, or whether it just declares a grain without proof.

### Turn 3 — Challenge the first join recommendation
**Phase:** `build`

```
You said f_orders joins to customers on customer_id. Can you prove that? I want to see: (1) the FK match rate — what % of customer_ids in orders exist in customers?, (2) the cardinality — is it truly many:1 or are there duplicate customer_ids in orders?, (3) the null rate on customer_id in orders. Show me the SQL you're running.
```

> **Watch for:** Agent (Join Validator) should generate and execute all 3 queries explicitly. The SQL should be shown in the response. If match rate < 100%, agent should flag this as an open question.

### Turn 4 — Propose an incorrect metric to test agent correction
**Phase:** `build`

```
For total revenue, I want to include ALL orders — even refunded ones. Refunds are already tracked separately so there's no double-counting.
```

> **Watch for:** Agent should respectfully push back: refunded revenue + a separate refund measure would double-count the refunded amount in gross revenue unless revenue column is already net of refunds. Agent should check the data to determine which is true, then explain its position clearly.

### Turn 5 — Demand proof on additivity claims
**Phase:** `review`

```
You listed avg_order_value as non_additive. What does that actually mean in practice? And why is order_count listed as fully_additive but customer_count isn't?
```

> **Watch for:** Agent should explain: non_additive means the metric can't be correctly summed across dimensions (you can't add two averages). COUNT(distinct customer_id) is semi_additive — it can be summed over time but not across dimensions without re-counting. COUNT(order_id) is fully additive — always safe to sum.

### Turn 6 — Save Comprehensive with open questions
**Phase:** `save`

```
Save Comprehensive (rec 2) in all formats. I want to review the readme — specifically the open questions section. List what you're still not certain about.
```

> **Watch for:** Agent should call save_output(format='all', recommendation_number=2). The readme's open questions section should contain any ambiguities discovered during validation.
