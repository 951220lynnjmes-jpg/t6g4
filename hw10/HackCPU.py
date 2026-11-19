"""Minimal Hack CPU / RAM emulator used to verify translated VM code.

The instruction semantics match ``CPU.hdl`` (and ``hackemu.js`` from the
reference implementation):

* a C-instruction writes ``M`` using the *old* A register,
* ``A`` written by the same instruction is the jump target,
* all words are 16-bit and jumps compare the signed ALU output.

This is not a VM: it only runs 16-bit ``.hack`` machine code.  It lets the test
suite compare ``VMEmulator`` state with the state produced by the real
``VMTranslator -> Assembler -> CPU`` pipeline.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Iterable, List, Optional, Union

from VMTranslator import VMError

SCREEN_BASE = 16384
SCREEN_WORDS = 8192
SCREEN_ROWS = 256
SCREEN_COLS = 512
KBD_ADDR = 24576
RAM_WORDS = 32768
WORD_MASK = 0xFFFF


def _alu(comp: int, x: int, y: int) -> int:
    if comp == 0b101010:
        return 0
    if comp == 0b111111:
        return 1
    if comp == 0b111010:
        return WORD_MASK  # -1
    if comp == 0b001100:
        return x  # D
    if comp == 0b110000:
        return y  # A / M
    if comp == 0b001101:
        return ~x & WORD_MASK  # !D
    if comp == 0b110001:
        return ~y & WORD_MASK  # !A / !M
    if comp == 0b001111:
        return -x & WORD_MASK  # -D
    if comp == 0b110011:
        return -y & WORD_MASK  # -A / -M
    if comp == 0b011111:
        return x + 1  # D+1
    if comp == 0b110111:
        return y + 1  # A+1 / M+1
    if comp == 0b001110:
        return x - 1  # D-1
    if comp == 0b110010:
        return y - 1  # A-1 / M-1
    if comp == 0b000010:
        return x + y  # D+A / D+M
    if comp == 0b010011:
        return x - y  # D-A / D-M
    if comp == 0b000111:
        return y - x  # A-D / M-D
    if comp == 0b000000:
        return x & y  # D&A / D&M
    if comp == 0b010101:
        return x | y  # D|A / D|M
    return 0  # pragma: no cover - unreachable for valid C-instructions


class HackCPU:
    def __init__(self):
        self.rom: List[int] = []
        self.memory = [0] * RAM_WORDS
        self.a = 0
        self.d = 0
        self.pc = 0
        self.cycles = 0

    def reset(self) -> "HackCPU":
        self.memory = [0] * RAM_WORDS
        self.a = 0
        self.d = 0
        self.pc = 0
        self.cycles = 0
        return self

    def load(self, program: Union[str, Iterable[Union[str, int]]]) -> "HackCPU":
        """Load ``.hack`` text (one 16-bit word per line) or a list of words."""
        if isinstance(program, str):
            return self.load_hack(program)
        words = []
        for line_number, item in enumerate(program, 1):
            if isinstance(item, str):
                value = self._parse_word(line_number, item)
            else:
                value = item & WORD_MASK
            words.append(value)
        self.rom = words
        return self.reset()

    def load_hack(self, text: str) -> "HackCPU":
        words = []
        for line_number, raw_line in enumerate(text.splitlines(), 1):
            line = raw_line.strip()
            if line:
                words.append(self._parse_word(line_number, line))
        self.rom = words
        return self.reset()

    @staticmethod
    def _parse_word(line_number: int, line: str) -> int:
        if len(line) != 16 or any(bit not in "01" for bit in line):
            raise VMError(f"Line {line_number}: not a 16-bit binary word: {line!r}")
        return int(line, 2)

    @property
    def halted(self) -> bool:
        return self.pc >= len(self.rom)

    def step(self) -> bool:
        """Execute one machine instruction; return ``False`` at end of ROM."""
        if self.halted:
            return False
        instruction = self.rom[self.pc]
        if instruction & 0x8000 == 0:
            self.a = instruction & 0x7FFF
            self.pc += 1
        else:
            a_bit = (instruction >> 12) & 1
            comp = (instruction >> 6) & 0x3F
            dest = (instruction >> 3) & 0x7
            jump = instruction & 0x7
            old_a = self.a
            y = self.memory[old_a] if a_bit else old_a
            out = _alu(comp, self.d, y) & WORD_MASK
            signed = out - 0x10000 if out & 0x8000 else out

            if dest & 1:
                self.memory[old_a] = out
            if dest & 4:
                self.a = out & 0x7FFF  # the Hack A register is 15-bit
            if dest & 2:
                self.d = out

            taken = (
                signed > 0 if jump == 1 else
                signed == 0 if jump == 2 else
                signed >= 0 if jump == 3 else
                signed < 0 if jump == 4 else
                signed != 0 if jump == 5 else
                signed <= 0 if jump == 6 else
                True if jump == 7 else False
            )
            self.pc = self.a if taken else self.pc + 1
        self.cycles += 1
        return True

    def run(self, max_steps: int = 1_000_000) -> int:
        while not self.halted and self.cycles < max_steps:
            self.step()
        if not self.halted:
            raise VMError(f"step limit {max_steps} exceeded")
        return self.cycles

    def run_steps(self, count: int) -> int:
        """Execute at most ``count`` instructions (useful for infinite loops)."""
        executed = 0
        while executed < count and self.step():
            executed += 1
        return executed

    def screen_pixel(self, row: int, col: int) -> bool:
        if not 0 <= row < SCREEN_ROWS or not 0 <= col < SCREEN_COLS:
            return False
        word = self.memory[SCREEN_BASE + row * 32 + col // 16]
        return bool(word & (1 << (15 - col % 16)))

    def set_key(self, code: int) -> None:
        self.memory[KBD_ADDR] = code & WORD_MASK

    def summary(self) -> str:
        stack = self.memory[256 : self.memory[0]]
        lines = [
            f"cycles = {self.cycles}",
            f"halted = {self.halted}",
            f"A = {self.a}  D = {self.d}  PC = {self.pc}",
            f"SP = {self.memory[0]}  LCL = {self.memory[1]}  ARG = {self.memory[2]}",
            f"stack = {stack if len(stack) < 20 else stack[:20] + ['...']}",
        ]
        return "\n".join(lines)


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in ("-h", "--help"):
        print("Usage: python HackCPU.py INPUT.hack [--steps N]")
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

    try:
        source = Path(args[0]).read_text(encoding="utf-8")
        cpu = HackCPU().load_hack(source)
        # Single-file VM translations have no bootstrap code; a VM emulator
        # would start with SP = 256, so do the same here by default.
        cpu.memory[0] = 256
        if steps is None:
            cpu.run()
        else:
            cpu.run_steps(steps)
    except (OSError, VMError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(cpu.summary())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
