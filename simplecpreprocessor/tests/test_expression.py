"""Tests for expression parser."""
from __future__ import absolute_import
import pytest
from simplecpreprocessor.expression import evaluate_expression
from simplecpreprocessor.core import Defines
from simplecpreprocessor.tokens import Token, TokenType


def make_tokens(values):
    """Create Token objects from values."""
    return [
        Token.from_string(0, val, TokenType.IDENTIFIER)
        for val in values
    ]


def test_simple_integer():
    tokens = make_tokens(["42"])
    defines = Defines({})
    result = evaluate_expression(tokens, defines)
    assert result == 42


def test_simple_addition():
    tokens = make_tokens(["1", "+", "2"])
    defines = Defines({})
    result = evaluate_expression(tokens, defines)
    assert result == 3


def test_simple_subtraction():
    tokens = make_tokens(["5", "-", "3"])
    defines = Defines({})
    result = evaluate_expression(tokens, defines)
    assert result == 2


def test_multiplication():
    tokens = make_tokens(["3", "*", "4"])
    defines = Defines({})
    result = evaluate_expression(tokens, defines)
    assert result == 12


def test_division():
    tokens = make_tokens(["10", "/", "2"])
    defines = Defines({})
    result = evaluate_expression(tokens, defines)
    assert result == 5


def test_modulo():
    tokens = make_tokens(["10", "%", "3"])
    defines = Defines({})
    result = evaluate_expression(tokens, defines)
    assert result == 1


def test_precedence_multiply_before_add():
    tokens = make_tokens(["2", "+", "3", "*", "4"])
    defines = Defines({})
    result = evaluate_expression(tokens, defines)
    assert result == 14


def test_precedence_with_parentheses():
    tokens = make_tokens(["(", "2", "+", "3", ")", "*", "4"])
    defines = Defines({})
    result = evaluate_expression(tokens, defines)
    assert result == 20


def test_logical_and_true():
    tokens = make_tokens(["1", "&&", "1"])
    defines = Defines({})
    result = evaluate_expression(tokens, defines)
    assert result == 1


def test_logical_and_false():
    tokens = make_tokens(["1", "&&", "0"])
    defines = Defines({})
    result = evaluate_expression(tokens, defines)
    assert result == 0


def test_logical_or_true():
    tokens = make_tokens(["1", "||", "0"])
    defines = Defines({})
    result = evaluate_expression(tokens, defines)
    assert result == 1


def test_logical_or_false():
    tokens = make_tokens(["0", "||", "0"])
    defines = Defines({})
    result = evaluate_expression(tokens, defines)
    assert result == 0


def test_logical_not_true():
    tokens = make_tokens(["!", "0"])
    defines = Defines({})
    result = evaluate_expression(tokens, defines)
    assert result == 1


def test_logical_not_false():
    tokens = make_tokens(["!", "1"])
    defines = Defines({})
    result = evaluate_expression(tokens, defines)
    assert result == 0


def test_equal():
    tokens = make_tokens(["5", "==", "5"])
    defines = Defines({})
    result = evaluate_expression(tokens, defines)
    assert result == 1


def test_not_equal():
    tokens = make_tokens(["5", "!=", "3"])
    defines = Defines({})
    result = evaluate_expression(tokens, defines)
    assert result == 1


def test_less_than():
    tokens = make_tokens(["3", "<", "5"])
    defines = Defines({})
    result = evaluate_expression(tokens, defines)
    assert result == 1


def test_greater_than():
    tokens = make_tokens(["5", ">", "3"])
    defines = Defines({})
    result = evaluate_expression(tokens, defines)
    assert result == 1


def test_less_than_or_equal():
    tokens = make_tokens(["3", "<=", "5"])
    defines = Defines({})
    result = evaluate_expression(tokens, defines)
    assert result == 1


def test_greater_than_or_equal():
    tokens = make_tokens(["5", ">=", "5"])
    defines = Defines({})
    result = evaluate_expression(tokens, defines)
    assert result == 1


def test_bitwise_and():
    tokens = make_tokens(["5", "&", "3"])
    defines = Defines({})
    result = evaluate_expression(tokens, defines)
    assert result == 1


def test_bitwise_or():
    tokens = make_tokens(["4", "|", "2"])
    defines = Defines({})
    result = evaluate_expression(tokens, defines)
    assert result == 6


def test_bitwise_xor():
    tokens = make_tokens(["5", "^", "3"])
    defines = Defines({})
    result = evaluate_expression(tokens, defines)
    assert result == 6


def test_unary_minus():
    tokens = make_tokens(["-", "5"])
    defines = Defines({})
    result = evaluate_expression(tokens, defines)
    assert result == -5


def test_unary_plus():
    tokens = make_tokens(["+", "5"])
    defines = Defines({})
    result = evaluate_expression(tokens, defines)
    assert result == 5


def test_defined_true():
    tokens = make_tokens(["defined", "(", "FOO", ")"])
    defines = Defines({"FOO": []})
    result = evaluate_expression(tokens, defines)
    assert result == 1


def test_defined_false():
    tokens = make_tokens(["defined", "(", "FOO", ")"])
    defines = Defines({})
    result = evaluate_expression(tokens, defines)
    assert result == 0


def test_defined_without_parens():
    tokens = make_tokens(["defined", "FOO"])
    defines = Defines({"FOO": []})
    result = evaluate_expression(tokens, defines)
    assert result == 1


def test_defined_without_parens_false():
    tokens = make_tokens(["defined", "BAR"])
    defines = Defines({})
    result = evaluate_expression(tokens, defines)
    assert result == 0


def test_complex_expression_with_defined():
    tokens = make_tokens(
        ["defined", "(", "FOO", ")", "&&", "(", "1", "+", "2", ")", ">", "2"]
    )
    defines = Defines({"FOO": []})
    result = evaluate_expression(tokens, defines)
    assert result == 1


def test_undefined_identifier_evaluates_to_zero():
    tokens = make_tokens(["UNDEFINED"])
    defines = Defines({})
    result = evaluate_expression(tokens, defines)
    assert result == 0


def test_empty_expression():
    tokens = []
    defines = Defines({})
    result = evaluate_expression(tokens, defines)
    assert result == 0


def test_division_by_zero():
    tokens = make_tokens(["1", "/", "0"])
    defines = Defines({})
    with pytest.raises(ZeroDivisionError):
        evaluate_expression(tokens, defines)


def test_modulo_by_zero():
    tokens = make_tokens(["1", "%", "0"])
    defines = Defines({})
    with pytest.raises(ZeroDivisionError):
        evaluate_expression(tokens, defines)


def test_missing_closing_paren():
    tokens = make_tokens(["(", "1", "+", "2"])
    defines = Defines({})
    with pytest.raises(SyntaxError):
        evaluate_expression(tokens, defines)


def test_missing_closing_paren_in_defined():
    tokens = make_tokens(["defined", "(", "FOO"])
    defines = Defines({})
    with pytest.raises(SyntaxError):
        evaluate_expression(tokens, defines)
