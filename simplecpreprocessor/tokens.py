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


def is_string(value):
    """
    Return True if the given token value is a C/C++ string literal.
    Accepts either a Token or a raw string.
    """
    if isinstance(value, Token):
        return value.type is TokenType.STRING
    if not isinstance(value, str):
        return False
    # Fallback regex check for raw strings
    return bool(
        re.match(r'^(?:u8|u|U|L)?"([^"\\]|\\.)*"$', value)
    )


class TokenExpander:
    def __init__(self, defines):
        self.defines = defines
        self.seen = set()

    def expand_tokens(self, tokens):
        for token in tokens:
            if token.value in self.seen:
                yield token
            else:
                resolved = self.defines.get(token.value, token)
                if resolved is token:
                    yield token
                else:
                    self.seen.add(token.value)
                    yield from self.expand_tokens(resolved)
                    self.seen.remove(token.value)


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
        if remainder:
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
            except StopIteration:
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
