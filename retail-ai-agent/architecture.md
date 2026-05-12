# Retail AI Assistant — Architecture Document

## Overview

This system is a single agentic AI assistant that handles both personal shopping
recommendations and customer support (returns/exchanges) for a fashion boutique.
It is powered by **Google Gemini** (`gemini-2.0-flash`) using the `google-genai`
Python SDK with structured function calling.

---

## System Architecture

```
User Input (CLI)
      │
      ▼
┌─────────────────────────────────────────────┐
│               Agent Loop (agent.py)          │
│                                             │
│  1. Send message + tool schemas to Claude   │
│  2. Claude decides: call a tool or respond? │
│  3a. Tool call → dispatch to Python fn      │
│  3b. Feed result back to Claude             │
│  4. Repeat until stop_reason = "end_turn"   │
│  5. Return Claude's final text response     │
└─────────────────────────────────────────────┘
      │                    ▲
      ▼                    │
┌──────────────┐    structured JSON result
│  Tool Layer  │
│              │
│ search_products(filters)   → products.csv
│ get_product(product_id)    → products.csv
│ get_order(order_id)        → orders.csv + products.csv
│ evaluate_return(order_id)  → orders.csv + products.csv + policy rules
└──────────────┘
```

### Component Responsibilities

| Component         | Responsibility                                               |
|-------------------|--------------------------------------------------------------|
| `main.py`         | CLI interface, demo runner, user I/O                        |
| `agent/agent.py`  | Agentic loop, tool dispatching, conversation management     |
| `agent/tool_registry.py` | JSON schemas Claude uses to decide when/how to call tools |
| `tools/search_products.py` | Multi-filter product search, ranked by bestseller_score |
| `tools/get_product.py`     | Single product lookup by ID                             |
| `tools/get_order.py`       | Order lookup with product enrichment                    |
| `tools/evaluate_return.py` | Policy engine: deterministic return eligibility ruling  |
| `data/`           | Source of truth: CSVs and policy.txt                        |

---

## Why This Structure?

### 1. Separation of Reasoning from Data Retrieval

Claude (the LLM) is responsible for:
- Understanding customer intent
- Selecting the right tool and parameters
- Translating structured tool results into human-friendly explanations
- Applying judgment about tone and emphasis

Python tools are responsible for:
- Reading and filtering data from disk
- Applying policy rules deterministically
- Returning structured errors when data doesn't exist

This separation means that even if Claude's reasoning changes across model versions,
the policy decisions and data results remain consistent and auditable.

### 2. Tool Descriptions Drive Tool Selection

Each tool's `description` field in `tool_registry.py` is written to be
non-overlapping and intent-specific:

- `search_products` → triggered by browsing intent ("looking for", "recommend")
- `get_product` → triggered when a specific product ID is already known
- `get_order` → triggered for raw order lookup
- `evaluate_return` → triggered specifically for return/exchange decisions

Claude selects tools based on these descriptions. The system prompt reinforces
this with explicit instructions: "always use evaluate_return for returns — never
reason about policy from memory."

### 3. Agentic Loop Design (Gemini Multi-Turn Pattern)

The loop follows Gemini's function-calling protocol:

```
User message
  → Gemini returns FunctionCall parts
  → Python executes each function
  → FunctionResponse parts sent back as next user turn
  → Gemini reasons again → more calls OR final text
```

Gemini's response parts are inspected each iteration:
- `function_call` parts → dispatch to Python, feed back as `FunctionResponse`
- `text` parts (no function calls) → final answer, exit loop

A `MAX_ITERATIONS = 8` guard prevents runaway loops.

---

## How Hallucination Is Minimized

Hallucination in retail AI has real consequences: wrong prices, incorrect stock
levels, or false return approvals all damage customer trust. Three layers prevent it:

### Layer 1: No Product Data in Context

Products and orders are **never embedded in the system prompt**. Claude has no
memorized inventory. To mention a product, it *must* call a tool. If it doesn't
call a tool, it has no data to speak from.

### Layer 2: Explicit Errors for Missing IDs

Every tool returns a structured `{"error": "..."}` when data isn't found:

```python
# get_order — if order doesn't exist:
return {"error": f"Order '{order_id}' not found. Please verify the order ID."}
```

The system prompt instructs Claude: *"If a tool returns an error, relay it
honestly. Do not invent an alternative."* This converts a potential hallucination
moment into a transparent customer message.

### Layer 3: Deterministic Policy Engine

`evaluate_return` encodes policy as Python logic, not Claude's interpretation.
Return eligibility is computed by rule priority:

```
Clearance → DENY (final sale)
  ↓
Aurelia Couture → exchange only
  ↓
Sale item → 7 days, store credit
  ↓
Nocturne → 21 days, full refund
  ↓
Normal → 14 days, full refund
```

Claude receives a `policy_rule` field (e.g., `CLEARANCE_FINAL_SALE`) and writes
the explanation — it cannot override or misremember the rule because the rule
was already applied by code.

---

## Key Design Decisions

### Why not put all policy in the system prompt?
Policy in prompts can be misquoted, misapplied to edge cases, or ignored under
complex reasoning chains. Encoding it as Python logic makes it testable, version-
controlled, and impossible to bypass by the LLM.

### Why sort by bestseller_score?
Business awareness: the agent surfaces what sells, not just what technically
matches. A dress in size 8 under $300 with a score of 95 is a better
recommendation than one with a score of 30 — even if both satisfy the filters.

### Why join orders with products in get_order?
Return eligibility depends on the product's `is_clearance`, `is_sale`, and
`vendor` fields — not just the order record. Joining at retrieval time gives
Claude one coherent object to reason about, reducing the chance of mismatched
data across two separate tool calls.

### Why a max iteration guard?
Tool-calling loops can theoretically run indefinitely if Claude keeps requesting
data without converging. The guard at 8 iterations (generous for any realistic
query) provides a safety net without affecting normal operation.

---

## Data Flow Examples

**Shopping query:**
```
"modest gown under $300 in size 8 on sale"
  → search_products({tags:"modest,evening", max_price:300, size:8, is_sale:true})
  → [{P0004, $120, score:90, stock_size8:5}, ...]
  → Claude: "I recommend P0004 — here's why..."
```

**Return query:**
```
"Can I return order O0005?"
  → evaluate_return("O0005")
  → {eligible:true, policy_rule:"NORMAL_14_DAY_FULL_REFUND", days_remaining:12}
  → Claude: "Yes, you have 12 days left in your return window..."
```

**Edge case:**
```
"Return order O9999"
  → evaluate_return("O9999")
  → {eligible:false, policy_rule:"ORDER_NOT_FOUND", reason:"Order 'O9999' not found."}
  → Claude: "I wasn't able to find order O9999..."
```
