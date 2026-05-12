#!/usr/bin/env python3
"""
main.py — CLI entry point for the Retail AI Assistant.

Usage:
    python main.py                    # interactive mode
    python main.py --verbose          # show tool calls in real time
    python main.py --demo             # run all demo scenarios automatically
    python main.py --demo --verbose   # demo with tool trace
"""

import argparse
import sys
from pathlib import Path

# Ensure project root is on the path
sys.path.insert(0, str(Path(__file__).parent))

from agent.agent import run_agent

# ── ANSI colours for readability ──────────────────────────────────────────────
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RESET = "\033[0m"
BOLD = "\033[1m"

BANNER = f"""
{BOLD}{CYAN}╔══════════════════════════════════════════════════════╗
║        RETAIL AI ASSISTANT — Fashion Boutique        ║
║  Personal Shopper  ·  Returns & Support              ║
║  Powered by Google Gemini                            ║
╚══════════════════════════════════════════════════════╝{RESET}
Type your question and press Enter. Type {YELLOW}quit{RESET} or {YELLOW}exit{RESET} to leave.
"""

# ── Demo scenarios for the screen recording ───────────────────────────────────
DEMO_SCENARIOS = [
    {
        "label": "🛍️  Shopping Scenario 1 — Multi-constraint filter (modest + sale + size)",
        "input": "I need a modest evening gown under $300 in size 8. I prefer something on sale.",
    },
    {
        "label": "🛍️  Shopping Scenario 2 — Occasion + size + budget",
        "input": "Looking for a cocktail dress in size 10, budget is $200. What would you recommend?",
    },
    {
        "label": "🔄  Support Scenario 1 — Nocturne order (extended 21-day window)",
        "input": "Hi, my order is O0004. The dress doesn't fit. Can I return it for a refund?",
    },
    {
        "label": "🔄  Support Scenario 2 — Clearance item return attempt",
        "input": "I want to return order O0003. It's a bit tight. Can I get my money back?",
    },
    {
        "label": "🔄  Support Scenario 3 — Aurelia Couture (exchange only, no refund)",
        "input": "I'd like to return order O0012 for a full refund. The colour isn't what I expected.",
    },
    {
        "label": "⚠️  Edge Case — Non-existent order ID",
        "input": "Can I return order O9999? I need to know ASAP.",
    },
]


def print_separator():
    print(f"\n{CYAN}{'─' * 56}{RESET}\n")


def run_demo(verbose: bool):
    print(BANNER)
    print(f"{BOLD}{YELLOW}▶  DEMO MODE — Running {len(DEMO_SCENARIOS)} scenarios{RESET}\n")

    for i, scenario in enumerate(DEMO_SCENARIOS, 1):
        print_separator()
        print(f"{BOLD}[{i}/{len(DEMO_SCENARIOS)}] {scenario['label']}{RESET}")
        print(f"\n{GREEN}Customer:{RESET} {scenario['input']}\n")

        response = run_agent(scenario["input"], verbose=verbose)

        print(f"{CYAN}Assistant:{RESET}\n{response}\n")

    print_separator()
    print(f"{BOLD}{GREEN}✓ Demo complete.{RESET}\n")


def run_interactive(verbose: bool):
    print(BANNER)

    while True:
        try:
            user_input = input(f"{GREEN}You:{RESET} ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break

        if not user_input:
            continue

        if user_input.lower() in ("quit", "exit", "q"):
            print("Goodbye!")
            break

        print()
        response = run_agent(user_input, verbose=verbose)
        print(f"{CYAN}Assistant:{RESET}\n{response}\n")


def main():
    parser = argparse.ArgumentParser(description="Retail AI Assistant CLI")
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print tool calls and raw results to stderr",
    )
    parser.add_argument(
        "--demo", "-d",
        action="store_true",
        help="Run all demo scenarios automatically and exit",
    )
    args = parser.parse_args()

    if args.demo:
        run_demo(verbose=args.verbose)
    else:
        run_interactive(verbose=args.verbose)


if __name__ == "__main__":
    main()
