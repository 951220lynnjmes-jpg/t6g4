"""End-to-end: .jack -> .vm -> .asm -> .hack, compared with the VM emulator."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent / "hw9"))
sys.path.insert(0, str(ROOT.parent / "hw10"))

from Assembler import Assembler
from HackCPU import HackCPU
from JackCompiler import compile_source
from VMTranslator import translate
from VMEmulator import VMEmulator

from programs import BOOTSTRAP

WRAPPER = "call Sys.init 0\nlabel DONE\ngoto DONE\n"


class IntegrationTests(unittest.TestCase):
    def test_jack_to_hack_matches_vm_emulator(self):
        source = WRAPPER + compile_source(BOOTSTRAP)
        asm = translate([("Sys.vm", source)], bootstrap=False)

        cpu = HackCPU().load(Assembler().assemble(asm))
        cpu.memory[0] = 256
        vm = VMEmulator().load([("Sys.vm", source)], bootstrap=False)
        cpu.run_steps(3000)
        vm.run_steps(300)

        self.assertGreater(cpu.cycles, 0)
        self.assertGreater(vm.steps, 0)
        self.assertEqual(len(cpu.memory), len(vm.memory))
        for address, (expected, actual) in enumerate(zip(cpu.memory, vm.memory)):
            self.assertEqual(expected, actual, f"RAM[{address}] differs")
        self.assertEqual(cpu.memory[5], 10)
        self.assertEqual(vm.memory[5], 10)


if __name__ == "__main__":
    unittest.main()
