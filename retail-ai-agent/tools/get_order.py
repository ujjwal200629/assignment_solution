"""
Tool: get_order
Fetches an order record by order_id and enriches it with the linked product's
current attributes from the product inventory.

The join gives the agent both transaction context (what was paid, when, what size)
and current product state (is it still on sale? clearance? what vendor?), which
evaluate_return needs to apply policy rules correctly.

Edge case: if the product was removed from inventory after the order was placed,
the order is still returned with product_details=None and a warning field.
This prevents silent failures — the agent can still surface the order details
even when the product record is gone.
"""

import ast
import pandas as pd
from pathlib import Path

ORDERS_PATH = Path(__file__).parent.parent / "data" / "orders.csv"
PRODUCTS_PATH = Path(__file__).parent.parent / "data" / "product_inventory.csv"


def get_order(order_id: str) -> dict:
    """
    Fetch one order by ID, joined with its product record.

    Returns:
      {order fields + product fields} on success.
      {"error": "Order <id> not found."} if order doesn't exist.
      {"error": "..."} if the linked product is missing from inventory.
    """
    try:
        orders = pd.read_csv(ORDERS_PATH)
    except FileNotFoundError:
        return {"error": "Orders file not found."}

    order_id = str(order_id).strip().upper()
    row = orders[orders["order_id"].str.upper() == order_id]

    if row.empty:
        return {"error": f"Order '{order_id}' not found. Please verify the order ID and try again."}

    o = row.iloc[0]

    # Enrich with product data
    try:
        products = pd.read_csv(PRODUCTS_PATH)
    except FileNotFoundError:
        return {"error": "Product inventory file not found."}

    product_row = products[products["product_id"].str.upper() == str(o["product_id"]).upper()]

    if product_row.empty:
        # Order exists but product was removed — still return order data with a warning
        return {
            "order_id": o["order_id"],
            "order_date": o["order_date"],
            "product_id": o["product_id"],
            "size": int(o["size"]),
            "price_paid": float(o["price_paid"]),
            "customer_id": o["customer_id"],
            "product_details": None,
            "warning": f"Product '{o['product_id']}' linked to this order no longer exists in inventory.",
        }

    p = product_row.iloc[0]

    # Parse stock
    try:
        raw_stock = ast.literal_eval(str(p["stock_per_size"]))
        stock = {int(k): int(v) for k, v in raw_stock.items()}
    except Exception:
        stock = {}

    return {
        "order_id": o["order_id"],
        "order_date": str(o["order_date"]),
        "product_id": o["product_id"],
        "size": int(o["size"]),
        "price_paid": float(o["price_paid"]),
        "customer_id": o["customer_id"],
        "product_details": {
            "title": p["title"],
            "vendor": p["vendor"],
            "current_price": float(p["price"]),
            "tags": p["tags"],
            "is_sale": bool(p["is_sale"]),
            "is_clearance": bool(p["is_clearance"]),
            "stock_per_size": stock,
        },
    }
