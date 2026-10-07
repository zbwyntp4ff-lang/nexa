"""A safe arithmetic calculator tool.
Deliberately does **not** use ``eval()``. Expressions are parsed with
``ast`` and only a small whitelist of numeric operators is evaluated, so
arbitrary code execution is impossible even if the expression comes from
untrusted (model-generated) input.
"""
from __future__ import annotations
import ast
import operator
from typing import Any
from app.tools.base import Tool, ToolResult
_ALLOWED_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_ALLOWED_UNARYOPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}
class ExpressionError(ValueError):
    pass
def safe_eval_arithmetic(expression: str) -> float:
    """Evaluate a numeric expression containing only ``+ - * / // % ** ()``."""
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise ExpressionError(f"Could not parse expression: {exc}") from exc
    return _eval_node(tree.body)
def _eval_node(node: ast.AST) -> float:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return node.value
        raise ExpressionError(f"Unsupported constant: {node.value!r}")
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_BINOPS:
        left = _eval_node(node.left)
        right = _eval_node(node.right)
        try:
            return _ALLOWED_BINOPS[type(node.op)](left, right)
        except ZeroDivisionError as exc:
            raise ExpressionError("Division by zero.") from exc
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_UNARYOPS:
        return _ALLOWED_UNARYOPS[type(node.op)](_eval_node(node.operand))
    raise ExpressionError(f"Unsupported expression element: {ast.dump(node)}")
class CalculatorTool(Tool):
    name = "calculator"
    description = "Evaluate a basic arithmetic expression, e.g. '25 * 37'."
    input_schema = {
        "type": "object",
        "properties": {
            "expression": {
                "type": "string",
                "description": "An arithmetic expression using + - * / // % ** and parentheses.",
            }
        },
        "required": ["expression"],
    }
    permissions = frozenset({"compute"})
    async def execute(self, **kwargs: Any) -> ToolResult:
        expression = kwargs.get("expression")
        if not expression or not isinstance(expression, str):
            return ToolResult(success=False, error="'expression' must be a non-empty string.")
        try:
            value = safe_eval_arithmetic(expression)
        except ExpressionError as exc:
            return ToolResult(success=False, error=str(exc))
        except RecursionError:
            return ToolResult(success=False, error="Expression is too deeply nested.")
        return ToolResult(success=True, output=value, metadata={"expression": expression})
