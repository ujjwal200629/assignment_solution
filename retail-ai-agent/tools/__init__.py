"""
tools package — pure-Python tool functions for the Retail AI Assistant.

Each function is a self-contained data retrieval or rule evaluation unit.
No LLM calls occur inside any tool. Tools read from CSV files and return
plain dicts that are serialised as FunctionResponse content for Gemini.

All tools follow the same contract:
  - On success: return a dict with the requested data.
  - On failure: return {"error": "<human-readable message>"}.
    The agent relays this error to the customer without inventing alternatives.
"""

from tools.search_products import search_products
from tools.get_product import get_product
from tools.get_order import get_order
from tools.evaluate_return import evaluate_return

__all__ = ["search_products", "get_product", "get_order", "evaluate_return"]
