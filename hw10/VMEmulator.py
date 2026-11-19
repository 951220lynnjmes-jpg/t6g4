"""Nand2Tetris VM interpreter (chapters 7 and 8).

Unlike ``VMTranslator``, this module executes the stack-machine bytecode
directly.  It keeps the same RAM contract as the generated Hack code:

    RAM[0]  SP    RAM[1]  LCL   RAM[2]  ARG   RAM[3]  THIS  RAM[4]  THAT
    RAM[5..12] temp      RAM[16..] static variables (per source file)

Calling a function pushes the five frame words (return address, LCL, ARG,
THIS, THAT) onto the very same stack, so the state after running a program can
be compared with the state produced by translating it and running the result
on a real Hack CPU (see ``HackCPU.py`` and ``tests/test_integration.py``).
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from VMTranslator import (
    ARITHMETIC_COMMANDS,
    INDIRECT_SEGMENTS,
    MAX_INDEX,
    Command,
    Parser,
    VMError,
    base_name,
    translate_with_map,
)

SP, LCL, ARG, THIS, THAT = range(5)
TEMP_BASE = 5
STACK_BASE = 256
RAM_WORDS = 32768
WORD_MASK = 0xFFFF

VMSource = Tuple[str, str]


def _signed(value: int) -> int:
    """Interpret a 16-bit word as a signed two's-complement integer."""
    return value - 0x10000 if value & 0x8000 else value


@dataclass
class Instruction:
    command: Command
    file_name: str
    scope: str = ""
    static_address: Optional[int] = None
    target: Optional[int] = None


