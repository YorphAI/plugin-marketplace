---
name: yorph-semantic-join
description: Use this skill when a user wants to match, link, deduplicate, or cross-reference records across datasets, OR when they want to enrich, normalize, or categorize rows based on text fields — for example: "find all customers who appear in both lists", "match these product listings to our catalog", "flag duplicates", "what's the average price of chocolate" (where rows say "dark chocolate" or "milk choc"), "add a category column", "fix spelling in this column", "group these by product type". Trigger whenever structured meaning needs to be extracted from messy text fields before doing analysis.
---

# Semantic Feature Extraction, Enrichment, and Joining

The core idea: messy text fields often contain structured information that's useful for analysis — categories, canonical names, dates, IDs, hierarchies. Extracting that structure cheaply, as new columns, unlocks grouping, aggregation, matching, and joining that would otherwise require an LLM on every operation.

## Step 1: Inspect the data and propose enrichments

Get a stratified sample of the dataset(s) and identify what structured information is latent in the text fields. Use an LLM call on the sample (not the full dataset) to propose a set of extraction columns that would be useful given the user's goal.

Examples of what to extract:
- **Spelling correction**: "drk chocolate" → "dark chocolate"
- **Canonical form**: "milk choc", "Milk Chocolate", "mlk choc" → "milk chocolate"
- **Specific category**: "dark chocolate" → "chocolate"
- **General category**: "dark chocolate" → "food" / "confectionery"
- **Parsed fields**: extract a year from a date string, a domain from an email, a numeric value from "approx. $12"
- **Keyword sets**: meaningful tokens from a free-text description

The LLM should look at a sample and decide which extractions make sense for the data and the user's goal — don't hardcode a fixed set.

## Step 2: Extract features at linear cost

Once the extraction schema is decided, extract features for every record in a single pass — one operation per row, not per pair. Prefer cheap methods:

- **Regex / parsing**: dates, IDs, prices, zip codes
- **Normalization**: lowercase, strip punctuation, remove stopwords
- **Substring / slicing**: first word of a name, year from a date
- **LLM-based concept mapping**: for fields that genuinely need semantic understanding (e.g. inferring category or related concepts from a product description) — use your intelligence to come up with several mappings to apply, e.g.: mapping = {"chocolate": "candy", ...} ; df[lvl1].map(mapping)

Add extracted values as new columns. These columns are the foundation for everything downstream.

## Step 3: Use extracted columns for the user's actual goal

With clean, structured columns in hand, the user's goal usually becomes straightforward:

- **Aggregation/grouping**: group by the new category column, average the price column
- **Matching/joining across datasets**: compare extracted features between record pairs, use AND logic across features to filter candidates, then confirm with LLM only where needed
- **Deduplication**: exact or fuzzy match on canonical form column
- **Filtering**: "show me all rows where category = chocolate"

For matching specifically: be conservative with filter thresholds — better to pass a non-match to the LLM than to silently drop a true match.
