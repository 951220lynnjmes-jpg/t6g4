import re
import sys
from pathlib import Path


SYMBOL_PATTERN = re.compile(r"[A-Za-z_.$:][A-Za-z0-9_.$:]*\Z")
DECIMAL_PATTERN = re.compile(r"[0-9]+\Z")


class AssemblyError(Exception):
    pass


class SymbolTable:
    PREDEFINED_SYMBOLS = {
        "SP": 0,
        "LCL": 1,
        "ARG": 2,
        "THIS": 3,
        "THAT": 4,
        "R0": 0,
        "R1": 1,
        "R2": 2,
        "R3": 3,
        "R4": 4,
        "R5": 5,
        "R6": 6,
        "R7": 7,
        "R8": 8,
        "R9": 9,
        "R10": 10,
        "R11": 11,
        "R12": 12,
        "R13": 13,
        "R14": 14,
        "R15": 15,
        "SCREEN": 16384,
        "KBD": 24576,
    }

    def __init__(self):
        self._symbols = dict(self.PREDEFINED_SYMBOLS)
        self._next_variable_address = 16

    def add_entry(self, symbol, address):
        if not SYMBOL_PATTERN.fullmatch(symbol):
            raise AssemblyError(f"Invalid label: {symbol!r}")
        if symbol in self._symbols:
            raise AssemblyError(f"Duplicate symbol: {symbol}")
        self._symbols[symbol] = address

    def add_variable(self, symbol):
        if not SYMBOL_PATTERN.fullmatch(symbol):
            raise AssemblyError(f"Invalid symbol: {symbol!r}")
        if symbol in self._symbols:
            return self._symbols[symbol]
        if self._next_variable_address > 16383:
            raise AssemblyError("Out of variable memory")
        address = self._next_variable_address
        self._symbols[symbol] = address
        self._next_variable_address += 1
        return address

    def contains(self, symbol):
        return symbol in self._symbols

    def get_address(self, symbol):
        return self._symbols[symbol]


class Parser:
    def __init__(self, source):
        self.instructions = []
        self._parse(source)

    def _parse(self, source):
        for line_number, raw_line in enumerate(source.splitlines(), 1):
            line = raw_line.split("//", 1)[0].strip()
            if not line:
                continue

            if line.startswith("("):
                if not line.endswith(")"):
                    raise AssemblyError(
                        f"Line {line_number}: malformed label declaration"
                    )
                symbol = line[1:-1].strip()
                if not SYMBOL_PATTERN.fullmatch(symbol):
                    raise AssemblyError(f"Line {line_number}: invalid label {symbol!r}")
                self.instructions.append((line_number, f"({symbol})"))
                continue

            if "(" in line or ")" in line:
                raise AssemblyError(f"Line {line_number}: malformed instruction")

            instruction = "".join(line.split())
            self.instructions.append((line_number, instruction))


class Code:
    _COMP = {
        "0": "0101010",
        "1": "0111111",
        "-1": "0111010",
        "D": "0001100",
        "A": "0110000",
        "!D": "0001101",
        "!A": "0110001",
        "-D": "0001111",
        "-A": "0110011",
        "D+1": "0011111",
        "A+1": "0110111",
        "D-1": "0001110",
        "A-1": "0110010",
        "D+A": "0000010",
        "D-A": "0010011",
        "A-D": "0000111",
        "D&A": "0000000",
        "D|A": "0010101",
        "M": "1110000",
        "!M": "1110001",
        "-M": "1110011",
        "M+1": "1110111",
        "M-1": "1110010",
        "D+M": "1000010",
        "D-M": "1010011",
        "M-D": "1000111",
        "D&M": "1000000",
        "D|M": "1010101",
    }

    _DEST = {
        "": "000",
        "M": "001",
        "D": "010",
        "MD": "011",
        "A": "100",
        "AM": "101",
        "AD": "110",
        "AMD": "111",
    }

    _JUMP = {
        "": "000",
        "JGT": "001",
        "JEQ": "010",
        "JGE": "011",
        "JLT": "100",
        "JNE": "101",
        "JLE": "110",
        "JMP": "111",
    }

    def comp(self, mnemonic):
        try:
            return self._COMP[mnemonic]
        except KeyError:
            raise AssemblyError(f"Invalid comp field: {mnemonic!r}") from None

    def dest(self, mnemonic):
        try:
            return self._DEST[mnemonic]
        except KeyError:
            raise AssemblyError(f"Invalid dest field: {mnemonic!r}") from None

    def jump(self, mnemonic):
        try:
            return self._JUMP[mnemonic]
        except KeyError:
            raise AssemblyError(f"Invalid jump field: {mnemonic!r}") from None


