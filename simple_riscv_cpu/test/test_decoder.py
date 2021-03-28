# SPDX-License-Identifier: LGPL-2.1-or-later
# See Notices.txt for copyright information

import enum
from typing import Dict
from simple_riscv_cpu.cpu import CPUDecoder, LoadStoreSize, Op
from nmigen.sim import Simulator, Delay
import unittest


class TestDecoder(unittest.TestCase):
    def check(self, instruction: int, expected: Dict[str, int]):
        decoder = CPUDecoder()
        sim = Simulator(decoder)

        def input_process():
            yield decoder.instruction_in.eq(instruction)

        def check_process():
            yield Delay(1e-6)
            for k, expected_value in expected.items():
                value = yield getattr(decoder, k)
                if isinstance(expected_value, enum.Enum):
                    value = expected_value.__class__(value)
                else:
                    value = hex(value)
                    expected_value = hex(expected_value)
                with self.subTest(f"decoder.{k}"):
                    self.assertEqual(value, expected_value)

        with sim.write_vcd(f"test_decode_{hex(instruction)}.vcd"):
            sim.add_process(input_process)
            sim.add_process(check_process)
            sim.run()

    def test_zero(self):
        self.check(0, {'op': Op.Invalid})

    def test_ones(self):
        self.check(0xFFFFFFFF, {'op': Op.Invalid})

    def test_lui(self):
        self.check(0x12345637, {'op': Op.LoadUpperImm,
                                'immediate': 0x12345000,
                                'rd': 0xC})

    def test_jal(self):
        self.check(0x12345FEF, {'op': Op.JumpAndLink,
                                'immediate': 0x45922,
                                'rd': 0x1F})

    def test_ori(self):
        self.check(0x82386293, {'op': Op.OrImm,
                                'immediate': 0xFFFFF823,
                                'rd': 0x5,
                                'rs1': 0x10})

    def test_sb(self):
        self.check(0x44CA0B23, {'op': Op.StoreByte,
                                'immediate': 0x456,
                                'rs1': 0x14,
                                'rs2': 0xC,
                                'load_store_size': LoadStoreSize.Byte})

    def test_bltu(self):
        self.check(0x25466363, {'op': Op.BranchLTUnsigned,
                                'immediate': 0x246,
                                'rs1': 0xC,
                                'rs2': 0x14})


if __name__ == "__main__":
    unittest.main()
