import enum

from . import filesystem, tokens, platform, exceptions, expression
from .tokens import TokenType, is_string


class Tag(enum.Enum):
    PRAGMA_ONCE = "#pragma_once"
    IFDEF = "#ifdef"
    IFNDEF = "#ifndef"
    IF = "#if"
    ELSE = "#else"
    ELIF = "#elif"


def constants_to_token_constants(constants):
    return {
        key: [tokens.Token.from_string(None, value, TokenType.IDENTIFIER)]
        for key, value in constants.items()
    }


TOKEN_CONSTANTS = constants_to_token_constants(platform.PLATFORM_CONSTANTS)


class Defines:
    def __init__(self, base):
        self.defines = base.copy()

    def get(self, key, default=None):
        return self.defines.get(key, default)

    def __delitem__(self, key):
        self.defines.pop(key, None)

    def __setitem__(self, key, value):
        self.defines[key] = value

    def __contains__(self, key):
        return key in self.defines


class Preprocessor:

    def __init__(self, line_ending=tokens.DEFAULT_LINE_ENDING,
                 include_paths=(), header_handler=None,
                 platform_constants=TOKEN_CONSTANTS,
                 ignore_headers=(), fold_strings_to_null=False):
        self.ignore_headers = ignore_headers
        self.include_once = {}
        self.defines = Defines(platform_constants)
        self.constraints = []
        self.ignore = False
        self.line_ending = line_ending
        self.last_constraint = None
        self.header_stack = []
        self.fold_strings_to_null = fold_strings_to_null
        self.token_expander = tokens.TokenExpander(self.defines)
        if header_handler is None:
            self.headers = filesystem.HeaderHandler(include_paths)
        else:
            self.headers = header_handler
            self.headers.add_include_paths(include_paths)

    def process_define(self, **kwargs):
        if self.ignore:
            return
        chunk = kwargs["chunk"]
        for i, tokenized in enumerate(chunk):
            if not tokenized.whitespace:
                define_name = tokenized.value
                break
        self.defines[define_name] = chunk[i+2:-1]

    def process_endif(self, **kwargs):
        line_no = kwargs["line_no"]
        if not self.constraints:
            fmt = "Unexpected #endif on line %s"
            raise exceptions.ParseError(fmt % line_no)
        (constraint_type, constraint, ignore,
         original_line_no) = self.constraints.pop()
        if ignore:
            self.ignore = False
        self.last_constraint = constraint, constraint_type, original_line_no

    def process_else(self, **kwargs):
        line_no = kwargs["line_no"]
        if not self.constraints:
            fmt = "Unexpected #else on line %s"
            raise exceptions.ParseError(fmt % line_no)
        constraint_type, constraint, ignore, _ = self.constraints.pop()

        # For IF/ELIF, check if any branch was taken
        if constraint_type in (Tag.IF, Tag.ELIF):
            branch_was_taken = constraint
            if branch_was_taken:
                # A branch was already taken, don't take else
                ignore = True
                if not self.ignore:
                    self.ignore = True
            else:
                # No branch was taken, take the else
                ignore = False
                if self.ignore:
                    self.ignore = False
        else:
            # Original logic for IFDEF/IFNDEF
            if self.ignore and ignore:
                ignore = False
                self.ignore = False
            elif not self.ignore and not ignore:
                ignore = True
                self.ignore = True

        self.constraints.append((Tag.ELSE, constraint, ignore, line_no))

    def process_ifdef(self, **kwargs):
        chunk = kwargs["chunk"]
        line_no = kwargs["line_no"]
        for token in chunk:
            if not token.whitespace:
                condition = token.value
                break
        if not self.ignore and condition not in self.defines:
            self.ignore = True
            self.constraints.append((Tag.IFDEF, condition, True, line_no))
        else:
            self.constraints.append((Tag.IFDEF, condition, False, line_no))

    def process_pragma(self, **kwargs):
        chunk = kwargs["chunk"]
        line_no = kwargs["line_no"]
        pragma = None
        for token in chunk:
            if not token.whitespace:
                method_name = "process_pragma_%s" % token.value
                pragma = getattr(self, method_name, None)
                break
        if pragma is None:
            s = (
                "Unsupported pragma %s on line %s"
                % (token.value, line_no)
            )
            raise exceptions.ParseError(s)
        else:
            ret = pragma(chunk=chunk, line_no=line_no)
            if ret is not None:
                yield from ret

    def process_pragma_once(self, **_):
        self.include_once[self.current_name()] = Tag.PRAGMA_ONCE

    def process_pragma_pack(self, chunk, **_):
        yield "#pragma"
        for token in chunk:
            yield token.value

    def current_name(self):
        return self.header_stack[-1].name

    def process_ifndef(self, **kwargs):
        chunk = kwargs["chunk"]
        line_no = kwargs["line_no"]
        for token in chunk:
            if not token.whitespace:
                condition = token.value
                break
        if not self.ignore and condition in self.defines:
            self.ignore = True
            self.constraints.append((Tag.IFNDEF, condition, True, line_no))
        else:
            self.constraints.append((Tag.IFNDEF, condition, False, line_no))

    def process_undef(self, **kwargs):
        chunk = kwargs["chunk"]
        for token in chunk:
            if not token.whitespace:
                undefine = token.value
                del self.defines[undefine]
                return

    def process_if(self, **kwargs):
        chunk = kwargs["chunk"]
        line_no = kwargs["line_no"]
        try:
            result = expression.evaluate_expression(chunk, self.defines)
            condition_met = result != 0
        except (SyntaxError, ZeroDivisionError) as e:
            fmt = "Error evaluating #if on line %s: %s"
            raise exceptions.ParseError(fmt % (line_no, str(e)))

        # Store whether this branch was taken in the constraint field
        branch_taken = condition_met
        if not self.ignore and not condition_met:
            self.ignore = True
            self.constraints.append((Tag.IF, branch_taken, True, line_no))
        else:
            self.constraints.append((Tag.IF, branch_taken, False, line_no))

    def process_elif(self, **kwargs):
        chunk = kwargs["chunk"]
        line_no = kwargs["line_no"]
        if not self.constraints:
            fmt = "Unexpected #elif on line %s"
            raise exceptions.ParseError(fmt % line_no)

        constraint_type, constraint, ignore, original_line_no = (
            self.constraints.pop()
        )

        if constraint_type == Tag.ELSE:
            fmt = "#elif after #else on line %s"
            raise exceptions.ParseError(fmt % line_no)

        # Check if any previous branch was taken
        # For IF/ELIF, constraint stores whether that branch was taken
        previous_branch_taken = constraint if constraint_type in (
            Tag.IF, Tag.ELIF
        ) else (not ignore)

        if previous_branch_taken:
            # A previous branch was taken, so ignore this elif
            branch_taken = True  # Mark that a branch was taken
            ignore = True
            if not self.ignore:
                self.ignore = True
        else:
            # No previous branch taken, evaluate this elif's condition
            try:
                result = expression.evaluate_expression(chunk, self.defines)
                condition_met = result != 0
            except (SyntaxError, ZeroDivisionError) as e:
                fmt = "Error evaluating #elif on line %s: %s"
                raise exceptions.ParseError(fmt % (line_no, str(e)))

            if condition_met:
                # This branch's condition is met
                branch_taken = True
                ignore = False
                if self.ignore:
                    self.ignore = False
            else:
                # This branch's condition is not met
                branch_taken = False
                ignore = True
                # self.ignore should already be True

        self.constraints.append((Tag.ELIF, branch_taken, ignore, line_no))

    def process_source_chunks(self, chunk):
        if not self.ignore:
            for token in self.token_expander.expand_tokens(chunk):
                if self.fold_strings_to_null and is_string(token):
                    yield "NULL"
                else:
                    yield token.value

    def skip_file(self, name):
        item = self.include_once.get(name)
        if item is Tag.PRAGMA_ONCE:
            return True
        elif item is None:
            return False
        else:
            constraint, constraint_type = item
            if constraint_type is Tag.IFDEF:
                return constraint not in self.defines
            else:
                assert constraint_type is Tag.IFNDEF
                return constraint in self.defines

    def _read_header(self, header, error, anchor_file=None):
        if header not in self.ignore_headers:
            f = self.headers.open_header(header, self.skip_file, anchor_file)
            if f is None:
                raise error
            elif f is not filesystem.SKIP_FILE:
                with f:
                    for chunk in self.preprocess(f):
                        yield chunk

    def process_include(self, **kwargs):
        chunk = kwargs["chunk"]
        line_no = kwargs["line_no"]

        # Find first non-whitespace token after #include
        it = iter(chunk)
        first = None
        for tok in it:
            if not tok.whitespace:
                first = tok
                break

        if first is None:
            fmt = (
                "Invalid include on line %s, got empty include name"
                % line_no
            )
            raise exceptions.ParseError(fmt)

        # Case 1: quoted include
        if first.type is TokenType.STRING:
            item = first.value
            if (
                item.startswith(("u8\"", "u\"", "U\"", "L\""))
                and item.endswith("\"")
            ):
                header = item[item.index("\"")+1:-1]
            elif item.startswith('"') and item.endswith('"'):
                header = item.strip('"')
            else:
                fmt = (
                    "Invalid include on line %s, got %r for include name"
                    % (line_no, item)
                )
                raise exceptions.ParseError(fmt)
            s = (
                "Line %s includes a file %s that can't be found"
                % (line_no, item)
            )
            error = exceptions.ParseError(s)
            return self._read_header(header, error, self.current_name())

        # Case 2: angle-bracket include
        if first.value == "<":
            parts = []
            for tok in it:
                if tok.value == ">":
                    item = "<" + "".join(parts) + ">"
                    header = "".join(parts)
                    s = (
                        "Line %s includes a file %s that can't be found"
                        % (line_no, item)
                    )
                    error = exceptions.ParseError(s)
                    return self._read_header(header, error)
                if tok.type is TokenType.NEWLINE:
                    fmt = (
                        "Invalid include on line %s, missing '>'"
                        % line_no
                    )
                    raise exceptions.ParseError(fmt)
                parts.append(tok.value)
            fmt = (
                "Invalid include on line %s, missing '>'"
                % line_no
            )
            raise exceptions.ParseError(fmt)

        fmt = (
            "Invalid include on line %s, got %r for include name"
            % (line_no, first.value)
        )
        raise exceptions.ParseError(fmt)

    def check_fullfile_guard(self):
        if self.last_constraint is None:
            return
        constraint, constraint_type, begin = self.last_constraint
        if begin != 0:
            return
        self.include_once[self.current_name()] = constraint, constraint_type

    def preprocess(self, f_object, depth=0):
        self.header_stack.append(f_object)
        tokenizer = tokens.Tokenizer(f_object, self.line_ending)
        for chunk in tokenizer.read_chunks():
            self.last_constraint = None
            if chunk[0].value == "#":
                line_no = chunk[0].line_no
                macro_name = chunk[1].value
                macro_chunk = chunk[2:]
                macro = getattr(
                    self,
                    "process_%s" % macro_name,
                    None
                )
                if macro is None:
                    fmt = (
                        "Line number %s contains unsupported macro %s"
                        % (line_no, macro_name)
                    )
                    raise exceptions.ParseError(fmt)
                ret = macro(line_no=line_no, chunk=macro_chunk)
                if ret is not None:
                    for token in ret:
                        yield token
            else:
                for token in self.process_source_chunks(chunk):
                    yield token
        self.check_fullfile_guard()
        self.header_stack.pop()
        if not self.header_stack and self.constraints:
            constraint_type, name, _, line_no = self.constraints[-1]
            fmt = (
                "{tag} {name} from line {line_no} left open"
                .format(
                    tag=constraint_type.value,
                    name=name,
                    line_no=line_no
                )
            )
            raise exceptions.ParseError(fmt)


def preprocess(f_object, line_ending="\n", include_paths=(),
               header_handler=None,
               extra_constants=(),
               ignore_headers=(), fold_strings_to_null=False):
    """
    This preprocessor yields chunks of text that combined result in lines
    delimited with the given line ending. There is always a final line ending.
    """
    platform_constants = platform.PLATFORM_CONSTANTS.copy()
    platform_constants.update(extra_constants)
    preprocessor = Preprocessor(
        line_ending,
        include_paths,
        header_handler,
        constants_to_token_constants(platform_constants),
        ignore_headers,
        fold_strings_to_null
    )
    return preprocessor.preprocess(f_object)
