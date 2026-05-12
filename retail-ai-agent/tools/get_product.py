"""
Tool: get_product
Fetches the full record for a single product by its product_id.

Use this when you have a specific product ID and need complete details
(stock breakdown by size, compare_at_price, tags, vendor). For browsing or
filtering the catalogue, use search_products instead.

Returns a full product dict on success, or {"error": "..."} if the ID
does not exist in inventory — never invents or approximates data.
"""

import ast
import pandas as pd
from pathlib import Path

DATA_PATH = Path(__file__).parent.parent / "data" / "product_inventory.csv"


def get_product(product_id: str) -> dict:
    """
    Fetch one product by ID.

    Returns:
      Full product dict on success.
      {"error": "Product <id> not found."} if ID doesn't exist.
    """
    try:
        df = pd.read_csv(DATA_PATH)
    except FileNotFoundError:
        return {"error": "Product inventory file not found."}

    product_id = str(product_id).strip().upper()
    row = df[df["product_id"].str.upper() == product_id]

    if row.empty:
        return {"error": f"Product '{product_id}' not found in inventory."}

    r = row.iloc[0]

    # Parse stock dict
    try:
        raw_stock = ast.literal_eval(str(r["stock_per_size"]))
        stock = {int(k): int(v) for k, v in raw_stock.items()}
    except Exception:
        stock = {}

    return {
        "product_id": r["product_id"],
        "title": r["title"],
        "vendor": r["vendor"],
        "price": float(r["price"]),
        "compare_at_price": float(r["compare_at_price"]) if pd.notna(r["compare_at_price"]) else None,
        "tags": r["tags"],
        "sizes_available": r["sizes_available"],
        "stock_per_size": stock,
        "is_sale": bool(r["is_sale"]),
        "is_clearance": bool(r["is_clearance"]),
        "bestseller_score": int(r["bestseller_score"]),
    }