class Assembler:
    def __init__(self):
        self._code = Code()

    def assemble(self, source):
        parser = Parser(source)
        symbols = SymbolTable()

        rom_address = 0
        for line_number, instruction in parser.instructions:
            if instruction.startswith("("):
                try:
                    symbols.add_entry(instruction[1:-1], rom_address)
                except AssemblyError as exc:
                    raise AssemblyError(f"Line {line_number}: {exc}") from exc
            else:
                rom_address += 1

        binary = []
        for line_number, instruction in parser.instructions:
            if instruction.startswith("("):
                continue
            try:
                binary.append(self._assemble_instruction(instruction, symbols))
            except AssemblyError as exc:
                raise AssemblyError(f"Line {line_number}: {exc}") from exc
        return binary

    def _assemble_instruction(self, instruction, symbols):
        if instruction.startswith("@"):
            return self._assemble_a_instruction(instruction[1:], symbols)
        return self._assemble_c_instruction(instruction)

    def _assemble_a_instruction(self, symbol, symbols):
        if not symbol:
            raise AssemblyError("Missing value after @")

        if DECIMAL_PATTERN.fullmatch(symbol):
            address = int(symbol)
        else:
            if symbols.contains(symbol):
                address = symbols.get_address(symbol)
            else:
                address = symbols.add_variable(symbol)

        if not 0 <= address <= 32767:
            raise AssemblyError(f"A-instruction value out of range: {address}")
        return f"{address:016b}"

    def _assemble_c_instruction(self, instruction):
        dest = ""
        jump = ""
        rest = instruction

        if "=" in rest:
            parts = rest.split("=")
            if len(parts) != 2:
                raise AssemblyError(f"Invalid C-instruction: {instruction!r}")
            dest, rest = parts
            if not dest:
                raise AssemblyError(f"Invalid C-instruction: {instruction!r}")

        if ";" in rest:
            parts = rest.split(";")
            if len(parts) != 2:
                raise AssemblyError(f"Invalid C-instruction: {instruction!r}")
            comp, jump = parts
            if not jump:
                raise AssemblyError(f"Invalid C-instruction: {instruction!r}")
        else:
            comp = rest

        if not comp:
            raise AssemblyError(f"Invalid C-instruction: {instruction!r}")

        return (
            "111"
            + self._code.comp(comp)
            + self._code.dest(dest)
            + self._code.jump(jump)
        )


def assemble_file(input_path, output_path=None):
    input_path = Path(input_path)
    if not input_path.suffix:
        candidate = input_path.with_suffix(".asm")
        if candidate.exists():
            input_path = candidate
    if output_path is None:
        output_path = input_path.with_suffix(".hack")
    output_path = Path(output_path)

    source = input_path.read_text(encoding="utf-8-sig")
    binary = Assembler().assemble(source)
    text = "\n".join(binary)
    if binary:
        text += "\n"
    output_path.write_text(text, encoding="utf-8")
    return output_path, len(binary)


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in ("-h", "--help"):
        print("Usage: python Assembler.py INPUT.asm [OUTPUT.hack]")
        print("       python Assembler.py")
        return 0 if args else 2
    if len(args) > 2:
        print("Usage: python Assembler.py INPUT.asm [OUTPUT.hack]", file=sys.stderr)
        return 2

    try:
        output_path, count = assemble_file(args[0], args[1] if len(args) == 2 else None)
    except (OSError, AssemblyError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Assembled {args[0]} -> {output_path} ({count} instructions)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
