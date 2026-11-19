"""Nand2Tetris VM translator: .vm (stack machine) -> Hack assembly.

Supports the complete command set of chapters 7 and 8:

* arithmetic / logical: add sub neg eq gt lt and or not
* memory access: push / pop constant local argument this that temp pointer static
* program flow: label goto if-goto
* functions: function call return
* bootstrap: SP = 256, followed by ``call Sys.init 0`` (multi-file mode)

The generated instruction sequences follow the usual nand2tetris translation
contract (R13 = frame address, R14 = return address), so the output can be fed
directly to ``hw9/Assembler.py``.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple, Union

SYMBOL_PATTERN = re.compile(r"[A-Za-z_.$:][A-Za-z0-9_.$:]*\Z")
DECIMAL_PATTERN = re.compile(r"[0-9]+\Z")

ARITHMETIC_COMMANDS = frozenset(
    ("add", "sub", "neg", "eq", "gt", "lt", "and", "or", "not")
)
COMPARISON_COMMANDS = frozenset(("eq", "gt", "lt"))
FLOW_COMMANDS = frozenset(("label", "goto", "if-goto"))
SEGMENTS = frozenset(
    ("constant", "local", "argument", "this", "that", "temp", "pointer", "static")
)
INDIRECT_SEGMENTS = {
    "local": "LCL",
    "argument": "ARG",
    "this": "THIS",
    "that": "THAT",
}
MAX_INDEX = 0x7FFF

VMFile = Union[str, Path]
VMSource = Union[VMFile, Tuple[VMFile, str]]


class VMError(Exception):
    """Raised for malformed VM source or an unsupported command."""


@dataclass(frozen=True)
class Command:
    """One parsed VM command (``text`` keeps the original line for comments)."""

    line_number: int
    type: str
    text: str
    cmd: str = ""
    arg1: str = ""
    arg2: Optional[int] = None


def parse_line(line_number: int, raw_line: str) -> Optional[Command]:
    """Parse a single source line; return ``None`` for blank / comment lines."""
    line = raw_line.split("//", 1)[0].strip()
    if not line:
        return None

    parts = line.split()
    command, args = parts[0], parts[1:]

    def fail(message: str) -> None:
        raise VMError(f"Line {line_number}: {message}")

    if command in ARITHMETIC_COMMANDS or command == "return":
        if args:
            fail(f"{command} takes no arguments")
        kind = "arithmetic" if command != "return" else "return"
        return Command(line_number, kind, line, command)

    if command in ("push", "pop"):
        if len(args) != 2:
            fail(f"{command} needs a segment and an index")
        segment, index_text = args
        if segment not in SEGMENTS:
            fail(f"unknown segment {segment!r}")
        if not DECIMAL_PATTERN.fullmatch(index_text):
            fail(f"index must be a non-negative integer: {index_text!r}")
        index = int(index_text)
        if command == "pop" and segment == "constant":
            fail("cannot pop into constant")
        if segment == "temp" and not 0 <= index <= 7:
            fail("temp index must be between 0 and 7")
        if segment == "pointer" and not 0 <= index <= 1:
            fail("pointer index must be 0 (THIS) or 1 (THAT)")
        if index > MAX_INDEX:
            fail(f"index out of range: {index}")
        return Command(line_number, command, line, command, segment, index)

    if command in FLOW_COMMANDS:
        if len(args) != 1:
            fail(f"{command} needs exactly one label")
        if not SYMBOL_PATTERN.fullmatch(args[0]):
            fail(f"invalid label {args[0]!r}")
        return Command(line_number, command, line, command, args[0])

    if command in ("function", "call"):
        if len(args) != 2:
            fail(f"{command} needs a function name and a number")
        name, count_text = args
        if not SYMBOL_PATTERN.fullmatch(name):
            fail(f"invalid function name {name!r}")
        if not DECIMAL_PATTERN.fullmatch(count_text):
            fail(f"expected a non-negative integer: {count_text!r}")
        count = int(count_text)
        if count > MAX_INDEX:
            fail(f"number out of range: {count}")
        return Command(line_number, command, line, command, name, count)

    fail(f"unknown command {command!r}")
    raise AssertionError("unreachable")  # pragma: no cover


class Parser:
    """Strip comments / whitespace and validate every VM command."""

    def __init__(self, source: str):
        self.commands = [
            command
            for line_number, raw_line in enumerate(source.splitlines(), 1)
            if (command := parse_line(line_number, raw_line)) is not None
        ]


def base_name(path: VMFile) -> str:
    """Return the symbol-safe file stem used for ``static`` variables."""
    name = Path(str(path).replace("\\", "/")).name
    if name.lower().endswith(".vm"):
        name = name[:-3]
    if not name:
        name = "unknown"
    if not SYMBOL_PATTERN.fullmatch(name):
        name = re.sub(r"[^A-Za-z0-9_.$:]", "_", name)
        if not SYMBOL_PATTERN.fullmatch(name):
            name = "_" + name
    return name


class CodeWriter:
    """Emit Hack assembly for parsed VM commands."""

    def __init__(self):
        self.lines = []
        self.instruction_count = 0
        self.label_count = 0
        self.return_count = 0
        self.file_name = "unknown"
        self.function_name = ""
        self.scoped_labels = False

    def emit(self, *lines: str) -> None:
        self.lines.extend(lines)
        self.instruction_count += sum(
            1
            for line in lines
            if line and not line.startswith("(") and not line.lstrip().startswith("//")
        )

    def set_file_name(self, name: VMFile) -> None:
        self.file_name = base_name(name)

    def set_function_name(self, name: str) -> None:
        self.function_name = name

    def label_name(self, label: str) -> str:
        # Multiple files need per-function scopes: two classes may both define
        # a label named LOOP (the same convention as the standard translator).
        if self.scoped_labels and self.function_name:
            return f"{self.function_name}${label}"
        return label

    def write(self, command: Command) -> None:
        if command.type == "arithmetic":
            self.write_arithmetic(command.cmd)
        elif command.type in ("push", "pop"):
            self.write_push_pop(command.type, command.arg1, command.arg2)
        elif command.type == "label":
            self.write_label(command.arg1)
        elif command.type == "goto":
            self.write_goto(command.arg1)
        elif command.type == "if-goto":
            self.write_if_goto(command.arg1)
        elif command.type == "function":
            self.write_function(command.arg1, command.arg2)
        elif command.type == "call":
            self.write_call(command.arg1, command.arg2)
        elif command.type == "return":
            self.write_return()
        else:  # pragma: no cover - Parser never produces other types
            raise VMError(f"unhandled command type {command.type!r}")

    def write_arithmetic(self, command: str) -> None:
        if command == "add":
            self.emit("@SP", "AM=M-1", "D=M", "A=A-1", "M=D+M")
        elif command == "sub":
            self.emit("@SP", "AM=M-1", "D=M", "A=A-1", "M=M-D")
        elif command == "neg":
            self.emit("@SP", "A=M-1", "M=-M")
        elif command == "and":
            self.emit("@SP", "AM=M-1", "D=M", "A=A-1", "M=D&M")
        elif command == "or":
            self.emit("@SP", "AM=M-1", "D=M", "A=A-1", "M=D|M")
        elif command == "not":
            self.emit("@SP", "A=M-1", "M=!M")
        elif command in COMPARISON_COMMANDS:
            jump = {"eq": "JEQ", "gt": "JGT", "lt": "JLT"}[command]
            number = self.label_count
            self.label_count += 1
            self.emit("@SP", "AM=M-1", "D=M", "A=A-1", "D=M-D")
            self.emit(f"@TRUE_{number}", f"D;{jump}")
            self.emit("@SP", "A=M-1", "M=0")
            self.emit(f"@END_{number}", "0;JMP")
            self.emit(f"(TRUE_{number})", "@SP", "A=M-1", "M=-1")
            self.emit(f"(END_{number})")
        else:  # pragma: no cover - guarded by parse_line
            raise VMError(f"unsupported arithmetic command {command!r}")

    def write_push_pop(self, command: str, segment: str, index: int) -> None:
        if command == "push":
            if segment == "constant":
                self.emit(f"@{index}", "D=A", "@SP", "A=M", "M=D", "@SP", "M=M+1")
            elif segment in INDIRECT_SEGMENTS:
                base = INDIRECT_SEGMENTS[segment]
                self.emit(
                    f"@{index}", "D=A", f"@{base}", "A=D+M", "D=M",
                    "@SP", "A=M", "M=D", "@SP", "M=M+1",
                )
            elif segment == "temp":
                self.emit(
                    f"@{5 + index}", "D=M", "@SP", "A=M", "M=D", "@SP", "M=M+1"
                )
            elif segment == "pointer":
                self.emit(
                    "@THIS" if index == 0 else "@THAT",
                    "D=M", "@SP", "A=M", "M=D", "@SP", "M=M+1",
                )
            elif segment == "static":
                self.emit(
                    f"@{self.file_name}.{index}",
                    "D=M", "@SP", "A=M", "M=D", "@SP", "M=M+1",
                )
            else:  # pragma: no cover
                raise VMError(f"unsupported push segment {segment!r}")
            return

        if command != "pop":  # pragma: no cover
            raise VMError(f"unsupported memory command {command!r}")
        if segment in INDIRECT_SEGMENTS:
            base = INDIRECT_SEGMENTS[segment]
            # Compute the destination address first, then pop the value; using
            # D for the address would clash with the popped value otherwise.
            self.emit(
                f"@{index}", "D=A", f"@{base}", "D=D+M", "@R13", "M=D",
                "@SP", "AM=M-1", "D=M", "@R13", "A=M", "M=D",
            )
        elif segment == "temp":
            self.emit("@SP", "AM=M-1", "D=M", f"@{5 + index}", "M=D")
        elif segment == "pointer":
            self.emit(
                "@SP", "AM=M-1", "D=M", "@THIS" if index == 0 else "@THAT", "M=D"
            )
        elif segment == "static":
            self.emit(
                "@SP", "AM=M-1", "D=M", f"@{self.file_name}.{index}", "M=D"
            )
        else:  # pragma: no cover
            raise VMError(f"unsupported pop segment {segment!r}")

    def write_label(self, label: str) -> None:
        self.emit(f"({self.label_name(label)})")

    def write_goto(self, label: str) -> None:
        self.emit(f"@{self.label_name(label)}", "0;JMP")

    def write_if_goto(self, label: str) -> None:
        self.emit(
            "@SP", "AM=M-1", "D=M", f"@{self.label_name(label)}", "D;JNE"
        )

    def write_function(self, name: str, num_locals: int) -> None:
        self.emit(f"({name})")
        for _ in range(num_locals):
            self.emit("@SP", "A=M", "M=0", "@SP", "M=M+1")

    def write_call(self, name: str, num_args: int) -> None:
        return_label = f"{name}$ret.{self.return_count}"
        self.return_count += 1

        # 1. push return address
        self.emit(f"@{return_label}", "D=A", "@SP", "A=M", "M=D", "@SP", "M=M+1")
        # 2. push the caller's LCL, ARG, THIS, THAT
        for register in ("LCL", "ARG", "THIS", "THAT"):
            self.emit(f"@{register}", "D=M", "@SP", "A=M", "M=D", "@SP", "M=M+1")
        # 3. ARG = SP - 5 - num_args
        self.emit(
            "@SP", "D=M", "@5", "D=D-A", f"@{num_args}", "D=D-A", "@ARG", "M=D"
        )
        # 4. LCL = SP
        self.emit("@SP", "D=M", "@LCL", "M=D")
        # 5. jump to the callee, then land on the return label
        self.emit(f"@{name}", "0;JMP", f"({return_label})")

    def write_return(self) -> None:
        # frame = LCL; retAddr = *(frame - 5)
        self.emit("@LCL", "D=M", "@R13", "M=D")
        self.emit("@5", "A=D-A", "D=M", "@R14", "M=D")
        # *ARG = pop(); SP = ARG + 1
        self.emit("@SP", "AM=M-1", "D=M", "@ARG", "A=M", "M=D")
        self.emit("@ARG", "D=M+1", "@SP", "M=D")
        # restore THAT, THIS, ARG, LCL from frame-1 .. frame-4
        for register in ("THAT", "THIS", "ARG", "LCL"):
            self.emit("@R13", "AM=M-1", "D=M", f"@{register}", "M=D")
        # goto retAddr
        self.emit("@R14", "A=M", "0;JMP")

    def write_bootstrap(self) -> None:
        self.emit("// Bootstrap code", "// Initialize SP = 256")
        self.emit("@256", "D=A", "@SP", "M=D", "// Call Sys.init")
        self.write_call("Sys.init", 0)


def _prepare_files(files: Iterable[VMSource]) -> Sequence[Tuple[str, str]]:
    prepared = []
    for item in files:
        if isinstance(item, (str, Path)):
            path = Path(item)
            prepared.append((str(path), path.read_text(encoding="utf-8-sig")))
        else:
            name, source = item
            prepared.append((str(name), source))
    if not prepared:
        raise VMError("no .vm source was given")
    return prepared


def translate_with_map(
    files: Iterable[VMSource], bootstrap: Optional[bool] = None
) -> Tuple[str, dict]:
    """Translate to Hack assembly and also return the VM -> ROM address map.

    ``map["addresses"][i]`` is the ROM address of VM command ``i``;
    ``map["bootstrap_return"]`` is the return address pushed by the synthetic
    ``call Sys.init 0``; ``map["rom_to_index"]`` converts a saved return address
    back into a VM program counter.  The interpreter uses this to push exactly
    the same return addresses as the generated machine code.
    """
    prepared = _prepare_files(files)
    if bootstrap is None:
        bootstrap = len(prepared) > 1

    writer = CodeWriter()
    writer.scoped_labels = bootstrap
    if bootstrap:
        writer.write_bootstrap()
    bootstrap_return = writer.instruction_count if bootstrap else None

    addresses: List[int] = []
    for name, source in prepared:
        writer.set_file_name(name)
        writer.set_function_name("")
        writer.emit(f"// ========== File: {name} ==========")
        for command in Parser(source).commands:
            addresses.append(writer.instruction_count)
            writer.emit(f"// {command.text}")
            if command.type == "function":
                writer.set_function_name(command.arg1)
            writer.write(command)

    rom_size = writer.instruction_count
    rom_to_index = {}
    for index, address in enumerate(addresses):
        # Several consecutive labels share an address; the first one is the
        # correct destination for a call that lands immediately after them.
        rom_to_index.setdefault(address, index)
    rom_to_index[rom_size] = len(addresses)

    text = "\n".join(writer.lines)
    if text:
        text += "\n"
    layout = {
        "addresses": addresses,
        "bootstrap_return": bootstrap_return,
        "rom_size": rom_size,
        "rom_to_index": rom_to_index,
    }
    return text, layout


def translate(files: Iterable[VMSource], bootstrap: Optional[bool] = None) -> str:
    """Translate one or more ``(name, source)`` pairs into Hack assembly.

    The bootstrap code is emitted for multi-file input by default (and only
    then), matching the standard nand2tetris VM translator contract.
    """
    text, _ = translate_with_map(files, bootstrap)
    return text


def translate_file(input_path: VMFile, output_path: Optional[VMFile] = None):
    """Translate a ``.vm`` file (or a directory of ``.vm`` files) to ``.asm``.

    Returns ``(output_path, instruction_count)`` where the count excludes
    comments, blank lines and label declarations.
    """
    path = Path(input_path)
    if path.is_dir():
        sources = sorted(path.glob("*.vm"), key=lambda item: item.name)
        if not sources:
            raise VMError(f"no .vm files found in {path}")
        output = Path(output_path) if output_path else path / f"{path.name}.asm"
        files = [(item.name, item.read_text(encoding="utf-8-sig")) for item in sources]
        asm = translate(files, bootstrap=True)
    else:
        if output_path is None:
            output = path.with_suffix(".asm")
        else:
            output = Path(output_path)
        files = [(path.name, path.read_text(encoding="utf-8-sig"))]
        asm = translate(files, bootstrap=False)

    output.write_text(asm, encoding="utf-8")
    count = sum(
        1
        for line in asm.splitlines()
        if line and not line.startswith("(") and not line.lstrip().startswith("//")
    )
    return output, count


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in ("-h", "--help"):
        print("Usage: python VMTranslator.py INPUT.vm [OUTPUT.asm]")
        print("       python VMTranslator.py DIRECTORY [OUTPUT.asm]")
        return 0 if args else 2
    if len(args) > 2:
        print("Usage: python VMTranslator.py INPUT.vm [OUTPUT.asm]", file=sys.stderr)
        return 2

    try:
        output, count = translate_file(args[0], args[1] if len(args) == 2 else None)
    except (OSError, VMError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Translated {args[0]} -> {output} ({count} Hack instructions)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
