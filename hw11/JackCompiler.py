"""Nand2Tetris Jack compiler (chapters 10, 11, 12): .jack -> .vm.

The compiler is split into the same four pieces used in the course:

* ``tokenize``: a Jack tokenizer that removes both comment styles and emits
  the five token kinds of the language.
* ``SymbolTable``: class-level (static/field) and subroutine-level
  (argument/var) scopes with VM segment mapping.
* ``VMWriter``: emits the nine VM commands consumed by ``hw10/VMTranslator``.
* ``CompilationEngine``: a recursive-descent parser that walks the Jack
  grammar and emits VM code directly (no XML intermediate file).

Output follows the official compiler conventions: methods receive ``this``
as argument 0, constructors call ``Memory.alloc``, ``do`` discards the return
value into ``temp 0``, and control-flow labels are numbered per subroutine.

Usage::

    python JackCompiler.py Foo.jack [Foo.vm]
    python JackCompiler.py DIRECTORY [OUTPUT_DIR]
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence

KEYWORDS = frozenset(
    (
        "class", "constructor", "function", "method", "field", "static", "var",
        "int", "char", "boolean", "void", "true", "false", "null", "this",
        "let", "do", "if", "else", "while", "return",
    )
)
SYMBOLS = frozenset("{}()[].,;+-*/&|<>=~")
PRIMITIVE_TYPES = frozenset(("int", "char", "boolean"))
BINARY_OPERATORS = frozenset("+-*/&|<>=")
ARITHMETIC_OPS = {"+": "add", "-": "sub", "&": "and", "|": "or", "<": "lt", ">": "gt", "=": "eq"}
STATEMENTS = frozenset(("let", "if", "while", "do", "return"))
MAX_INTEGER = 32767


class JackError(Exception):
    """Raised for malformed Jack source or an undefined identifier."""


@dataclass(frozen=True)
class Token:
    kind: str
    value: str
    line: int

    def __str__(self) -> str:
        return self.value


def _is_digit(char: str) -> bool:
    return "0" <= char <= "9"


def _is_letter(char: str) -> bool:
    return "a" <= char <= "z" or "A" <= char <= "Z" or char == "_"


def _is_identifier_char(char: str) -> bool:
    return _is_letter(char) or _is_digit(char)


def tokenize(source: str) -> List[Token]:
    """Convert Jack source into keyword/symbol/constant/identifier tokens."""
    tokens: List[Token] = []
    index = 0
    line = 1
    length = len(source)

    while index < length:
        char = source[index]

        if char == "\n":
            line += 1
            index += 1
        elif char.isspace():
            index += 1
        elif source.startswith("//", index):
            while index < length and source[index] != "\n":
                index += 1
        elif source.startswith("/*", index):
            start_line = line
            index += 2
            while index < length and not source.startswith("*/", index):
                if source[index] == "\n":
                    line += 1
                index += 1
            if index >= length:
                raise JackError(f"Line {start_line}: unterminated block comment")
            index += 2
        elif char == '"':
            start_line = line
            index += 1
            value = []
            while index < length and source[index] != '"':
                if source[index] == "\n":
                    raise JackError(f"Line {start_line}: unterminated string constant")
                value.append(source[index])
                index += 1
            if index >= length:
                raise JackError(f"Line {start_line}: unterminated string constant")
            index += 1
            tokens.append(Token("stringConstant", "".join(value), start_line))
        elif _is_digit(char):
            start = index
            while index < length and _is_digit(source[index]):
                index += 1
            value = source[start:index]
            if int(value) > MAX_INTEGER:
                raise JackError(f"Line {line}: integer constant out of range: {value}")
            tokens.append(Token("integerConstant", value, line))
        elif _is_letter(char):
            start = index
            while index < length and _is_identifier_char(source[index]):
                index += 1
            word = source[start:index]
            kind = "keyword" if word in KEYWORDS else "identifier"
            tokens.append(Token(kind, word, line))
        elif char in SYMBOLS:
            tokens.append(Token("symbol", char, line))
            index += 1
        else:
            raise JackError(f"Line {line}: unexpected character {char!r}")

    return tokens


class SymbolTable:
    """Jack scopes, with the VM segment used by each symbol kind."""

    KINDS = ("static", "field", "arg", "var")
    SEGMENTS = {"static": "static", "field": "this", "arg": "argument", "var": "local"}

    def __init__(self) -> None:
        self._tables = {kind: {} for kind in self.KINDS}

    def reset_subroutine(self) -> None:
        self._tables["arg"] = {}
        self._tables["var"] = {}

    def define(self, name: str, type_name: str, kind: str) -> None:
        if kind not in self.KINDS:
            raise JackError(f"unknown symbol kind {kind!r}")
        table = self._tables[kind]
        if name in table:
            raise JackError(f"{kind} symbol {name!r} is already defined")
        table[name] = (type_name, len(table))

    def count(self, kind: str) -> int:
        return len(self._tables[kind])

    def kind_of(self, name: str) -> str:
        for kind in self.KINDS:
            if name in self._tables[kind]:
                return kind
        return ""

    def type_of(self, name: str) -> str:
        kind = self.kind_of(name)
        if not kind:
            raise JackError(f"undefined identifier {name!r}")
        return self._tables[kind][name][0]

    def index_of(self, name: str) -> int:
        kind = self.kind_of(name)
        if not kind:
            raise JackError(f"undefined identifier {name!r}")
        return self._tables[kind][name][1]

    def segment_of(self, name: str) -> str:
        kind = self.kind_of(name)
        if not kind:
            raise JackError(f"undefined identifier {name!r}")
        return self.SEGMENTS[kind]


class VMWriter:
    """Collect VM commands as one command per line."""

    def __init__(self) -> None:
        self.lines: List[str] = []

    def write_push(self, segment: str, index: int) -> None:
        self.lines.append(f"push {segment} {index}")

    def write_pop(self, segment: str, index: int) -> None:
        self.lines.append(f"pop {segment} {index}")

    def write_arithmetic(self, command: str) -> None:
        self.lines.append(command)

    def write_call(self, name: str, num_args: int) -> None:
        self.lines.append(f"call {name} {num_args}")

    def write_label(self, label: str) -> None:
        self.lines.append(f"label {label}")

    def write_goto(self, label: str) -> None:
        self.lines.append(f"goto {label}")

    def write_if(self, label: str) -> None:
        self.lines.append(f"if-goto {label}")

    def write_return(self) -> None:
        self.lines.append("return")

    def write_function(self, name: str, num_locals: int) -> None:
        self.lines.append(f"function {name} {num_locals}")

    def __str__(self) -> str:
        return "\n".join(self.lines) + ("\n" if self.lines else "")


class CompilationEngine:
    """Recursive-descent compiler producing VM code from a Jack token list."""

    def __init__(self, tokens: Sequence[Token], writer: Optional[VMWriter] = None):
        self.tokens = list(tokens)
        self.writer = writer if writer is not None else VMWriter()
        self.symbol_table = SymbolTable()
        self.class_name = ""
        self.pos = 0
        self.if_count = 0
        self.while_count = 0
        self.has_return = False

    def compile_class(self) -> None:
        self._expect("class")
        self.class_name = self._expect_identifier().value
        self._expect("{")
        while self._at("static") or self._at("field"):
            self._compile_class_var_dec()
        while self._at("constructor") or self._at("function") or self._at("method"):
            self._compile_subroutine()
        self._expect("}")
        if self._peek() is not None:
            token = self._current()
            self._error(f"unexpected token {str(token)!r} after class", token)

    def _compile_class_var_dec(self) -> None:
        kind = self._current().value
        self.pos += 1
        type_name = self._expect_type()
        while True:
            name = self._expect_identifier().value
            self.symbol_table.define(name, type_name, kind)
            if not self._accept(","):
                break
        self._expect(";")

    def _compile_subroutine(self) -> None:
        kind = self._current().value
        self.pos += 1
        self._expect_type(allow_void=True)
        name = self._expect_identifier().value
        self._expect("(")

        self.symbol_table.reset_subroutine()
        if kind == "method":
            self.symbol_table.define("this", self.class_name, "arg")
        self._compile_parameter_list()
        self._expect(")")
        self._expect("{")

        while self._at("var"):
            self._compile_var_dec()

        self.writer.write_function(
            f"{self.class_name}.{name}", self.symbol_table.count("var")
        )
        if kind == "constructor":
            self.writer.write_push("constant", self.symbol_table.count("field"))
            self.writer.write_call("Memory.alloc", 1)
            self.writer.write_pop("pointer", 0)
        elif kind == "method":
            self.writer.write_push("argument", 0)
            self.writer.write_pop("pointer", 0)

        self.if_count = 0
        self.while_count = 0
        self.has_return = False
        self._compile_statements()
        self._expect("}")
        if not self.has_return:
            self.writer.write_push("constant", 0)
            self.writer.write_return()

    def _compile_parameter_list(self) -> None:
        if self._at(")"):
            return
        while True:
            type_name = self._expect_type()
            name = self._expect_identifier().value
            self.symbol_table.define(name, type_name, "arg")
            if not self._accept(","):
                break

    def _compile_var_dec(self) -> None:
        self._expect("var")
        type_name = self._expect_type()
        while True:
            name = self._expect_identifier().value
            self.symbol_table.define(name, type_name, "var")
            if not self._accept(","):
                break
        self._expect(";")

    def _compile_statements(self) -> None:
        while self._peek() is not None and self._peek().value in STATEMENTS:
            keyword = self._current().value
            if keyword == "let":
                self._compile_let()
            elif keyword == "if":
                self._compile_if()
            elif keyword == "while":
                self._compile_while()
            elif keyword == "do":
                self._compile_do()
            else:
                self._compile_return()

    def _compile_braced_statements(self) -> None:
        self._expect("{")
        self._compile_statements()
        self._expect("}")

    def _compile_let(self) -> None:
        self._expect("let")
        name = self._expect_identifier().value
        segment = self.symbol_table.segment_of(name)
        index = self.symbol_table.index_of(name)
        is_array = self._accept("[")
        if is_array:
            self._compile_expression()
            self.writer.write_push(segment, index)
            self._expect("]")
            self.writer.write_arithmetic("add")
        self._expect("=")
        self._compile_expression()
        self._expect(";")
        if is_array:
            self.writer.write_pop("temp", 0)
            self.writer.write_pop("pointer", 1)
            self.writer.write_push("temp", 0)
            self.writer.write_pop("that", 0)
        else:
            self.writer.write_pop(segment, index)

    def _compile_if(self) -> None:
        self._expect("if")
        self._expect("(")
        self._compile_expression()
        self._expect(")")
        number = self.if_count
        self.if_count += 1
        self.writer.write_if(f"IF_TRUE{number}")
        self.writer.write_goto(f"IF_FALSE{number}")
        self.writer.write_label(f"IF_TRUE{number}")
        self._compile_braced_statements()
        if self._accept("else"):
            self.writer.write_goto(f"IF_END{number}")
            self.writer.write_label(f"IF_FALSE{number}")
            self._compile_braced_statements()
            self.writer.write_label(f"IF_END{number}")
        else:
            self.writer.write_label(f"IF_FALSE{number}")

    def _compile_while(self) -> None:
        number = self.while_count
        self.while_count += 1
        self._expect("while")
        self.writer.write_label(f"WHILE_EXP{number}")
        self._expect("(")
        self._compile_expression()
        self._expect(")")
        self.writer.write_arithmetic("not")
        self.writer.write_if(f"WHILE_END{number}")
        self._compile_braced_statements()
        self.writer.write_goto(f"WHILE_EXP{number}")
        self.writer.write_label(f"WHILE_END{number}")

    def _compile_do(self) -> None:
        self._expect("do")
        self._compile_subroutine_call()
        self._expect(";")
        self.writer.write_pop("temp", 0)

    def _compile_return(self) -> None:
        self._expect("return")
        if self._at(";"):
            self.writer.write_push("constant", 0)
        else:
            self._compile_expression()
        self._expect(";")
        self.writer.write_return()
        self.has_return = True

    def _compile_expression(self) -> None:
        self._compile_term()
        while self._peek() is not None and self._peek().value in BINARY_OPERATORS:
            operator = self._current().value
            self.pos += 1
            self._compile_term()
            if operator == "*":
                self.writer.write_call("Math.multiply", 2)
            elif operator == "/":
                self.writer.write_call("Math.divide", 2)
            else:
                self.writer.write_arithmetic(ARITHMETIC_OPS[operator])

    def _compile_term(self) -> None:
        token = self._current()
        if token.kind == "integerConstant":
            self.pos += 1
            self.writer.write_push("constant", int(token.value))
        elif token.kind == "stringConstant":
            self.pos += 1
            self.writer.write_push("constant", len(token.value))
            self.writer.write_call("String.new", 1)
            for char in token.value:
                self.writer.write_push("constant", ord(char))
                self.writer.write_call("String.appendChar", 2)
        elif token.kind == "keyword" and token.value in ("true", "false", "null", "this"):
            self.pos += 1
            if token.value == "true":
                self.writer.write_push("constant", 0)
                self.writer.write_arithmetic("not")
            elif token.value == "this":
                self.writer.write_push("pointer", 0)
            else:
                self.writer.write_push("constant", 0)
        elif token.value == "-":
            self.pos += 1
            self._compile_term()
            self.writer.write_arithmetic("neg")
        elif token.value == "~":
            self.pos += 1
            self._compile_term()
            self.writer.write_arithmetic("not")
        elif token.value == "(":
            self.pos += 1
            self._compile_expression()
            self._expect(")")
        elif token.kind == "identifier":
            following = self._peek(1)
            if following is not None and following.value == "[":
                name = self._expect_identifier().value
                self._expect("[")
                self._compile_expression()
                self._expect("]")
                self.writer.write_push(
                    self.symbol_table.segment_of(name), self.symbol_table.index_of(name)
                )
                self.writer.write_arithmetic("add")
                self.writer.write_pop("pointer", 1)
                self.writer.write_push("that", 0)
            elif following is not None and following.value in ("(", "."):
                self._compile_subroutine_call()
            else:
                name = self._expect_identifier().value
                self.writer.write_push(
                    self.symbol_table.segment_of(name), self.symbol_table.index_of(name)
                )
        else:
            self._error(f"expected a term, found {str(token)!r}", token)

    def _compile_subroutine_call(self) -> None:
        name = self._expect_identifier().value
        if self._accept("("):
            self.writer.write_push("pointer", 0)
            num_args = self._compile_expression_list()
            self._expect(")")
            self.writer.write_call(f"{self.class_name}.{name}", num_args + 1)
            return

        self._expect(".")
        subroutine = self._expect_identifier().value
        kind = self.symbol_table.kind_of(name)
        if kind:
            self.writer.write_push(
                self.symbol_table.SEGMENTS[kind], self.symbol_table.index_of(name)
            )
            class_name = self.symbol_table.type_of(name)
            extra = 1
        else:
            class_name = name
            extra = 0
        self._expect("(")
        num_args = self._compile_expression_list()
        self._expect(")")
        self.writer.write_call(f"{class_name}.{subroutine}", num_args + extra)

    def _compile_expression_list(self) -> int:
        if self._at(")"):
            return 0
        count = 1
        self._compile_expression()
        while self._accept(","):
            self._compile_expression()
            count += 1
        return count

    def _peek(self, offset: int = 0) -> Optional[Token]:
        position = self.pos + offset
        return self.tokens[position] if position < len(self.tokens) else None

    def _current(self) -> Token:
        token = self._peek()
        if token is None:
            raise JackError("unexpected end of file")
        return token

    def _at(self, value: str) -> bool:
        token = self._peek()
        return token is not None and token.value == value

    def _accept(self, value: str) -> bool:
        if not self._at(value):
            return False
        self.pos += 1
        return True

    def _expect(self, value: str) -> Token:
        token = self._current()
        if token.value != value:
            self._error(f"expected {value!r}, found {str(token)!r}", token)
        self.pos += 1
        return token

    def _expect_identifier(self) -> Token:
        token = self._current()
        if token.kind != "identifier":
            self._error(f"expected an identifier, found {str(token)!r}", token)
        self.pos += 1
        return token

    def _expect_type(self, allow_void: bool = False) -> str:
        token = self._current()
        if token.kind == "identifier" or (
            token.kind == "keyword"
            and (token.value in PRIMITIVE_TYPES or (allow_void and token.value == "void"))
        ):
            self.pos += 1
            return token.value
        self._error(f"expected a type, found {str(token)!r}", token)
        raise AssertionError("unreachable")

    @staticmethod
    def _error(message: str, token: Token) -> None:
        raise JackError(f"Line {token.line}: {message}")


def compile_source(source: str) -> str:
    """Compile Jack source text into VM commands."""
    tokens = tokenize(source)
    if not tokens:
        raise JackError("empty Jack source")
    engine = CompilationEngine(tokens)
    engine.compile_class()
    return str(engine.writer)


def compile_file(input_path, output_path=None) -> Path:
    """Compile one ``.jack`` file, defaulting to a sibling ``.vm`` file."""
    path = Path(input_path)
    output = Path(output_path) if output_path is not None else path.with_suffix(".vm")
    output.write_text(compile_source(path.read_text(encoding="utf-8-sig")), encoding="utf-8")
    return output


def compile_path(input_path, output_path=None) -> List[Path]:
    """Compile a ``.jack`` file or every ``.jack`` file in a directory."""
    path = Path(input_path)
    if path.is_dir():
        sources = sorted(path.glob("*.jack"), key=lambda item: item.name)
        if not sources:
            raise JackError(f"no .jack files found in {path}")
        destination = Path(output_path) if output_path is not None else path
        destination.mkdir(parents=True, exist_ok=True)
        return [
            compile_file(source, destination / f"{source.stem}.vm") for source in sources
        ]
    return [compile_file(path, output_path)]


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in ("-h", "--help"):
        print("Usage: python JackCompiler.py INPUT.jack [OUTPUT.vm]")
        print("       python JackCompiler.py DIRECTORY [OUTPUT_DIR]")
        return 0 if args else 2
    if len(args) > 2:
        print("Usage: python JackCompiler.py INPUT.jack [OUTPUT.vm]", file=sys.stderr)
        return 2

    try:
        outputs = compile_path(args[0], args[1] if len(args) == 2 else None)
    except (OSError, JackError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    for output in outputs:
        print(f"Compiled {args[0]} -> {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
