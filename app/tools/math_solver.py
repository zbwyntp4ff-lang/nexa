"""Bounded symbolic mathematics powered by SymPy.

Input is parsed with Python's AST and translated node-by-node. Never pass
untrusted expressions to sympify/parse_expr/eval/exec.
"""
from __future__ import annotations

import ast
import math
from typing import Any

import sympy as sp

from app.tools.base import Tool, ToolResult

_MAX_EXPRESSION_LENGTH = 500
_MAX_AST_NODES = 100
_MAX_AST_DEPTH = 20
_MAX_SYMBOLS = 4
_MAX_POWER = 100
_ALLOWED_FUNCTIONS = {
    "sqrt": sp.sqrt,
    "sin": sp.sin,
    "cos": sp.cos,
    "tan": sp.tan,
    "asin": sp.asin,
    "acos": sp.acos,
    "atan": sp.atan,
    "exp": sp.exp,
    "log": sp.log,
    "abs": sp.Abs,
}
_CONSTANTS = {"pi": sp.pi, "E": sp.E}
_ALLOWED_BINOPS = {
    ast.Add: lambda a, b: a + b,
    ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b,
    ast.Div: lambda a, b: a / b,
    ast.Pow: lambda a, b: a**b,
}
_ALLOWED_UNARYOPS = {ast.UAdd: lambda a: a, ast.USub: lambda a: -a}


class MathExpressionError(ValueError):
    """An expression or operation is outside the supported safe subset."""


def _check_tree(node: ast.AST, depth: int = 0, count: list[int] | None = None) -> None:
    if count is None:
        count = [0]
    count[0] += 1
    if count[0] > _MAX_AST_NODES or depth > _MAX_AST_DEPTH:
        raise MathExpressionError("Expression is too complex.")
    for child in ast.iter_child_nodes(node):
        _check_tree(child, depth + 1, count)


def parse_math_expression(expression: str) -> tuple[sp.Expr, set[str]]:
    if not isinstance(expression, str) or not expression.strip():
        raise MathExpressionError("Expression must be a non-empty string.")
    if len(expression) > _MAX_EXPRESSION_LENGTH:
        raise MathExpressionError("Expression is too long.")
    try:
        tree = ast.parse(expression, mode="eval")
    except (SyntaxError, ValueError) as exc:
        raise MathExpressionError("Could not parse mathematical expression.") from exc
    _check_tree(tree)
    symbols: set[str] = set()

    def visit(node: ast.AST) -> sp.Expr:
        if isinstance(node, ast.Constant):
            value = node.value
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise MathExpressionError("Only numeric constants are supported.")
            if isinstance(value, float) and not math.isfinite(value):
                raise MathExpressionError("Non-finite constants are not supported.")
            return sp.Integer(value) if isinstance(value, int) else sp.Float(value)
        if isinstance(node, ast.Name):
            if node.id in _CONSTANTS:
                return _CONSTANTS[node.id]
            if not node.id.isidentifier() or node.id.startswith("_"):
                raise MathExpressionError("Invalid variable name.")
            symbols.add(node.id)
            if len(symbols) > _MAX_SYMBOLS:
                raise MathExpressionError("At most four variables are supported.")
            return sp.Symbol(node.id, real=True)
        if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_BINOPS:
            left, right = visit(node.left), visit(node.right)
            if isinstance(node.op, ast.Pow):
                if right.is_number and abs(float(right)) > _MAX_POWER:
                    raise MathExpressionError("Exponent magnitude is limited to 100.")
            return _ALLOWED_BINOPS[type(node.op)](left, right)
        if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_UNARYOPS:
            return _ALLOWED_UNARYOPS[type(node.op)](visit(node.operand))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            function = _ALLOWED_FUNCTIONS.get(node.func.id)
            if function is None or node.keywords or len(node.args) not in (1, 2):
                raise MathExpressionError("Unsupported function or function arguments.")
            if node.func.id != "log" and len(node.args) != 1:
                raise MathExpressionError("This function accepts exactly one argument.")
            return function(*(visit(arg) for arg in node.args))
        raise MathExpressionError(f"Unsupported expression element: {type(node).__name__}.")

    result = visit(tree.body)
    return result, symbols


class MathSolverTool(Tool):
    name = "math_solver"
    description = (
        "Solve bounded symbolic mathematics: simplify, differentiate, integrate, "
        "solve a polynomial equation, or evaluate an expression numerically. "
        "Use expression syntax such as 'x**2 + sin(x)'."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "enum": ["simplify", "differentiate", "integrate", "solve", "evaluate"],
            },
            "expression": {"type": "string", "minLength": 1, "maxLength": 500},
            "variable": {"type": "string", "default": "x"},
            "value": {"type": "number"},
        },
        "required": ["operation", "expression"],
        "additionalProperties": False,
    }
    permissions = frozenset({"compute"})

    async def execute(self, **kwargs: Any) -> ToolResult:
        operation = kwargs.get("operation")
        expression = kwargs.get("expression")
        variable = kwargs.get("variable", "x")
        if operation not in {"simplify", "differentiate", "integrate", "solve", "evaluate"}:
            return ToolResult(success=False, error="Unsupported math operation.")
        if not isinstance(variable, str) or not variable.isidentifier() or variable.startswith("_"):
            return ToolResult(success=False, error="Variable must be a valid identifier.")
        try:
            parsed, symbols = parse_math_expression(expression)
            symbol = sp.Symbol(variable, real=True)
            if operation in {"differentiate", "integrate", "solve"} and variable not in symbols:
                return ToolResult(success=False, error=f"Variable '{variable}' is not present in the expression.")
            if operation == "simplify":
                result = sp.simplify(parsed)
            elif operation == "differentiate":
                result = sp.diff(parsed, symbol)
            elif operation == "integrate":
                result = sp.integrate(parsed, symbol)
                if result.has(sp.Integral):
                    return ToolResult(success=False, error="Could not find a closed-form antiderivative.")
            elif operation == "solve":
                polynomial = sp.Poly(parsed, symbol)
                if polynomial.degree() > 8:
                    return ToolResult(success=False, error="Polynomial degree is limited to 8.")
                result = sp.solve(polynomial.as_expr(), symbol)
            else:
                value = kwargs.get("value")
                if symbols:
                    if variable not in symbols or len(symbols) != 1 or value is None:
                        return ToolResult(success=False, error="Numerical evaluation requires one variable and a numeric 'value'.")
                    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                        return ToolResult(success=False, error="'value' must be a finite number.")
                    parsed = parsed.subs(symbol, value)
                result = sp.N(parsed, 15)
                if result.free_symbols:
                    return ToolResult(success=False, error="Expression still contains unresolved variables.")
                if result.is_finite is False:
                    return ToolResult(success=False, error="Result is not finite.")
            rendered = str(result)
            if len(rendered) > 10_000:
                return ToolResult(success=False, error="Result is too large to return safely.")
            return ToolResult(
                success=True,
                output=rendered,
                metadata={"operation": operation, "variable": variable, "engine": "sympy"},
            )
        except MathExpressionError as exc:
            return ToolResult(success=False, error=str(exc))
        except (ArithmeticError, TypeError, ValueError, NotImplementedError) as exc:
            return ToolResult(success=False, error=f"Math operation failed safely ({exc.__class__.__name__}).")
