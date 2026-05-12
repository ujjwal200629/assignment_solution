"""
Tool: search_products
Filters the product inventory by any combination of constraints and returns
results ranked by bestseller_score descending.

Design notes:
  - All filters are optional; omitting a filter means "no restriction" on that axis.
  - Tag matching uses AND logic: a product must carry ALL requested tags to qualify.
    This prevents over-broad results when the customer specifies multiple style criteria.
  - Size filtering checks stock qty > 0, not just whether the size is listed.
    A size listed with 0 units is treated as out of stock.
  - Results are ranked by bestseller_score so the model's top recommendation
    is always the most popular qualifying item — not arbitrary CSV order.
"""

import ast
import pandas as pd
from pathlib import Path

DATA_PATH = Path(__file__).parent.parent / "data" / "product_inventory.csv"


def _parse_stock(stock_str: str) -> dict:
    """Parse stock_per_size from dict-like string to a real dict with int keys."""
    try:
        raw = ast.literal_eval(stock_str)
        return {int(k): int(v) for k, v in raw.items()}
    except Exception:
        return {}


def search_products(**filters) -> dict:  # noqa: ANN003
    """
    Search products with optional filters:
      - tags        : list[str] | str  — all tags must match (AND logic)
      - max_price   : float            — upper price bound (inclusive)
      - min_price   : float            — lower price bound (inclusive)
      - size        : int              — must be available AND in stock (qty > 0)
      - is_sale     : bool             — only sale items
      - is_clearance: bool             — only clearance items
      - vendor      : str              — exact vendor name match (case-insensitive)
      - limit       : int              — max results to return (default 5)

    Returns:
      {"results": [...], "count": int, "filters_applied": {...}}
      or {"error": "...", "results": [], "count": 0}
    """
    try:
        df = pd.read_csv(DATA_PATH)
    except FileNotFoundError:
        return {"error": "Product inventory file not found.", "results": [], "count": 0}

    limit = int(filters.get("limit", 5))
    applied = {}

    # --- tag filter (AND: product must have ALL requested tags) ---
    raw_tags = filters.get("tags")
    if raw_tags:
        if isinstance(raw_tags, str):
            tag_list = [t.strip().lower() for t in raw_tags.split(",")]
        else:
            tag_list = [t.strip().lower() for t in raw_tags]
        applied["tags"] = tag_list

        def has_all_tags(row_tags):
            row_tag_set = {t.strip().lower() for t in str(row_tags).split(",")}
            return all(t in row_tag_set for t in tag_list)

        df = df[df["tags"].apply(has_all_tags)]

    # --- price filters ---
    if "max_price" in filters:
        applied["max_price"] = filters["max_price"]
        df = df[df["price"] <= float(filters["max_price"])]

    if "min_price" in filters:
        applied["min_price"] = filters["min_price"]
        df = df[df["price"] >= float(filters["min_price"])]

    # --- sale / clearance flags ---
    if "is_sale" in filters:
        val = filters["is_sale"]
        if isinstance(val, str):
            val = val.lower() in ("true", "1", "yes")
        applied["is_sale"] = val
        df = df[df["is_sale"] == val]

    if "is_clearance" in filters:
        val = filters["is_clearance"]
        if isinstance(val, str):
            val = val.lower() in ("true", "1", "yes")
        applied["is_clearance"] = val
        df = df[df["is_clearance"] == val]

    # --- vendor filter ---
    if "vendor" in filters:
        applied["vendor"] = filters["vendor"]
        df = df[df["vendor"].str.lower() == filters["vendor"].lower()]

    # --- size filter: available AND in stock ---
    requested_size = filters.get("size")
    if requested_size is not None:
        requested_size = int(requested_size)
        applied["size"] = requested_size

        def size_in_stock(row):
            stock = _parse_stock(str(row["stock_per_size"]))
            return stock.get(requested_size, 0) > 0

        df = df[df.apply(size_in_stock, axis=1)]

    if df.empty:
        return {
            "results": [],
            "count": 0,
            "filters_applied": applied,
            "message": "No products match the given filters.",
        }

    # --- rank by bestseller_score descending ---
    df = df.sort_values("bestseller_score", ascending=False)

    results = []
    for _, row in df.head(limit).iterrows():
        stock = _parse_stock(str(row["stock_per_size"]))
        size_stock = stock.get(requested_size) if requested_size else None

        entry = {
            "product_id": row["product_id"],
            "title": row["title"],
            "vendor": row["vendor"],
            "price": float(row["price"]),
            "compare_at_price": float(row["compare_at_price"]) if pd.notna(row["compare_at_price"]) else None,
            "tags": row["tags"],
            "sizes_available": row["sizes_available"],
            "is_sale": bool(row["is_sale"]),
            "is_clearance": bool(row["is_clearance"]),
            "bestseller_score": int(row["bestseller_score"]),
        }
        if requested_size is not None:
            entry["stock_for_requested_size"] = size_stock

        results.append(entry)

    return {
        "results": results,
        "count": len(results),
        "filters_applied": applied,
    }
