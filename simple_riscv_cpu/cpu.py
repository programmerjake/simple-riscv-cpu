# SPDX-License-Identifier: LGPL-2.1-or-later
# See Notices.txt for copyright information

import enum
from typing import List
from nmigen.hdl.ast import Cat, Const, Mux, Repl, Signal, unsigned
from nmigen.hdl.dsl import Module
from nmigen.hdl.ir import Elaboratable
from nmigen.hdl.mem import Memory


class CPUMemory(Elaboratable):
    def __init__(self, initial_words: List[int]):
        # data port
        self.address = Signal(unsigned(32))
        self.read_data = Signal(unsigned(32))
        self.write_data = Signal(unsigned(32))
        self.write_byte_enables = Signal(unsigned(4))

        # instruction port
        self.instruction_address = Signal(unsigned(32))
        self.instruction_read_data = Signal(unsigned(32))

        self._memory = Memory(width=32,
                              depth=len(initial_words),
                              init=initial_words)

    def elaborate(self, platform):
        m = Module()

        # data read port
        read_port = self._memory.read_port(domain="comb")
        m.submodules += read_port
        m.d.comb += read_port.addr.eq(self.address)
        m.d.comb += self.read_data.eq(read_port.data)

        # data write port
        write_port = self._memory.write_port(granularity=8)
        m.submodules += write_port
        m.d.comb += write_port.addr.eq(self.address)
        m.d.comb += write_port.data.eq(self.write_data)
        m.d.comb += write_port.en.eq(self.write_byte_enables)

        # instruction read port
        instruction_read_port = self._memory.read_port(domain="comb")
        m.submodules += instruction_read_port
        m.d.comb += instruction_read_port.addr.eq(self.instruction_address)
        m.d.comb += self.instruction_read_data.eq(instruction_read_port.data)
        return m


class Op(enum.Enum):
    Invalid = 0
    LoadUpperImm = enum.auto()
    AddUpperImmPC = enum.auto()
    JumpAndLink = enum.auto()
    JumpAndLinkReg = enum.auto()
    BranchEQ = enum.auto()
    BranchNE = enum.auto()
    BranchLT = enum.auto()
    BranchGE = enum.auto()
    BranchLTUnsigned = enum.auto()
    BranchGEUnsigned = enum.auto()
    LoadByte = enum.auto()
    LoadHalf = enum.auto()
    LoadWord = enum.auto()
    LoadByteUnsigned = enum.auto()
    LoadHalfUnsigned = enum.auto()
    StoreByte = enum.auto()
    StoreHalf = enum.auto()
    StoreWord = enum.auto()
    AddImm = enum.auto()
    SetLTImm = enum.auto()
    SetLTImmUnsigned = enum.auto()
    XorImm = enum.auto()
    OrImm = enum.auto()
    AndImm = enum.auto()
    ShiftLeftImm = enum.auto()
    ShiftRightImm = enum.auto()
    AddOrSub = enum.auto()
    SetLT = enum.auto()
    SetLTUnsigned = enum.auto()
    Xor = enum.auto()
    Or = enum.auto()
    And = enum.auto()
    ShiftLeft = enum.auto()
    ShiftRight = enum.auto()


class OpVariant(enum.Enum):
    Add_ShiftUnsigned = enum.auto()
    Sub_ShiftSigned = enum.auto()


