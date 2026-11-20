import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from hack_assembler import Assembler, AssemblyError, SymbolTable, assemble_file


class AssemblerTests(unittest.TestCase):
    def assemble(self, source):
        return Assembler().assemble(source)

    def test_add_program(self):
        source = """
        // Computes R0 = 2 + 3
        @2
        D=A
        @3
        D=D+A
        @0
        M=D
        """
        self.assertEqual(
            self.assemble(source),
            [
                "0000000000000010",
                "1110110000010000",
                "0000000000000011",
                "1110000010010000",
                "0000000000000000",
                "1110001100001000",
            ],
        )

    def test_labels_and_variables(self):
        source = """
        @counter
        M=0
        (LOOP)
        @counter
        M=M+1
        @LOOP
        0;JMP
        """
        self.assertEqual(
            self.assemble(source),
            [
                "0000000000010000",
                "1110101010001000",
                "0000000000010000",
                "1111110111001000",
                "0000000000000010",
                "1110101010000111",
            ],
        )

    def test_predefined_symbols(self):
        source = """
        @SP
        @LCL
        @ARG
        @THIS
        @THAT
        @R15
        @SCREEN
        @KBD
        D=M
        """
        self.assertEqual(
            self.assemble(source),
            [
                "0000000000000000",
                "0000000000000001",
                "0000000000000010",
                "0000000000000011",
                "0000000000000100",
                "0000000000001111",
                "0100000000000000",
                "0110000000000000",
                "1111110000010000",
            ],
        )

    def test_comments_and_whitespace(self):
        source = """
            @2   // load two
        D = A
        ( LOOP )
        @ LOOP
        0 ; JMP
        """
        self.assertEqual(
            self.assemble(source),
            [
                "0000000000000010",
                "1110110000010000",
                "0000000000000010",
                "1110101010000111",
            ],
        )

    def test_all_destinations(self):
        source = """
        M=0
        D=0
        MD=0
        A=0
        AM=0
        AD=0
        AMD=0
        """
        self.assertEqual(
            self.assemble(source),
            [
                "1110101010001000",
                "1110101010010000",
                "1110101010011000",
                "1110101010100000",
                "1110101010101000",
                "1110101010110000",
                "1110101010111000",
            ],
        )

    def test_all_jumps(self):
        source = """
        0;JGT
        0;JEQ
        0;JGE
        0;JLT
        0;JNE
        0;JLE
        0;JMP
        """
        self.assertEqual(
            self.assemble(source),
            [
                "1110101010000001",
                "1110101010000010",
                "1110101010000011",
                "1110101010000100",
                "1110101010000101",
                "1110101010000110",
                "1110101010000111",
            ],
        )

    def test_invalid_comp(self):
        with self.assertRaises(AssemblyError):
            self.assemble("D=Z")

    def test_invalid_address(self):
        with self.assertRaises(AssemblyError):
            self.assemble("@32768")

    def test_duplicate_label(self):
        with self.assertRaises(AssemblyError):
            self.assemble("(LOOP)\n@LOOP\n0;JMP\n(LOOP)")

    def test_missing_operand(self):
        with self.assertRaises(AssemblyError):
            self.assemble("@")

    def test_invalid_label(self):
        with self.assertRaises(AssemblyError):
            self.assemble("(1LOOP)")

    def test_variable_allocation_order(self):
        table = SymbolTable()
        self.assertEqual(table.add_variable("foo"), 16)
        self.assertEqual(table.add_variable("bar"), 17)
        self.assertEqual(table.add_variable("foo"), 16)
        self.assertEqual(table.get_address("SCREEN"), 16384)

    def test_assemble_file(self):
        with tempfile.TemporaryDirectory() as directory:
            source_path = Path(directory) / "Add.asm"
            source_path.write_text("@2\nD=A\n", encoding="utf-8")
            output_path, count = assemble_file(source_path)
            self.assertEqual(output_path, source_path.with_suffix(".hack"))
            self.assertEqual(count, 2)
            self.assertEqual(
                output_path.read_text(encoding="utf-8").splitlines(),
                ["0000000000000010", "1110110000010000"],
            )


if __name__ == "__main__":
    unittest.main()
