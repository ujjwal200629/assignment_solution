# data/

Static data files that serve as the system's source of truth. All tools read from these files at runtime using `pandas.read_csv`. No database — no migrations — no connection pooling. Files are loaded fresh on each tool call.

---

## Files

| File | Rows | Purpose |
|------|------|---------|
| `product_inventory.csv` | 100 products | Full product catalogue — prices, tags, stock, vendors |
| `orders.csv` | ~50 orders | Customer order history — links orders to products |
| `policy.txt` | — | Human-readable return policy (reference only) |

---

## product_inventory.csv

The product catalogue. Read by `search_products`, `get_product`, and `get_order`.

### Schema

| Column | Type | Description |
|--------|------|-------------|
| `product_id` | `str` | Unique identifier, e.g. `P0001` |
| `title` | `str` | Display name, e.g. `Silk Avenue Style 1` |
| `vendor` | `str` | Brand name — one of six vendors (see below) |
| `price` | `float` | Current selling price in USD |
| `compare_at_price` | `float` | Original price (used to show discount) |
| `tags` | `str` | Comma-separated style/occasion tags |
| `sizes_available` | `str` | Pipe-separated list of sizes, e.g. `8\|4\|14` |
| `stock_per_size` | `str` | Python dict literal, e.g. `{'8': 18, '4': 13}` |
| `is_sale` | `bool` | True if currently on sale |
| `is_clearance` | `bool` | True if clearance (final sale, no returns) |
| `bestseller_score` | `int` | Popularity score 1–99 — higher is more popular |

### Vendors

| Vendor | Return policy exception |
|--------|------------------------|
| Silk Avenue | Standard |
| Velour House | Standard |
| Aurelia Couture | Exchange only — no refunds |
| Lumiere | Standard |
| Eden Atelier | Standard |
| Nocturne | Extended 21-day return window |

### Tags reference

Available tags used in `search_products` filtering:

`cocktail` · `evening` · `modest` · `prom` · `bridal` · `lace` · `flowy` · `fitted` · `sleeve` · `minimal` · `sparkle` · `casual`

### stock_per_size format

Stock is stored as a Python dict literal string — `ast.literal_eval` parses it at query time:

```python
# Raw CSV value:
"{'8': 18, '4': 13, '14': 1, '2': 0, '10': 2}"

# Parsed:
{8: 18, 4: 13, 14: 1, 2: 0, 10: 2}
```

A size with qty `0` is treated as out of stock by `search_products`. A size missing from the dict entirely is also out of stock.

### Sample row

```
product_id: P0001
title:       Silk Avenue Style 1
vendor:      Silk Avenue
price:       137.0
compare_at_price: 137.0
tags:        cocktail,lace,flowy
sizes_available: 8|4|14|2|10
stock_per_size:  {'8': 18, '4': 13, '14': 1, '2': 0, '10': 2}
is_sale:     False
is_clearance: False
bestseller_score: 72
```

---

## orders.csv

Customer order history. Read by `get_order` (and indirectly by `evaluate_return` through `get_order`).

### Schema

| Column | Type | Description |
|--------|------|-------------|
| `order_id` | `str` | Unique order identifier, e.g. `O0001` |
| `order_date` | `str` | ISO date string `YYYY-MM-DD` |
| `product_id` | `str` | Foreign key into `product_inventory.csv` |
| `size` | `int` | Size ordered |
| `price_paid` | `float` | Amount paid at time of order |
| `customer_id` | `str` | Customer identifier, e.g. `C011` |

### Join with products

`get_order` always joins this table with `product_inventory.csv` on `product_id`. The joined result includes the product's current `is_clearance`, `is_sale`, and `vendor` — the fields `evaluate_return` needs to apply policy rules.

### Sample rows

```
O0001 | 2026-01-28 | P0015 | size 14 | $298 | C011
O0003 | 2026-02-03 | P0018 | size 16 | $376 | C040  ← clearance item
O0004 | 2026-02-08 | P0086 | size 16 | $316 | C004  ← Nocturne vendor
```

### Order IDs used in demo scenarios

| Order ID | Scenario | Expected outcome |
|----------|----------|-----------------|
| `O0003` | Clearance return attempt | Refused — final sale |
| `O0004` | Nocturne return | Refused — 21-day window expired (93 days ago) |
| `O0012` | Aurelia Couture return | Exchange only — no refund |
| `O9999` | Non-existent order | `ORDER_NOT_FOUND` error |

---

## policy.txt

Human-readable version of the return policy. Not read by any tool at runtime — it is the source of truth from which the **policy constants** in `evaluate_return.py` were derived.

```
NORMAL_RETURN_DAYS   = 14   # Normal Items
SALE_RETURN_DAYS     = 7    # Sale Items
NOCTURNE_EXTENDED_DAYS = 21 # Nocturne vendor exception
```

If the policy changes, update both `policy.txt` (for humans) and the constants in `evaluate_return.py` (for the code).

### Full policy

```
Return Policy

Normal Items:
  Returns accepted within 14 days of delivery for a full refund.

Sale Items:
  Returnable within 7 days. Store credit only.

Clearance Items:
  Final sale. Not eligible for return or exchange.

Vendor Exceptions:
  Aurelia Couture: Exchanges only, no refunds.
  Nocturne: Extended return window of 21 days.

Exchange Rules:
  Size exchanges allowed if stock available.
  Customer pays return shipping unless defective.
```
