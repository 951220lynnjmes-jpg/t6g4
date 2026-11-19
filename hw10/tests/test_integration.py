"""End-to-end checks: .vm -> .asm -> .hack -> Hack CPU vs. the VM interpreter."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent / "hw9"))

from Assembler import Assembler
from HackCPU import HackCPU
from VMTranslator import translate
from VMEmulator import VMEmulator

from programs import (
    ARITHMETIC,
    FACTORIAL,
    INFINITE_BOOTSTRAP,
    MAIN_UTILS,
    MEMORY_ACCESS,
    PROGRAM_FLOW,
    SCOPE_FILES,
    SIMPLE_ADD,
    STATIC_FILES,
)


def build(files):
    asm = translate(files)
    binary = Assembler().assemble(asm)
    cpu = HackCPU().load(binary)
    if len(files) == 1:
        # The official VM emulator starts with SP = 256; a single-file
        # translation intentionally has no bootstrap code.
        cpu.memory[0] = 256
    vm = VMEmulator()
    vm.load(files)
    return cpu, vm


class IntegrationTests(unittest.TestCase):
    def assert_memory_equal(self, cpu, vm):
        # The interpreter now writes R13/R14 and pushes ROM return addresses
        # exactly like the translated code, so every RAM word must match.
        self.assertEqual(len(cpu.memory), len(vm.memory))
        for address, (expected, actual) in enumerate(zip(cpu.memory, vm.memory)):
            self.assertEqual(expected, actual, f"RAM[{address}] differs")

    def compare(self, files, cpu_steps=None, vm_steps=None):
        cpu, vm = build(files)
        if cpu_steps is None:
            cpu.run()
            vm.run()
        else:
            cpu.run_steps(cpu_steps)
            vm.run_steps(vm_steps)
        self.assertGreater(cpu.cycles, 0)
        self.assertGreater(vm.steps, 0)
        self.assert_memory_equal(cpu, vm)
        return cpu, vm

    def test_simple_add(self):
        self.compare([("SimpleAdd.vm", SIMPLE_ADD)])

    def test_arithmetic(self):
        self.compare([("Arithmetic.vm", ARITHMETIC)])

    def test_memory_access(self):
        self.compare([("MemoryAccess.vm", MEMORY_ACCESS)])

    def test_program_flow(self):
        self.compare([("ProgramFlow.vm", PROGRAM_FLOW)])

    def test_recursive_functions(self):
        cpu, vm = self.compare(
            [("Fact.vm", FACTORIAL)], cpu_steps=20000, vm_steps=3000
        )
        self.assertEqual(cpu.memory[256], 120)
        self.assertEqual(vm.memory[256], 120)

    def test_multi_file_functions_with_bootstrap(self):
        self.compare(MAIN_UTILS, cpu_steps=3000, vm_steps=300)

    def test_statics_with_bootstrap(self):
        self.compare(STATIC_FILES, cpu_steps=3000, vm_steps=300)

    def test_scoped_labels_with_bootstrap(self):
        self.compare(SCOPE_FILES, cpu_steps=3000, vm_steps=300)

    def test_infinite_bootstrap_loop(self):
        cpu, vm = build(INFINITE_BOOTSTRAP)
        cpu.run_steps(3000)
        vm.run_steps(300)
        self.assert_memory_equal(cpu, vm)
        self.assertEqual(cpu.memory[261], 4)


if __name__ == "__main__":
    unittest.main()
