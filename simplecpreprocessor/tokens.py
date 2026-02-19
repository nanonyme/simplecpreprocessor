import re
import enum

DEFAULT_LINE_ENDING = "\n"
COMMENT_START = ("/*", "//")
LINE_ENDINGS = ("\r\n", "\n")


class TokenType(enum.Enum):
    IDENTIFIER = enum.auto()
    STRING = enum.auto()
    CHAR = enum.auto()
    COMMENT_START = enum.auto()
    COMMENT_END = enum.auto()
    NEWLINE = enum.auto()
    WHITESPACE = enum.auto()
    SYMBOL = enum.auto()


class Token:
    __slots__ = ["line_no", "value", "type", "whitespace", "chunk_mark"]

    def __init__(self, line_no, value, type_, whitespace):
        self.line_no = line_no
        self.value = value
        self.type = type_
        self.whitespace = whitespace
        self.chunk_mark = False

    @classmethod
    def from_string(cls, line_no, value, type_):
        text = value if value is not None else ""
        return cls(line_no, text, type_, not text.strip())

    @classmethod
    def from_constant(cls, line_no, value, type_):
        return cls(line_no, value, type_, False)

    def __repr__(self):
        return (
            f"Line {self.line_no}, {self.type.name}, value {self.value!r}"
        )  # pragma: no cover


def is_string(value: Token):
    """
    Return True if the given token value is a C/C++ string literal.
    Accepts either a Token or a raw string.
    """
    return value.type is TokenType.STRING


class TokenExpander:
    def __init__(self, defines):
        self.defines = defines
        self.seen = set()

    def expand_tokens(self, tokens):
        # Convert to list to allow lookahead
        token_list = list(tokens)
        i = 0
        while i < len(token_list):
            token = token_list[i]
            if token.value in self.seen:
                yield token
                i += 1
            else:
                resolved = self.defines.get(token.value, token)
                if resolved is token:
                    yield token
                    i += 1
                else:
                    # Import FunctionLikeMacro here to avoid circular import
                    from .core import FunctionLikeMacro
                    if isinstance(resolved, FunctionLikeMacro):
                        # Look ahead for '('
                        j = i + 1
                        # Skip whitespace
                        while j < len(token_list):
                            if not token_list[j].whitespace:
                                break
                            j += 1

                        if j < len(token_list) and token_list[j].value == "(":
                            # Extract arguments
                            args, end_pos = self._extract_args(
                                token_list, j + 1
                            )
                            if args is not None:
                                # Expand the macro
                                self.seen.add(token.value)
                                expanded = self._expand_function_macro(
                                    resolved, args
                                )
                                yield from self.expand_tokens(expanded)
                                self.seen.remove(token.value)
                                i = end_pos + 1
                                continue
                        # No '(' found, don't expand
                        yield token
                        i += 1
                    else:
                        # Object-like macro
                        self.seen.add(token.value)
                        yield from self.expand_tokens(resolved)
                        self.seen.remove(token.value)
                        i += 1

    def _extract_args(self, tokens, start):
        """Extract arguments from a function-like macro call.

        Returns (args, end_pos) where args is a list of token lists,
        or (None, None) if parsing fails.
        """
        args = []
        current_arg = []
        paren_depth = 0
        i = start

        while i < len(tokens):
            token = tokens[i]
            if token.value == "(":
                paren_depth += 1
                current_arg.append(token)
            elif token.value == ")":
                if paren_depth == 0:
                    # End of argument list
                    # Add last argument (even if empty)
                    if current_arg or not args:
                        args.append(current_arg)
                    return args, i
                else:
                    paren_depth -= 1
                    current_arg.append(token)
            elif token.value == "," and paren_depth == 0:
                # Argument separator
                args.append(current_arg)
                current_arg = []
            else:
                current_arg.append(token)
            i += 1

        # No closing ')' found
        return None, None

    def _expand_function_macro(self, macro, args):
        """Expand a function-like macro with given arguments.

        Returns a list of tokens.
        """
        # Strip leading/trailing whitespace from each arg
        clean_args = []
        for arg in args:
            # Remove leading whitespace
            start = 0
            while start < len(arg) and arg[start].whitespace:
                start += 1
            # Remove trailing whitespace
            end = len(arg)
            while end > start and arg[end-1].whitespace:
                end -= 1
            clean_args.append(arg[start:end])

        # Expand arguments first (recursive expansion)
        # Create a fresh expander to avoid recursion guard conflicts
        expanded_args = []
        for arg in clean_args:
            expander = TokenExpander(self.defines)
            expanded_arg = list(expander.expand_tokens(arg))
            expanded_args.append(expanded_arg)

        # Build parameter -> argument mapping
        param_map = {}
        for i, param in enumerate(macro.params):
            if i < len(expanded_args):
                param_map[param] = expanded_args[i]
            else:
                param_map[param] = []  # Missing argument

        # Substitute parameters in body
        result = []
        for token in macro.body:
            if token.value in param_map:
                # Replace with argument
                result.extend(param_map[token.value])
            else:
                result.append(token)

        return result


