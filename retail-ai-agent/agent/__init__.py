"""
agent package — Gemini agentic loop and tool registry.

Public interface: run_agent(user_message, verbose) → str
"""

from agent.agent import run_agent

__all__ = ["run_agent"]
