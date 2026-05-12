"""
agent.py
Core agentic loop for the Retail AI Assistant — powered by Google Gemini.

Architecture:
  - Gemini acts as orchestrator: reads the user message, decides which tool
    to call, receives the structured result, and writes a human response.
  - Tools are pure Python — they do data retrieval and rule evaluation.
  - The loop continues until Gemini produces a final text response (no more
    function calls) or hits the max-iteration safety guard.
  - Hallucination is prevented by: (a) no product/order data in the system
    prompt, (b) tools return explicit errors for missing IDs, (c) Gemini is
    instructed never to mention specifics it hasn't retrieved via a tool call.
"""

import json
import sys
from pathlib import Path

import google.generativeai as genai  # type: ignore[import]
from google.generativeai import types  # type: ignore[import]

# Add project root to path so tools import correctly
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.tool_registry import TOOL_DEFINITIONS
from tools import evaluate_return, get_order, get_product, search_products

# ── Dispatch table — maps tool name → Python function ────────────────────────
TOOL_DISPATCH = {
    "search_products": search_products,
    "get_product": get_product,
    "get_order": get_order,
    "evaluate_return": evaluate_return,
}

# ── System prompt ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are an intelligent retail AI assistant for a women's fashion boutique.
You operate in two modes depending on what the customer needs:

MODE 1 — PERSONAL SHOPPER
Help customers find the perfect dress. When they describe what they want,
call search_products with the appropriate filters. Then explain your top
recommendation clearly: why it fits their constraints (size, price, style,
sale status), how many are in stock for their size, and why the bestseller
score makes it a confident pick. If multiple strong options exist, briefly
mention the runner-up. Reason like a knowledgeable stylist, not a database.

MODE 2 — CUSTOMER SUPPORT
When a customer mentions an order or return, call evaluate_return immediately.
Present the decision clearly: eligible or not, what type of refund applies,
how many days remain in the window, and which policy rule governs the decision.
Be empathetic but accurate — do not promise outcomes the policy doesn't support.

STRICT RULES (non-negotiable):
1. Never mention a product name, price, or stock level you have not fetched
   via a tool call in this conversation. If you don't have the data, get it.
2. If a tool returns {"error": "..."}, relay that error honestly to the customer.
   Do not invent an alternative or guess at the answer.
3. For return decisions, always use evaluate_return — never reason about policy
   from memory. The tool applies the rules correctly; you write the explanation.
4. If a customer asks about an order ID you haven't looked up yet, call get_order
   or evaluate_return before saying anything about that order.
5. Keep responses concise and warm. Bullet points are fine for multiple options.
   Avoid jargon. End support responses with a clear next step for the customer.
"""

MAX_ITERATIONS = 8  # safety guard against infinite loops

MODEL = "gemini-2.5-flash-preview-04-17"
def run_agent(user_message: str, verbose: bool = False) -> str:
    """
    Run one conversational turn through the Gemini agentic loop.

    Gemini's multi-turn tool-calling pattern:
      1. Send user message → Gemini returns FunctionCall parts
      2. Execute each function, wrap result in FunctionResponse parts
      3. Send FunctionResponse back as a new turn
      4. Repeat until Gemini returns only text (no function calls)

    Args:
        user_message: The customer's message.
        verbose: If True, print tool calls and results to stderr.

    Returns:
        The assistant's final response as a string.
    """
    # ── Gemini client (reads GEMINI_API_KEY from environment) ────────────────
    client = genai.Client(api_key="AIzaSyAT_nr09BY6svhvGhposBM97ZqjSFeKZv8")

    # Build conversation history as a list of Content objects
    history: list[types.Content] = [
        types.Content(role="user", parts=[types.Part(text=user_message)])
    ]

    for iteration in range(MAX_ITERATIONS):
        response = client.models.generate_content(
            model=MODEL,
            contents=history,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                tools=[TOOL_DEFINITIONS],
                temperature=0.1,   # low temp for deterministic tool selection
            ),
        )

        candidate = response.candidates[0]
        parts = candidate.content.parts

        # Separate function calls from text parts
        function_call_parts = [p for p in parts if p.function_call is not None]
        text_parts = [p for p in parts if p.text]

        # ── Case 1: Gemini wants to call one or more tools ────────────────────
        if function_call_parts:
            # Append Gemini's full response (reasoning + function calls) to history
            history.append(types.Content(role="model", parts=parts))

            # Execute each function call and collect FunctionResponse parts
            response_parts = []
            for part in function_call_parts:
                fc = part.function_call
                tool_name = fc.name
                tool_args = dict(fc.args) if fc.args else {}

                if verbose:
                    print(
                        f"\n[TOOL CALL] {tool_name}({json.dumps(tool_args, indent=2)})",
                        file=sys.stderr,
                    )

                func = TOOL_DISPATCH.get(tool_name)
                if func is None:
                    result = {"error": f"Unknown tool: {tool_name}"}
                else:
                    try:
                        result = func(**tool_args)
                    except Exception as e:
                        result = {"error": f"Tool execution failed: {str(e)}"}

                if verbose:
                    print(
                        f"[TOOL RESULT] {json.dumps(result, indent=2, default=str)[:800]}",
                        file=sys.stderr,
                    )

                response_parts.append(
                    types.Part(
                        function_response=types.FunctionResponse(
                            name=tool_name,
                            response={"result": json.dumps(result, default=str)},
                        )
                    )
                )

            # Feed all tool results back as a single user turn
            history.append(types.Content(role="user", parts=response_parts))

        # ── Case 2: Gemini produced a final text response ─────────────────────
        elif text_parts:
            return " ".join(p.text for p in text_parts).strip()

        else:
            return "[Agent stopped: no text or function call in response.]"

    return "[Agent reached maximum iterations without producing a final response.]"