class Tokenizer:
    NO_COMMENT = Token.from_constant(None, None, TokenType.WHITESPACE)

    def __init__(self, f_obj, line_ending):
        self.source = enumerate(f_obj)
        self.line_ending = line_ending
        self.line_no = None
        self._scanner = re.Scanner([
            (
                r"\r\n|\n",
                self._make_cb(TokenType.NEWLINE, normalize_newline=True)
            ),
            (r"/\*", self._make_cb(TokenType.COMMENT_START)),
            (r"//", self._make_cb(TokenType.COMMENT_START)),
            (r"\*/", self._make_cb(TokenType.COMMENT_END)),
            (
                r'(?:u8|u|U|L)?"([^"\\]|\\.)*"',
                self._make_cb(TokenType.STRING)
            ),
            (r"'\w'", self._make_cb(TokenType.CHAR)),
            (r"\b\w+\b", self._make_cb(TokenType.IDENTIFIER)),
            (r"[ \t]+", self._make_cb(TokenType.WHITESPACE)),
            (r"\W", self._make_cb(TokenType.SYMBOL)),
        ])

    def _make_cb(self, type_, normalize_newline=False):
        def _cb(s, t):
            val = self.line_ending if normalize_newline else t
            return Token.from_string(self.line_no, val, type_)
        return _cb

    def _scan_line(self, line_no, line):
        self.line_no = line_no
        tokens, remainder = self._scanner.scan(line)
        if remainder:  # pragma: no cover
            # Defensive: scanner patterns should match all input
            raise SyntaxError(
                f"Unrecognized input: {remainder!r}"
            )
        return iter(tokens)

    def __iter__(self):
        comment = self.NO_COMMENT
        token = None
        line_no = 0

        for line_no, line in self.source:
            tokens = self._scan_line(line_no, line)
            try:
                token = next(tokens)
            except StopIteration:  # pragma: no cover
                # Defensive: scanner always produces at least NEWLINE
                continue  # skip empty lines

            lookahead = None
            for lookahead in tokens:
                if (
                    token.value != "\\"
                    and lookahead.type is TokenType.NEWLINE
                ):
                    lookahead.chunk_mark = True
                if (
                    token.type is TokenType.COMMENT_END
                    and comment.value == "/*"
                ):
                    comment = self.NO_COMMENT
                elif comment is not self.NO_COMMENT:
                    pass
                else:
                    if token.type is TokenType.COMMENT_START:
                        comment = token
                    else:
                        if token.whitespace:
                            if lookahead.type is TokenType.COMMENT_START:
                                pass
                            elif lookahead.value == "#":
                                pass
                            else:
                                yield token
                        else:
                            yield token
                token = lookahead

            if comment.value == "//" and token.value != "\\":
                comment = self.NO_COMMENT
            if comment is self.NO_COMMENT:
                if lookahead is None:
                    token.chunk_mark = True
                yield token

        if token is None or not token.chunk_mark:
            token = Token.from_string(
                line_no, self.line_ending, TokenType.NEWLINE
            )
            token.chunk_mark = True
            yield token

    def read_chunks(self):
        chunk = []
        for token in self:
            chunk.append(token)
            if token.chunk_mark:
                yield chunk
                chunk = []
