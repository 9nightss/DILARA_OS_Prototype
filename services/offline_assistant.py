"""Small transparent offline assistant for D-LLM's no-model fallback.

This is not a generative LLM. It provides local help, notes, and simple utilities
without network access. A real custom model can replace it behind this adapter.
"""
from __future__ import annotations
import ast, operator, re

_ALLOWED = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod, ast.USub: operator.neg, ast.UAdd: operator.pos}

def _safe_math(expression: str):
    if len(expression) > 80 or not re.fullmatch(r"[0-9+*/().% \-]+", expression): raise ValueError
    tree = ast.parse(expression, mode="eval")
    def visit(node):
        if isinstance(node, ast.Expression): return visit(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)): return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED: return _ALLOWED[type(node.op)](visit(node.left), visit(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED: return _ALLOWED[type(node.op)](visit(node.operand))
        raise ValueError
    value = visit(tree)
    if abs(value) > 10**15: raise ValueError
    return value

def respond(prompt: str) -> str:
    text = prompt.strip()
    low = text.casefold()
    if not text: return "Enter a message to begin."
    if low in {"help", "/help", "what can you do?"}:
        return ("D-LLM Offline Assistant (built-in, no network):\n"
                "• Explain DILARA modules and the current session\n"
                "• Perform simple arithmetic by starting a message with /calc\n"
                "• Keep this conversation local to the current window (not saved)\n\n"
                "This is a transparent offline fallback, not a trained generative model. For model-based responses, select Ollama or configure a compatible local model.")
    if low.startswith("/calc "):
        try: return f"Result: {_safe_math(text[6:].strip())}"
        except Exception: return "I couldn't evaluate that expression. Use basic arithmetic only, for example: /calc (12 * 7) + 3"
    if any(x in low for x in ("what is dilara", "dilara modules", "what can dilara")):
        return ("DILARA is a local desktop-style hub. Its current workspaces are DSPACE, CYBERSTORM, EYE, KOD8, D-ARCADE, D-LLM, D-TERMINAL, and CHAOS. "
                "The app registry is extensible: administrators can add approved Python, URL, or folder shortcuts through Apps & Users.")
    if low in {"hello", "hi", "hello!", "hey"}: return "Hello. I'm the built-in offline D-LLM assistant. Type /help to see the local capabilities."
    return ("I received your message, but this offline fallback has no language-model weights, so it cannot generate a general answer. "
            "You can use /help or /calc, or switch to the Ollama-backed option for local model inference. No network request was made.")
