import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from VMEmulator import VMEmulator
from VMTranslator import VMError

from programs import (
    ARITHMETIC,
    FACTORIAL,
    MAIN_UTILS,
    MEMORY_ACCESS,
    PROGRAM_FLOW,
    SCOPE_FILES,
    SIMPLE_ADD,
    STATIC_FILES,
)


def signed(word):
    return word - 0x10000 if word & 0x8000 else word


def run(files, bootstrap=None, steps=None):
    vm = VMEmulator()
    vm.load(files, bootstrap=bootstrap)
    if steps is None:
        vm.run()
    else:
        vm.run_steps(steps)
    return vm


class EmulatorTests(unittest.TestCase):
    def test_simple_add(self):
        vm = run([("SimpleAdd.vm", SIMPLE_ADD)])
        self.assertEqual(vm.stack(), [15])
        self.assertEqual(vm.registers["SP"], 257)

    def test_all_arithmetic(self):
        vm = run([("Arithmetic.vm", ARITHMETIC)])
        self.assertEqual(
            [signed(value) for value in vm.stack()],
            [13, 7, -7, -13, 4, 6, -1, 0, -1, -1],
        )

    def test_memory_segments(self):
        vm = run([("MemoryAccess.vm", MEMORY_ACCESS)])
        self.assertEqual(vm.stack(), [82])
        self.assertEqual(vm.registers["THIS"], 100)
        self.assertEqual(vm.registers["THAT"], 200)
        self.assertEqual(vm.memory[103], 42)
        self.assertEqual(vm.memory[202], 24)
        self.assertEqual(vm.memory[10], 7)   # temp 5
        self.assertEqual(vm.memory[16], 9)   # static 0

    def test_program_flow(self):
        vm = run([("ProgramFlow.vm", PROGRAM_FLOW)])
        self.assertEqual(vm.stack(), [5])
        self.assertEqual(vm.memory[5], 5)

    def test_recursive_function(self):
        vm = run([("Fact.vm", FACTORIAL)], steps=2000)
        self.assertEqual(vm.memory[256], 120)
        self.assertEqual(vm.registers["LCL"], 0)
        self.assertEqual(vm.registers["ARG"], 0)

    def test_multi_file_functions(self):
        vm = run(MAIN_UTILS, steps=200)
        self.assertEqual(vm.memory[261], 28)

    def test_statics_are_per_file(self):
        vm = run(STATIC_FILES, steps=200)
        self.assertEqual(vm.memory[16], 123)   # Class1.static 0
        self.assertEqual(vm.memory[17], 456)   # Class2.static 0
        self.assertEqual(vm.memory[262], 456)

    def test_labels_are_scoped_per_function(self):
        vm = run(SCOPE_FILES, steps=200)
        self.assertEqual(vm.memory[262], 2)

    def test_bootstrap_needs_sys_init(self):
        vm = VMEmulator()
        with self.assertRaises(VMError):
            vm.load([("A.vm", "push constant 1")], bootstrap=True)

    def test_undefined_label(self):
        vm = VMEmulator()
        with self.assertRaises(VMError):
            vm.load([("A.vm", "goto NOWHERE")])

    def test_duplicate_function(self):
        vm = VMEmulator()
        with self.assertRaises(VMError):
            vm.load([("A.vm", "function f 0\nfunction f 0")])

    def test_stack_underflow(self):
        vm = VMEmulator()
        vm.load([("A.vm", "add")])
        with self.assertRaises(VMError):
            vm.run()

    def test_step_limit(self):
        vm = VMEmulator()
        vm.load([("A.vm", "label LOOP\ngoto LOOP")])
        with self.assertRaises(VMError):
            vm.run(max_steps=50)

    def test_load_files(self):
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "Add.vm"
            path.write_text(SIMPLE_ADD, encoding="utf-8")
            vm = VMEmulator().load_files([str(path)])
            vm.run()
            self.assertEqual(vm.stack(), [15])


if __name__ == "__main__":
    unittest.main()