class VMEmulator:
    """A single-threaded stack machine with Hack-style RAM and call frames."""

    def __init__(self):
        self.memory = [0] * RAM_WORDS
        self.instructions: List[Instruction] = []
        self.labels: Dict[str, int] = {}
        self.functions: Dict[str, int] = {}
        self.static_addresses: Dict[Tuple[str, int], int] = {}
        self.next_static = 16
        self.scoped_labels = False
        self.rom_addresses: List[int] = []
        self.rom_to_index: Dict[int, int] = {}
        self.rom_size = 0
        self.bootstrap_return_address: Optional[int] = None
        self.pc = 0
        self.steps = 0

    # ------------------------------------------------------------------ load

    def load(
        self, files: Iterable[VMSource], bootstrap: Optional[bool] = None
    ) -> "VMEmulator":
        """Load ``(name, source)`` pairs and reset the machine."""
        prepared = []
        for name, source in files:
            prepared.append((base_name(name), source))
        if not prepared:
            raise VMError("no .vm source was given")
        if bootstrap is None:
            bootstrap = len(prepared) > 1

        self.memory = [0] * RAM_WORDS
        self.instructions = []
        self.labels = {}
        self.functions = {}
        self.static_addresses = {}
        self.next_static = 16
        self.scoped_labels = bootstrap
        # Use the translator's own layout so return addresses written into RAM
        # are ROM addresses, exactly like the generated Hack code.
        _, layout = translate_with_map(prepared, bootstrap=bootstrap)
        self.rom_addresses = layout["addresses"]
        self.rom_to_index = layout["rom_to_index"]
        self.rom_size = layout["rom_size"]
        self.bootstrap_return_address = layout["bootstrap_return"]
        self.pc = 0
        self.steps = 0
        self._write(SP, STACK_BASE)

        current_function = ""
        for file_name, source in prepared:
            current_function = ""
            for command in Parser(source).commands:
                index = len(self.instructions)
                instruction = Instruction(command, file_name)

                if command.type == "function":
                    if command.arg1 in self.functions:
                        raise VMError(f"duplicate function {command.arg1!r}")
                    self.functions[command.arg1] = index
                    current_function = command.arg1

                elif command.type == "label":
                    key = self._label_key(current_function, command.arg1)
                    if key in self.labels:
                        raise VMError(f"duplicate label {key!r}")
                    self.labels[key] = index
                    instruction.target = index

                elif command.type in ("push", "pop") and command.arg1 == "static":
                    instruction.static_address = self._static_address(
                        file_name, command.arg2
                    )

                instruction.scope = current_function
                self.instructions.append(instruction)

        # Second pass: labels may be declared after the jump that uses them.
        for instruction in self.instructions:
            command = instruction.command
            if command.type in ("goto", "if-goto"):
                key = self._label_key(instruction.scope, command.arg1)
                instruction.target = self.labels.get(key)
                if instruction.target is None:
                    raise VMError(
                        f"Line {command.line_number}: undefined label "
                        f"{command.arg1!r}"
                    )

        if bootstrap:
            if "Sys.init" not in self.functions:
                raise VMError("bootstrap needs a Sys.init function")
            assert self.bootstrap_return_address is not None
            # Same return address as the generated ``call Sys.init 0``: the
            # label placed immediately after the bootstrap jump.
            self._push(self.bootstrap_return_address)
            for register in (LCL, ARG, THIS, THAT):
                self._push(self._read(register))
            self._write(ARG, self._read(SP) - 5)
            self._write(LCL, self._read(SP))
            self.pc = self.functions["Sys.init"]
        return self

    def load_files(
        self, paths: Sequence[str], bootstrap: Optional[bool] = None
    ) -> "VMEmulator":
        """Read ``.vm`` files from disk and load them."""
        files = [
            (str(path), Path(path).read_text(encoding="utf-8-sig")) for path in paths
        ]
        return self.load(files, bootstrap=bootstrap)

    def _label_key(self, function: str, label: str) -> str:
        # Keep the same rule as VMTranslator: scopes are only needed when
        # several files are linked together.
        if self.scoped_labels and function:
            return f"{function}${label}"
        return label

    def _static_address(self, file_name: str, index: int) -> int:
        key = (file_name, index)
        if key not in self.static_addresses:
            if self.next_static > MAX_INDEX:
                raise VMError("out of static memory")
            self.static_addresses[key] = self.next_static
            self.next_static += 1
        return self.static_addresses[key]

    def _rom_to_vm_pc(self, address: int) -> int:
        """Translate a saved ROM return address back to a VM command index."""
        try:
            return self.rom_to_index[address]
        except KeyError:
            raise VMError(f"return address {address} is not a VM instruction") from None

    # --------------------------------------------------------------- memory

    def _read(self, address: int) -> int:
        if not 0 <= address < RAM_WORDS:
            raise VMError(f"RAM address out of range: {address}")
        return self.memory[address]

    def _write(self, address: int, value: int) -> None:
        if not 0 <= address < RAM_WORDS:
            raise VMError(f"RAM address out of range: {address}")
        self.memory[address] = value & WORD_MASK

    def _push(self, value: int) -> None:
        top = self._read(SP)
        self._write(top, value)
        self._write(SP, top + 1)

    def _pop(self) -> int:
        top = self._read(SP) - 1
        if top < STACK_BASE:
            raise VMError("stack underflow")
        value = self._read(top)
        self._write(SP, top)
        return value

    def stack(self) -> List[int]:
        """Return the live portion of the stack (RAM[256 .. SP-1])."""
        return self.memory[STACK_BASE : self._read(SP)]

    # ------------------------------------------------------------ execution

    @property
    def halted(self) -> bool:
        return self.pc >= len(self.instructions)

    @property
    def registers(self) -> Dict[str, int]:
        return {
            name: self.memory[register]
            for name, register in (
                ("SP", SP),
                ("LCL", LCL),
                ("ARG", ARG),
                ("THIS", THIS),
                ("THAT", THAT),
            )
        }

    def step(self) -> bool:
        """Execute one VM command; return ``False`` when the program halts."""
        if self.halted:
            return False

        instruction = self.instructions[self.pc]
        command = instruction.command
        next_pc = self.pc + 1

        if command.type == "arithmetic":
            self._arithmetic(command.cmd)
        elif command.type == "push":
            self._push_value(instruction, command.arg1, command.arg2)
        elif command.type == "pop":
            self._pop_value(instruction, command.arg1, command.arg2)
        elif command.type == "label":
            pass
        elif command.type == "goto":
            next_pc = instruction.target
        elif command.type == "if-goto":
            if self._pop() != 0:
                next_pc = instruction.target
        elif command.type == "function":
            for _ in range(command.arg2):
                self._push(0)
        elif command.type == "call":
            if command.arg1 not in self.functions:
                raise VMError(f"call to undefined function {command.arg1!r}")
            # The generated code pushes the ROM address of the label emitted
            # right after the call, not a VM command index.
            return_address = (
                self.rom_addresses[self.pc + 1]
                if self.pc + 1 < len(self.rom_addresses)
                else self.rom_size
            )
            self._push(return_address)
            for register in (LCL, ARG, THIS, THAT):
                self._push(self._read(register))
            arg_base = self._read(SP) - 5 - command.arg2
            if arg_base < STACK_BASE:
                raise VMError("argument base below the stack base")
            self._write(ARG, arg_base)
            self._write(LCL, self._read(SP))
            next_pc = self.functions[command.arg1]
        elif command.type == "return":
            next_pc = self._rom_to_vm_pc(self._return())

        self.pc = next_pc
        self.steps += 1
        return True

    def run(self, max_steps: int = 1_000_000) -> int:
        """Run until halt; raise ``VMError`` if ``max_steps`` is exhausted."""
        while not self.halted and self.steps < max_steps:
            self.step()
        if not self.halted:
            raise VMError(f"step limit {max_steps} exceeded")
        return self.steps

    def run_steps(self, count: int) -> int:
        """Execute at most ``count`` commands (useful for infinite loops)."""
        executed = 0
        while executed < count and self.step():
            executed += 1
        return executed

    def _arithmetic(self, operation: str) -> None:
        if operation in ("neg", "not"):
            value = self._pop()
            self._push(-value if operation == "neg" else ~value)
            return

        if operation not in ARITHMETIC_COMMANDS:  # pragma: no cover
            raise VMError(f"unsupported operation {operation!r}")
        y = self._pop()
        x = self._pop()
        if operation == "add":
            result = x + y
        elif operation == "sub":
            result = x - y
        elif operation == "and":
            result = x & y
        elif operation == "or":
            result = x | y
        else:
            left, right = _signed(x), _signed(y)
            truth = {
                "eq": left == right,
                "gt": left > right,
                "lt": left < right,
            }[operation]
            result = -1 if truth else 0
        self._push(result)

    def _segment_address(self, instruction: Instruction, segment: str, index: int) -> int:
        if segment in INDIRECT_SEGMENTS:
            return self._read(
                {"local": LCL, "argument": ARG, "this": THIS, "that": THAT}[segment]
            ) + index
        if segment == "temp":
            return TEMP_BASE + index
        if segment == "pointer":
            return THIS + index
        if segment == "static":
            return instruction.static_address
        raise VMError(f"unsupported segment {segment!r}")

    def _push_value(self, instruction: Instruction, segment: str, index: int) -> None:
        if segment == "constant":
            self._push(index)
            return
        self._push(self._read(self._segment_address(instruction, segment, index)))

    def _pop_value(self, instruction: Instruction, segment: str, index: int) -> None:
        address = self._segment_address(instruction, segment, index)
        if segment in INDIRECT_SEGMENTS:
            # The translated code keeps the computed target address in R13.
            self._write(13, address)
        self._write(address, self._pop())

    def _return(self) -> int:
        frame = self._read(LCL)
        if frame < 5:
            raise VMError("return without a call frame")
        # Mirror the generated code: R13 = frame, R14 = return address, then
        # R13 is decremented once for each restored register.
        self._write(13, frame)
        return_address = self._read(frame - 5)
        self._write(14, return_address)

        value = self._pop()
        arg_base = self._read(ARG)
        self._write(arg_base, value)
        self._write(SP, arg_base + 1)
        for register in (THAT, THIS, ARG, LCL):
            address = self._read(13) - 1
            self._write(13, address)
            self._write(register, self._read(address))
        return return_address

    def load_directory(self, directory) -> "VMEmulator":
        """Load every ``.vm`` file in a directory with bootstrap enabled."""
        path = Path(directory)
        sources = sorted(path.glob("*.vm"), key=lambda item: item.name)
        if not sources:
            raise VMError(f"no .vm files found in {path}")
        return self.load(
            [(item.name, item.read_text(encoding="utf-8-sig")) for item in sources],
            bootstrap=True,
        )

    def summary(self) -> str:
        lines = [f"steps  = {self.steps}", f"halted = {self.halted}"]
        lines += [f"{name:5s} = {value}" for name, value in self.registers.items()]
        stack = self.stack()
        lines.append(f"stack  = {stack if len(stack) < 20 else stack[:20] + ['...']}")
        statics = [
            f"RAM[{address}] = {value}"
            for (_, _index), address in sorted(self.static_addresses.items())
            if (value := self.memory[address]) != 0
        ]
        if statics:
            lines.append("static = " + ", ".join(statics))
        return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in ("-h", "--help"):
        print("Usage: python VMEmulator.py INPUT.vm [INPUT2.vm ...] [--steps N]")
        print("       python VMEmulator.py DIRECTORY [--steps N]")
        return 0 if args else 2

    steps = None
    if "--steps" in args:
        position = args.index("--steps")
        if position + 1 >= len(args):
            print("Error: --steps needs a number", file=sys.stderr)
            return 2
        try:
            steps = int(args[position + 1])
        except ValueError:
            print("Error: --steps needs a number", file=sys.stderr)
            return 2
        del args[position : position + 2]

    paths = [Path(arg) for arg in args]
    try:
        vm = VMEmulator()
        if len(paths) == 1 and paths[0].is_dir():
            vm.load_directory(paths[0])
        else:
            vm.load_files([str(path) for path in paths], bootstrap=len(paths) > 1)
        if steps is None:
            vm.run()
        else:
            vm.run_steps(steps)
    except (OSError, VMError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(vm.summary())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
