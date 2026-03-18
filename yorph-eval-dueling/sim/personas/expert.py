"""
Expert persona: Data Architect who knows the schema and has a data dictionary.

Behaviour:
- Provides domain + fact/dim context upfront
- Uploads a data dictionary
- Asks detailed questions about grain and join validation
- Wants Balanced (recommendation 3)
- Pushes back specifically on the Comprehensive set (too many metrics)
"""

from .base import Persona, ConversationTurn

EXPERT = Persona(
    name="expert",
    title="Data Architect",
    description=(
        "A senior data architect at the company. Knows the schema well — "
        "has been working with this data for 2+ years. Has a data dictionary "
        "documenting business names, metric formulas, and known quirks. "
        "Uses precise technical language. Will catch incorrect grain assumptions "
        "and push back on metrics that don't match documented formulas."
    ),
    uploads_docs=True,
    challenges_joins=True,
    skips_questions=False,
    preferred_recommendation=3,
    data_dictionary=(
        "table_name,column_name,business_name,description,pii,valid_values,metric_formula\n"
        "orders,order_id,Order ID,Unique order identifier,false,,\n"
        "orders,revenue,Gross Revenue,\"Pre-tax order value in USD. Excludes shipping and taxes. "
        "NULL for cancelled/N/A orders.\",false,,SUM(revenue) WHERE status NOT IN ('N/A','refunded')\n"
        "orders,status,Order Status,\"Fulfilment status. 'N/A' = order was attempted but not confirmed.\","
        "false,\"completed,pending,refunded,N/A\",\n"
        "orders,customer_id,Customer ID,FK to customers.customer_id,false,,\n"
        "customers,customer_id,Customer ID,Unique customer identifier,false,,\n"
        "customers,email,Email Address,Customer email,true,,\n"
        "order_items,order_id,Order ID,FK to orders.order_id,false,,\n"
        "order_items,quantity,Quantity,Units ordered,false,,SUM(quantity)\n"
        "order_items,unit_price,Unit Price,\"Price at time of order. May differ from products.price "
        "if promo applied.\",false,,\n"
    ),
    turns=[
        ConversationTurn(
            phase="connect",
            label="Connect to simulation warehouse",
            message=(
                "Let's get started. Please connect to the simulation warehouse "
                "and profile all schemas."
            ),
            notes=(
                "Agent should call connect_warehouse(warehouse_type='simulation') "
                "then run_profiler() automatically."
            ),
        ),
        ConversationTurn(
            phase="clarify",
            label="Answer clarifying questions with full context",
            message=(
                "This is a {domain} data warehouse. "
                "The primary business process is {description}.\n\n"
                "Fact tables: {primary_table}. "
                "Dimension tables: customers, products.\n\n"
                "Key business rules:\n"
                "- Revenue excludes orders with status = 'N/A' or 'refunded'\n"
                "- order_items.unit_price is the price at order time — may differ "
                "from products.price due to promotions\n"
                "- 'N/A' in the status column is an encoded null meaning "
                "the order was attempted but never confirmed\n\n"
                "I'll upload our data dictionary now."
            ),
            notes=(
                "Agent should pick up business_rules and the encoded null pattern. "
                "Watch for whether it properly notes that status='N/A' is encoded null, "
                "not a valid status value."
            ),
        ),
        ConversationTurn(
            phase="build",
            label="Challenge a specific join assumption",
            message=(
                "Before you finalise the join recommendations: "
                "I want to make sure you've validated the join between "
                "order_items and products on product_id. "
                "Can you run a query to check the FK match rate? "
                "We've had issues with discontinued products not being in the catalog."
            ),
            notes=(
                "Agent (Join Validator) should call execute_validation_sql with a "
                "query checking distinct product_ids in order_items vs products. "
                "If match rate < 100%, it should flag discontinued products as an open question."
            ),
        ),
        ConversationTurn(
            phase="review",
            label="Select recommendation and flag an issue",
            message=(
                "I want Recommendation 3 (Balanced). "
                "But I have a concern: the Comprehensive set includes 'avg_order_value' "
                "as a SUM-based derived metric. AVG is non-additive — it can't be "
                "correctly rolled up across dimensions. Can you confirm whether the "
                "Balanced recommendation marks avg_order_value as non_additive?"
            ),
            notes=(
                "Agent should confirm avg_order_value has additivity='non_additive'. "
                "This tests whether the Measure Builder correctly flagged additivity."
            ),
        ),
        ConversationTurn(
            phase="save",
            label="Request dbt format with specific filename",
            message=(
                "Please save the Balanced recommendation in dbt format. "
                "Use filename 'production_semantic_layer'. "
                "Also confirm the companion readme includes the business rules "
                "we discussed about status='N/A' and revenue exclusion."
            ),
            notes=(
                "Agent should call save_output with format='dbt', "
                "recommendation_number=3, filename='production_semantic_layer'. "
                "Readme should include the N/A business rule."
            ),
        ),
    ],
)
