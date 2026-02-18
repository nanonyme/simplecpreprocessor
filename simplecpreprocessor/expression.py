"""
Expression parser for C preprocessor #if and #elif directives.
Uses a Pratt parser for operator precedence parsing.
"""


class ExpressionToken:
    """Token for expression parsing."""
    def __init__(self, type_, value):
        self.type = type_
        self.value = value

    def __repr__(self):
        return f"ExprToken({self.type}, {self.value!r})"


class ExpressionLexer:
    """Lexer for C preprocessor expressions."""

    def __init__(self, tokens):
        """
        Initialize lexer with preprocessor tokens.

        Args:
            tokens: List of Token objects from the preprocessor
        """
        self.tokens = []
        i = 0
        non_ws_tokens = [t for t in tokens if not t.whitespace]

        # Combine multi-character operators
        while i < len(non_ws_tokens):
            token = non_ws_tokens[i]

            # Check for two-character operators
            if i + 1 < len(non_ws_tokens):
                next_token = non_ws_tokens[i + 1]
                combined = token.value + next_token.value
                if combined in ("&&", "||", "==", "!=", "<=", ">="):
                    # Create a combined token
                    from .tokens import Token, TokenType
                    combined_token = Token.from_string(
                        token.line_no, combined, TokenType.SYMBOL
                    )
                    self.tokens.append(combined_token)
                    i += 2
                    continue

            self.tokens.append(token)
            i += 1

        self.pos = 0

    def peek(self):
        """Return current token without advancing."""
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return None

    def consume(self):
        """Consume and return current token."""
        token = self.peek()
        self.pos += 1
        return token

    def at_end(self):
        """Check if at end of tokens."""
        return self.pos >= len(self.tokens)


class ExpressionParser:
    """
    Pratt parser for C preprocessor constant expressions.
    Supports: integers, defined(), logical ops, comparison, arithmetic.
    """

    def __init__(self, tokens, defines):
        """
        Initialize parser.

        Args:
            tokens: List of Token objects from preprocessor
            defines: Defines object to check for macro definitions
        """
        self.lexer = ExpressionLexer(tokens)
        self.defines = defines

    def parse(self):
        """Parse and evaluate the expression, returning an integer."""
        if self.lexer.at_end():
            return 0
        result = self._parse_expr(0)
        if not self.lexer.at_end():
            raise SyntaxError(
                f"Unexpected token: {self.lexer.peek().value}"
            )
        return result

    def _parse_expr(self, min_precedence):
        """Parse expression with precedence climbing."""
        left = self._parse_primary()

        while (token := self.lexer.peek()) is not None:
            op = token.value
            # Stop at closing parenthesis
            if op == ")":
                break

            precedence = self._get_precedence(op)
            if precedence <= 0 or precedence < min_precedence:
                break

            self.lexer.consume()
            right = self._parse_expr(precedence + 1)
            left = self._apply_binary_op(op, left, right)

        return left

    def _parse_primary(self):
        """Parse primary expression (numbers, defined, unary, parens)."""
        token = self.lexer.peek()
        if token is None:
            raise SyntaxError("Unexpected end of expression")

        # Handle parentheses
        if token.value == "(":
            self.lexer.consume()
            result = self._parse_expr(0)
            closing = self.lexer.peek()
            if closing is None or closing.value != ")":
                raise SyntaxError("Missing closing parenthesis")
            self.lexer.consume()
            return result

        # Handle unary operators
        if token.value in ("!", "+", "-"):
            op = token.value
            self.lexer.consume()
            operand = self._parse_primary()
            if op == "!":
                return 0 if operand else 1
            elif op == "-":
                return -operand
            else:  # +
                return operand

        # Handle defined() operator
        if token.value == "defined":
            return self._parse_defined()

        # Handle integer literals
        try:
            value = int(token.value)
            self.lexer.consume()
            return value
        except ValueError:
            # Undefined identifier evaluates to 0
            self.lexer.consume()
            return 0

    def _parse_defined(self):
        """Parse defined(MACRO) or defined MACRO."""
        self.lexer.consume()  # consume 'defined'

        next_token = self.lexer.peek()
        if next_token is None:
            raise SyntaxError("Expected identifier after 'defined'")

        has_parens = next_token.value == "("
        if has_parens:
            self.lexer.consume()
            next_token = self.lexer.peek()
            if next_token is None:
                raise SyntaxError("Expected identifier in defined()")

        macro_name = next_token.value
        self.lexer.consume()

        if has_parens:
            closing = self.lexer.peek()
            if closing is None or closing.value != ")":
                raise SyntaxError("Missing closing paren in defined()")
            self.lexer.consume()

        return 1 if macro_name in self.defines else 0

    def _get_precedence(self, op):
        """Get operator precedence (higher = binds tighter)."""
        precedence_table = {
            "||": 1,
            "&&": 2,
            "|": 3,
            "^": 4,
            "&": 5,
            "==": 6, "!=": 6,
            "<": 7, ">": 7, "<=": 7, ">=": 7,
            "+": 8, "-": 8,
            "*": 9, "/": 9, "%": 9,
        }
        return precedence_table.get(op, 0)

    def _apply_binary_op(self, op, left, right):
        """Apply binary operator."""
        if op == "||":
            return 1 if (left or right) else 0
        elif op == "&&":
            return 1 if (left and right) else 0
        elif op == "|":
            return left | right
        elif op == "^":
            return left ^ right
        elif op == "&":
            return left & right
        elif op == "==":
            return 1 if left == right else 0
        elif op == "!=":
            return 1 if left != right else 0
        elif op == "<":
            return 1 if left < right else 0
        elif op == ">":
            return 1 if left > right else 0
        elif op == "<=":
            return 1 if left <= right else 0
        elif op == ">=":
            return 1 if left >= right else 0
        elif op == "+":
            return left + right
        elif op == "-":
            return left - right
        elif op == "*":
            return left * right
        elif op == "/":
            if right == 0:
                raise ZeroDivisionError("Division by zero")
            return left // right
        elif op == "%":
            if right == 0:
                raise ZeroDivisionError("Modulo by zero")
            return left % right
        else:
            raise SyntaxError(f"Unknown operator: {op}")


def evaluate_expression(tokens, defines):
    """
    Evaluate a C preprocessor constant expression.

    Args:
        tokens: List of Token objects from the preprocessor
        defines: Defines object to check for macro definitions

    Returns:
        Integer result of the expression (non-zero = true, 0 = false)
    """
    parser = ExpressionParser(tokens, defines)
    return parser.parse()
