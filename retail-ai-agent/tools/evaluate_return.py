"""
Tool: evaluate_return
Applies the store's return policy to an order and returns a structured,
authoritative eligibility decision.

Design rationale:
  This is intentionally pure rule logic — no LLM is involved in the decision.
  Encoding policy as a deterministic priority chain guarantees correctness
  regardless of how the question is phrased. The model's role is only to write
  a warm, human explanation of the outcome this tool produces.

Rule priority (first match wins):
  1. Order not found         → hard refuse
  2. Clearance item          → final sale, no return
  3. Aurelia Couture vendor  → exchange only, no refund (14-day window)
  4. Sale item               → 7-day store credit only
  5. Nocturne vendor         → extended 21-day full refund window
  6. Normal item             → standard 14-day full refund

The tool calls get_order internally rather than accepting a pre-fetched order,
so the agent can call evaluate_return directly without a prior get_order call.
"""

from datetime import date, datetime
from pathlib import Path
from tools.get_order import get_order

POLICY_PATH = Path(__file__).parent.parent / "data" / "policy.txt"

# ── Policy constants (mirrors policy.txt exactly) ────────────────────────────
NORMAL_RETURN_DAYS = 14
SALE_RETURN_DAYS = 7
NOCTURNE_EXTENDED_DAYS = 21

VENDOR_RULES = {
    "aurelia couture": {
        "exchange_only": True,
        "refund_eligible": False,
        "note": "Aurelia Couture: exchanges only, no refunds.",
    },
    "nocturne": {
        "return_window_days": NOCTURNE_EXTENDED_DAYS,
        "note": f"Nocturne: extended {NOCTURNE_EXTENDED_DAYS}-day return window applies.",
    },
}


def _days_since_order(order_date_str: str) -> int:
    """Return how many days ago the order was placed (relative to today)."""
    order_date = datetime.strptime(str(order_date_str).strip(), "%Y-%m-%d").date()
    return (date.today() - order_date).days


def evaluate_return(order_id: str) -> dict:
    """
    Evaluate return eligibility for an order.

    Decision chain (first matching rule wins):
      1. Order not found → hard refuse
      2. Clearance item  → final sale, no return
      3. Vendor exception (Aurelia Couture) → exchange only, no refund
      4. Sale item       → 7-day window, store credit only
      5. Vendor exception (Nocturne) → 21-day window
      6. Normal item     → 14-day window, full refund

    Returns:
      {
        "order_id": str,
        "eligible": bool,
        "exchange_only": bool,
        "refund_type": "full" | "store_credit" | "none",
        "policy_rule": str,          # which rule fired
        "days_since_order": int,
        "window_days": int,
        "days_remaining": int,       # negative = expired
        "product_title": str,
        "vendor": str,
        "is_sale": bool,
        "is_clearance": bool,
        "exchange_size_available": bool | None,  # None if not applicable
      }
    """
    order = get_order(order_id)

    # ── Rule 1: Order must exist ──────────────────────────────────────────────
    if "error" in order:
        return {
            "order_id": order_id,
            "eligible": False,
            "exchange_only": False,
            "refund_type": "none",
            "policy_rule": "ORDER_NOT_FOUND",
            "reason": order["error"],
        }

    product = order.get("product_details") or {}
    vendor_lower = product.get("vendor", "").lower()
    is_clearance = product.get("is_clearance", False)
    is_sale = product.get("is_sale", False)
    days_since = _days_since_order(order["order_date"])

    base = {
        "order_id": order["order_id"],
        "order_date": order["order_date"],
        "days_since_order": days_since,
        "product_title": product.get("title", "Unknown"),
        "vendor": product.get("vendor", "Unknown"),
        "is_sale": is_sale,
        "is_clearance": is_clearance,
        "size_ordered": order["size"],
        "price_paid": order["price_paid"],
    }

    # ── Rule 2: Clearance → final sale ───────────────────────────────────────
    if is_clearance:
        return {
            **base,
            "eligible": False,
            "exchange_only": False,
            "refund_type": "none",
            "policy_rule": "CLEARANCE_FINAL_SALE",
            "window_days": 0,
            "days_remaining": 0,
            "reason": "Clearance items are final sale and not eligible for return or exchange.",
        }

    # ── Rule 3: Aurelia Couture → exchange only (no refund) ──────────────────
    if vendor_lower == "aurelia couture":
        window = NORMAL_RETURN_DAYS
        days_remaining = window - days_since
        within_window = days_remaining >= 0
        return {
            **base,
            "eligible": within_window,
            "exchange_only": True,
            "refund_type": "none",
            "policy_rule": "VENDOR_AURELIA_EXCHANGE_ONLY",
            "window_days": window,
            "days_remaining": days_remaining,
            "reason": (
                f"Aurelia Couture items are eligible for exchange only — no refunds. "
                f"{'Within' if within_window else 'Outside'} the {window}-day window "
                f"({days_since} days since order)."
            ),
        }

    # ── Rule 4: Sale item → 7-day window, store credit only ──────────────────
    if is_sale:
        window = SALE_RETURN_DAYS
        days_remaining = window - days_since
        within_window = days_remaining >= 0
        return {
            **base,
            "eligible": within_window,
            "exchange_only": False,
            "refund_type": "store_credit" if within_window else "none",
            "policy_rule": "SALE_ITEM_7_DAY_STORE_CREDIT",
            "window_days": window,
            "days_remaining": days_remaining,
            "reason": (
                f"Sale items are returnable within {window} days for store credit only. "
                f"Order was {days_since} day(s) ago — "
                f"{'eligible' if within_window else 'window has expired'}."
            ),
        }

    # ── Rule 5: Nocturne → 21-day window, full refund ────────────────────────
    if vendor_lower == "nocturne":
        window = NOCTURNE_EXTENDED_DAYS
        days_remaining = window - days_since
        within_window = days_remaining >= 0
        return {
            **base,
            "eligible": within_window,
            "exchange_only": False,
            "refund_type": "full" if within_window else "none",
            "policy_rule": "VENDOR_NOCTURNE_21_DAY",
            "window_days": window,
            "days_remaining": days_remaining,
            "reason": (
                f"Nocturne has an extended {window}-day return window. "
                f"Order was {days_since} day(s) ago — "
                f"{'eligible for full refund' if within_window else 'window has expired'}."
            ),
        }

    # ── Rule 6: Normal item → 14-day window, full refund ─────────────────────
    window = NORMAL_RETURN_DAYS
    days_remaining = window - days_since
    within_window = days_remaining >= 0

    return {
        **base,
        "eligible": within_window,
        "exchange_only": False,
        "refund_type": "full" if within_window else "none",
        "policy_rule": "NORMAL_14_DAY_FULL_REFUND",
        "window_days": window,
        "days_remaining": days_remaining,
        "reason": (
            f"Standard return policy: {window} days for a full refund. "
            f"Order was {days_since} day(s) ago — "
            f"{'eligible' if within_window else 'window has expired'}."
        ),
    }