class CPUDecoder(Elaboratable):
    def __init__(self):
        self.instruction_in = Signal(unsigned(32))
        self.op = Signal(Op)
        self.immediate = Signal(unsigned(32))
        self.i_type_immediate = Signal(unsigned(32))
        self.s_type_immediate = Signal(unsigned(32))
        self.b_type_immediate = Signal(unsigned(32))
        self.u_type_immediate = Signal(unsigned(32))
        self.j_type_immediate = Signal(unsigned(32))
        self.rd = Signal(unsigned(5))
        self.rs1 = Signal(unsigned(5))
        self.rs2 = Signal(unsigned(5))
        self.variant = Signal(OpVariant)

    def elaborate(self, platform):
        m = Module()

        m.d.comb += self.rd.eq(self.instruction_in[7:12])
        m.d.comb += self.rs1.eq(self.instruction_in[15:20])
        m.d.comb += self.rs2.eq(self.instruction_in[20:25])

        m.d.comb += self.i_type_immediate.eq(Cat(self.instruction_in[20:32],
                                                 Repl(self.instruction_in[31], 20)))

        m.d.comb += self.s_type_immediate.eq(Cat(self.instruction_in[7:12],
                                                 self.instruction_in[25:32],
                                                 Repl(self.instruction_in[31], 20)))

        m.d.comb += self.b_type_immediate.eq(Cat(Const(0, shape=unsigned(1)),
                                                 self.instruction_in[8:12],
                                                 self.instruction_in[25:31],
                                                 self.instruction_in[7],
                                                 Repl(self.instruction_in[31], 20)))

        m.d.comb += self.u_type_immediate.eq(Cat(Const(0, shape=unsigned(12)),
                                                 self.instruction_in[12:32]))

        m.d.comb += self.j_type_immediate.eq(Cat(Const(0, shape=unsigned(1)),
                                                 self.instruction_in[21:31],
                                                 self.instruction_in[20],
                                                 self.instruction_in[12:20],
                                                 Repl(self.instruction_in[31], 12)))

        with m.Switch(self.instruction_in):
            with m.Case('------- ----- ----- --- ----- 0110111'):
                m.d.comb += self.op.eq(Op.LoadUpperImm)
                m.d.comb += self.immediate.eq(self.u_type_immediate)
            with m.Case('------- ----- ----- --- ----- 0010111'):
                m.d.comb += self.op.eq(Op.AddUpperImmPC)
                m.d.comb += self.immediate.eq(self.u_type_immediate)

            with m.Case('------- ----- ----- --- ----- 1101111'):
                m.d.comb += self.op.eq(Op.JumpAndLink)
                m.d.comb += self.immediate.eq(self.j_type_immediate)

            with m.Case('------- ----- ----- 000 ----- 1100111'):
                m.d.comb += self.op.eq(Op.JumpAndLinkReg)
                m.d.comb += self.immediate.eq(self.i_type_immediate)

            with m.Case('------- ----- ----- 000 ----- 1100011'):
                m.d.comb += self.op.eq(Op.BranchEQ)
                m.d.comb += self.immediate.eq(self.b_type_immediate)
            with m.Case('------- ----- ----- 001 ----- 1100011'):
                m.d.comb += self.op.eq(Op.BranchNE)
                m.d.comb += self.immediate.eq(self.b_type_immediate)
            with m.Case('------- ----- ----- 100 ----- 1100011'):
                m.d.comb += self.op.eq(Op.BranchLT)
                m.d.comb += self.immediate.eq(self.b_type_immediate)
            with m.Case('------- ----- ----- 101 ----- 1100011'):
                m.d.comb += self.op.eq(Op.BranchGE)
                m.d.comb += self.immediate.eq(self.b_type_immediate)
            with m.Case('------- ----- ----- 110 ----- 1100011'):
                m.d.comb += self.op.eq(Op.BranchLTUnsigned)
                m.d.comb += self.immediate.eq(self.b_type_immediate)
            with m.Case('------- ----- ----- 111 ----- 1100011'):
                m.d.comb += self.op.eq(Op.BranchGEUnsigned)
                m.d.comb += self.immediate.eq(self.b_type_immediate)

            with m.Case('------- ----- ----- 000 ----- 0000011'):
                m.d.comb += self.op.eq(Op.LoadByte)
                m.d.comb += self.immediate.eq(self.i_type_immediate)
            with m.Case('------- ----- ----- 001 ----- 0000011'):
                m.d.comb += self.op.eq(Op.LoadHalf)
                m.d.comb += self.immediate.eq(self.i_type_immediate)
            with m.Case('------- ----- ----- 010 ----- 0000011'):
                m.d.comb += self.op.eq(Op.LoadWord)
                m.d.comb += self.immediate.eq(self.i_type_immediate)
            with m.Case('------- ----- ----- 100 ----- 0000011'):
                m.d.comb += self.op.eq(Op.LoadByteUnsigned)
                m.d.comb += self.immediate.eq(self.i_type_immediate)
            with m.Case('------- ----- ----- 101 ----- 0000011'):
                m.d.comb += self.op.eq(Op.LoadHalfUnsigned)
                m.d.comb += self.immediate.eq(self.i_type_immediate)

            with m.Case('------- ----- ----- 000 ----- 0100011'):
                m.d.comb += self.op.eq(Op.StoreByte)
                m.d.comb += self.immediate.eq(self.s_type_immediate)
            with m.Case('------- ----- ----- 001 ----- 0100011'):
                m.d.comb += self.op.eq(Op.StoreHalf)
                m.d.comb += self.immediate.eq(self.s_type_immediate)
            with m.Case('------- ----- ----- 010 ----- 0100011'):
                m.d.comb += self.op.eq(Op.StoreWord)
                m.d.comb += self.immediate.eq(self.s_type_immediate)

            with m.Case('------- ----- ----- 000 ----- 0010011'):
                m.d.comb += self.op.eq(Op.AddImm)
                m.d.comb += self.immediate.eq(self.i_type_immediate)
            with m.Case('0000000 ----- ----- 001 ----- 0010011'):
                m.d.comb += self.op.eq(Op.ShiftLeftImm)
                m.d.comb += self.immediate.eq(self.i_type_immediate)
            with m.Case('------- ----- ----- 010 ----- 0010011'):
                m.d.comb += self.op.eq(Op.SetLTImm)
                m.d.comb += self.immediate.eq(self.i_type_immediate)
            with m.Case('------- ----- ----- 011 ----- 0010011'):
                m.d.comb += self.op.eq(Op.SetLTImmUnsigned)
                m.d.comb += self.immediate.eq(self.i_type_immediate)
            with m.Case('------- ----- ----- 100 ----- 0010011'):
                m.d.comb += self.op.eq(Op.XorImm)
                m.d.comb += self.immediate.eq(self.i_type_immediate)
            with m.Case('0-00000 ----- ----- 101 ----- 0010011'):
                m.d.comb += self.op.eq(Op.ShiftRightImm)
                m.d.comb += self.immediate.eq(self.i_type_immediate)
                m.d.comb += self.variant.eq(Mux(self.instruction_in[30],
                                                OpVariant.Sub_ShiftSigned,
                                                OpVariant.Add_ShiftUnsigned))
            with m.Case('------- ----- ----- 110 ----- 0010011'):
                m.d.comb += self.op.eq(Op.OrImm)
                m.d.comb += self.immediate.eq(self.i_type_immediate)
            with m.Case('------- ----- ----- 111 ----- 0010011'):
                m.d.comb += self.op.eq(Op.AndImm)
                m.d.comb += self.immediate.eq(self.i_type_immediate)

            with m.Case('0-00000 ----- ----- 000 ----- 0110011'):
                m.d.comb += self.op.eq(Op.AddOrSub)
                m.d.comb += self.variant.eq(Mux(self.instruction_in[30],
                                                OpVariant.Sub_ShiftSigned,
                                                OpVariant.Add_ShiftUnsigned))
            with m.Case('0000000 ----- ----- 001 ----- 0110011'):
                m.d.comb += self.op.eq(Op.ShiftLeft)
            with m.Case('0000000 ----- ----- 010 ----- 0110011'):
                m.d.comb += self.op.eq(Op.SetLT)
            with m.Case('0000000 ----- ----- 011 ----- 0110011'):
                m.d.comb += self.op.eq(Op.SetLTUnsigned)
            with m.Case('0000000 ----- ----- 100 ----- 0110011'):
                m.d.comb += self.op.eq(Op.Xor)
            with m.Case('0-00000 ----- ----- 101 ----- 0110011'):
                m.d.comb += self.op.eq(Op.ShiftRight)
                m.d.comb += self.variant.eq(Mux(self.instruction_in[30],
                                                OpVariant.Sub_ShiftSigned,
                                                OpVariant.Add_ShiftUnsigned))
            with m.Case('0000000 ----- ----- 110 ----- 0110011'):
                m.d.comb += self.op.eq(Op.Or)
            with m.Case('0000000 ----- ----- 111 ----- 0110011'):
                m.d.comb += self.op.eq(Op.And)

            with m.Default():
                m.d.comb += self.op.eq(Op.Invalid)
        return m
