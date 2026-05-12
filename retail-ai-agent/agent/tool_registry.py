"""
tool_registry.py
Gemini-compatible FunctionDeclaration schemas for all four retail tools.

These declarations are passed to Gemini at inference time so the model knows
what tools exist, what arguments each one accepts, and when to call them.
The schema descriptions are prompt-level instructions — they directly influence
which tool Gemini picks and which arguments it supplies.

Pattern: each FunctionDeclaration mirrors the signature of its Python counterpart
in tools/. If a tool's signature changes, its declaration here must change too.
"""

from google.genai import types


# ── Helper: build Schema objects cleanly ─────────────────────────────────────

def _str_prop(description: str) -> types.Schema:
    return types.Schema(type=types.Type.STRING, description=description)

def _num_prop(description: str) -> types.Schema:
    return types.Schema(type=types.Type.NUMBER, description=description)

def _int_prop(description: str) -> types.Schema:
    return types.Schema(type=types.Type.INTEGER, description=description)

def _bool_prop(description: str) -> types.Schema:
    return types.Schema(type=types.Type.BOOLEAN, description=description)


# ── Four function declarations ────────────────────────────────────────────────

search_products_fn = types.FunctionDeclaration(
    name="search_products",
    description=(
        "Search and filter the product inventory. Use this when the customer "
        "describes what they are looking for — by style, occasion, size, price, "
        "sale status, or any combination. Returns ranked results sorted by "
        "bestseller_score. Always use this before recommending products — "
        "never invent product names or prices."
    ),
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "tags": _str_prop(
                "Comma-separated style/occasion tags to filter by. "
                "Available tags include: cocktail, evening, modest, prom, bridal, "
                "lace, flowy, fitted, sleeve, minimal, sparkle, casual. "
                "All specified tags must match (AND logic)."
            ),
            "max_price": _num_prop("Maximum price (inclusive) in USD."),
            "min_price": _num_prop("Minimum price (inclusive) in USD."),
            "size": _int_prop(
                "Dress size (e.g. 2, 4, 6, 8, 10, 12, 14, 16). "
                "Only products with this size in stock (qty > 0) are returned."
            ),
            "is_sale": _bool_prop("Set to true to return only items currently on sale."),
            "is_clearance": _bool_prop("Set to true to return only clearance items."),
            "vendor": _str_prop(
                "Filter by exact vendor name. "
                "Available vendors: Silk Avenue, Velour House, Aurelia Couture, "
                "Lumiere, Eden Atelier, Nocturne."
            ),
            "limit": _int_prop("Maximum number of results to return. Default is 5."),
        },
    ),
)

get_product_fn = types.FunctionDeclaration(
    name="get_product",
    description=(
        "Fetch the full details of a single product by its product_id "
        "(e.g. 'P0003'). Use this when you have a specific product ID and "
        "need its complete record — stock levels, vendor, tags, price. "
        "Do NOT use this for browsing or searching; use search_products for that."
    ),
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "product_id": _str_prop("The product ID, e.g. 'P0003' or 'P0045'."),
        },
        required=["product_id"],
    ),
)

get_order_fn = types.FunctionDeclaration(
    name="get_order",
    description=(
        "Fetch an order record by order_id (e.g. 'O0043'). Returns order details "
        "joined with the linked product's current attributes. Use this when a "
        "customer references a specific order and you need its raw data (date, "
        "product, size, price paid). For return eligibility decisions, prefer "
        "evaluate_return which applies policy rules automatically."
    ),
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "order_id": _str_prop("The order ID, e.g. 'O0043'. Case-insensitive."),
        },
        required=["order_id"],
    ),
)

evaluate_return_fn = types.FunctionDeclaration(
    name="evaluate_return",
    description=(
        "Evaluate whether an order is eligible for return or exchange under "
        "store policy. Applies all rules in priority order: clearance → "
        "vendor exceptions → sale items → normal items. Returns a structured "
        "decision with the policy rule that fired, days remaining in the window, "
        "and refund type. ALWAYS use this (not manual reasoning) when a customer "
        "asks about returning or exchanging an item."
    ),
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "order_id": _str_prop("The order ID to evaluate for return eligibility."),
        },
        required=["order_id"],
    ),
)

# ── Single Tool object passed to Gemini ──────────────────────────────────────
TOOL_DEFINITIONS = types.Tool(
    function_declarations=[
        search_products_fn,
        get_product_fn,
        get_order_fn,
        evaluate_return_fn,
    ]
)
