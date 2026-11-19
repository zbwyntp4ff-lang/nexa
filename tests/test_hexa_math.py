from __future__ import annotations

import pytest

from app.tools.math_solver import MathSolverTool, MathExpressionError, parse_math_expression


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("x**2 + 2*x + 1", "x**2 + 2*x + 1"),
        ("sin(pi / 2)", "1"),
        ("sqrt(81)", "9"),
    ],
)
def test_safe_math_parser(expression, expected):
    parsed, _ = parse_math_expression(expression)
    assert str(parsed) == expected


@pytest.mark.asyncio
async def test_math_solver_differentiates():
    result = await MathSolverTool().execute(operation="differentiate", expression="x**3 + 2*x", variable="x")
    assert result.success
    assert result.output == "3*x**2 + 2"


@pytest.mark.asyncio
async def test_math_solver_integrates():
    result = await MathSolverTool().execute(operation="integrate", expression="2*x", variable="x")
    assert result.success
    assert result.output == "x**2"


@pytest.mark.asyncio
async def test_math_solver_solves_polynomial():
    result = await MathSolverTool().execute(operation="solve", expression="x**2 - 4", variable="x")
    assert result.success
    assert result.output == "[-2, 2]"


@pytest.mark.asyncio
async def test_math_solver_evaluates_with_substitution():
    result = await MathSolverTool().execute(operation="evaluate", expression="x**2 + 1", variable="x", value=4)
    assert result.success
    assert result.output == "17.0000000000000"


@pytest.mark.asyncio
async def test_math_solver_rejects_code_execution():
    result = await MathSolverTool().execute(
        operation="evaluate",
        expression="__import__('os').system('echo unsafe')",
    )
    assert not result.success


@pytest.mark.asyncio
async def test_math_solver_rejects_extra_fields_by_behavior():
    result = await MathSolverTool().execute(operation="unknown", expression="x")
    assert not result.success


def test_math_parser_rejects_large_expression():
    with pytest.raises(MathExpressionError, match="too long"):
        parse_math_expression("1+" * 300 + "1")
