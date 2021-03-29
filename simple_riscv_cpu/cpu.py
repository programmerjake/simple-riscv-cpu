# SPDX-License-Identifier: LGPL-2.1-or-later
# See Notices.txt for copyright information

import enum
import struct
import os
from typing import List
from nmigen.hdl.ast import Cat, Const, Mux, Repl, Signal, signed, unsigned
from nmigen.hdl.dsl import Module
from nmigen.hdl.ir import Elaboratable
from nmigen.hdl.mem import Memory
from nmigen.cli import main

MEMORY_START_ADDRESS = 0x10000
MEMORY_END_ADDRESS = 0x1000000
RESET_ADDRESS = MEMORY_START_ADDRESS
OUTPUT_PORT_ADDRESS = 0x10000000


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

        self.output_port_data = Signal(unsigned(8))
        self.output_port_valid = Signal()

    def elaborate(self, platform):
        m = Module()

        # data read port
        read_port = self._memory.read_port(domain="comb")
        m.submodules += read_port
        m.d.comb += read_port.addr.eq((self.address -
                                       MEMORY_START_ADDRESS) >> 2)
        m.d.comb += self.read_data.eq(read_port.data)

        # data write port
        write_port = self._memory.write_port(granularity=8)
        m.submodules += write_port
        m.d.comb += write_port.addr.eq((self.address -
                                        MEMORY_START_ADDRESS) >> 2)
        m.d.comb += write_port.data.eq(self.write_data)
        with m.If((self.address >= MEMORY_START_ADDRESS) & (self.address < MEMORY_END_ADDRESS)):
            m.d.comb += write_port.en.eq(self.write_byte_enables)
        with m.If(self.address == OUTPUT_PORT_ADDRESS):
            m.d.comb += self.output_port_data.eq(self.write_data[0:8])
            m.d.comb += self.output_port_valid.eq(self.write_byte_enables[0])

        # instruction read port
        instruction_read_port = self._memory.read_port(domain="comb")
        m.submodules += instruction_read_port
        m.d.comb += instruction_read_port.addr.eq((self.instruction_address -
                                                   MEMORY_START_ADDRESS) >> 2)
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


class LoadStoreSize(enum.Enum):
    Byte = enum.auto()
    Half = enum.auto()
    Word = enum.auto()


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
        self.load_store_size = Signal(LoadStoreSize)
        self.load_signed = Signal()

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
                m.d.comb += self.load_store_size.eq(LoadStoreSize.Byte)
                m.d.comb += self.load_signed.eq(True)
            with m.Case('------- ----- ----- 001 ----- 0000011'):
                m.d.comb += self.op.eq(Op.LoadHalf)
                m.d.comb += self.immediate.eq(self.i_type_immediate)
                m.d.comb += self.load_store_size.eq(LoadStoreSize.Half)
                m.d.comb += self.load_signed.eq(True)
            with m.Case('------- ----- ----- 010 ----- 0000011'):
                m.d.comb += self.op.eq(Op.LoadWord)
                m.d.comb += self.immediate.eq(self.i_type_immediate)
                m.d.comb += self.load_store_size.eq(LoadStoreSize.Word)
                m.d.comb += self.load_signed.eq(True)
            with m.Case('------- ----- ----- 100 ----- 0000011'):
                m.d.comb += self.op.eq(Op.LoadByteUnsigned)
                m.d.comb += self.immediate.eq(self.i_type_immediate)
                m.d.comb += self.load_store_size.eq(LoadStoreSize.Byte)
                m.d.comb += self.load_signed.eq(False)
            with m.Case('------- ----- ----- 101 ----- 0000011'):
                m.d.comb += self.op.eq(Op.LoadHalfUnsigned)
                m.d.comb += self.immediate.eq(self.i_type_immediate)
                m.d.comb += self.load_store_size.eq(LoadStoreSize.Half)
                m.d.comb += self.load_signed.eq(False)

            with m.Case('------- ----- ----- 000 ----- 0100011'):
                m.d.comb += self.op.eq(Op.StoreByte)
                m.d.comb += self.immediate.eq(self.s_type_immediate)
                m.d.comb += self.load_store_size.eq(LoadStoreSize.Byte)
            with m.Case('------- ----- ----- 001 ----- 0100011'):
                m.d.comb += self.op.eq(Op.StoreHalf)
                m.d.comb += self.immediate.eq(self.s_type_immediate)
                m.d.comb += self.load_store_size.eq(LoadStoreSize.Half)
            with m.Case('------- ----- ----- 010 ----- 0100011'):
                m.d.comb += self.op.eq(Op.StoreWord)
                m.d.comb += self.immediate.eq(self.s_type_immediate)
                m.d.comb += self.load_store_size.eq(LoadStoreSize.Word)

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


class CPURegisters(Elaboratable):
    def __init__(self):
        self.rs1_addr = Signal(unsigned(5))
        self.rs1_read_data = Signal(unsigned(32))

        self.rs2_addr = Signal(unsigned(5))
        self.rs2_read_data = Signal(unsigned(32))

        self.rd_addr = Signal(unsigned(5))
        self.rd_write_enable = Signal()
        self.rd_write_data = Signal(unsigned(32))

        self.regs = [Signal(unsigned(32), name=f"x{i}") for i in range(32)]

    def elaborate(self, platform):
        m = Module()
        with m.Switch(self.rs1_addr):
            for i in range(32):
                with m.Case(i):
                    m.d.comb += self.rs1_read_data.eq(self.regs[i])

        with m.Switch(self.rs2_addr):
            for i in range(32):
                with m.Case(i):
                    m.d.comb += self.rs2_read_data.eq(self.regs[i])

        with m.Switch(self.rd_addr):
            for i in range(32):
                with m.Case(i):
                    if i != 0:
                        with m.If(self.rd_write_enable):
                            m.d.sync += self.regs[i].eq(self.rd_write_data)

        return m


class CPU(Elaboratable):
    def __init__(self, initial_words):
        self.memory = CPUMemory(initial_words=initial_words)
        self.decoder = CPUDecoder()
        self.registers = CPURegisters()
        self.pc = Signal(unsigned(32), reset=RESET_ADDRESS)
        self.next_pc = Signal(unsigned(32))
        self.next_pc_fallthrough = Signal(unsigned(32))
        self.load_data = Signal(unsigned(32))
        self.load_data_byte = Signal(unsigned(8))
        self.load_data_half = Signal(unsigned(16))
        self.load_store_address = Signal(unsigned(32))
        self.store_byte_enables = Signal(unsigned(4))
        self.store_half_enables = Signal(unsigned(2))
        self.rs1_read_data_signed = Signal(signed(32))
        self.rs2_read_data_signed = Signal(signed(32))
        self.immediate_signed = Signal(signed(32))
        self.output_port_data = Signal(unsigned(8))
        self.output_port_valid = Signal()

    def elaborate(self, platform):
        m = Module()
        m.submodules.memory = self.memory
        m.submodules.decoder = self.decoder
        m.submodules.registers = self.registers

        m.d.comb += self.output_port_data.eq(self.memory.output_port_data)
        m.d.comb += self.output_port_valid.eq(self.memory.output_port_valid)

        m.d.comb += self.memory.instruction_address.eq(self.pc)
        m.d.comb += self.decoder.instruction_in.eq(
            self.memory.instruction_read_data)
        m.d.comb += self.immediate_signed.eq(self.decoder.immediate)
        m.d.comb += self.registers.rd_addr.eq(self.decoder.rd)
        m.d.comb += self.registers.rs1_addr.eq(self.decoder.rs1)
        m.d.comb += self.rs1_read_data_signed.eq(self.registers.rs1_read_data)
        m.d.comb += self.registers.rs2_addr.eq(self.decoder.rs2)
        m.d.comb += self.rs2_read_data_signed.eq(self.registers.rs2_read_data)
        m.d.comb += self.registers.rd_write_enable.eq(0)
        m.d.comb += self.load_store_address.eq(self.registers.rs1_read_data +
                                               self.decoder.immediate)
        m.d.comb += self.memory.address.eq(self.load_store_address & ~0x3)

        with m.Switch(self.decoder.load_store_size):
            with m.Case(LoadStoreSize.Byte):
                byte_index = self.load_store_address[0:2]
                m.d.comb += self.store_byte_enables.eq(1 << byte_index)
                m.d.comb += self.load_data_byte.eq(
                    self.memory.read_data.word_select(byte_index, 8))
                m.d.comb += self.memory.write_data.eq(
                    Repl(self.registers.rs2_read_data[0:8], 4))
                m.d.comb += self.load_data.eq(
                    Cat(self.load_data_byte,
                        Repl(self.decoder.load_signed &
                             self.load_data_byte[7], 24)))
            with m.Case(LoadStoreSize.Half):
                half_index = self.load_store_address[1]
                m.d.comb += self.store_half_enables.eq(1 << half_index)
                m.d.comb += self.store_byte_enables.eq(Cat(
                    self.store_half_enables[0],
                    self.store_half_enables[0],
                    self.store_half_enables[1],
                    self.store_half_enables[1],
                ))
                m.d.comb += self.load_data_half.eq(
                    self.memory.read_data.word_select(half_index, 16))
                m.d.comb += self.memory.write_data.eq(
                    Repl(self.registers.rs2_read_data[0:16], 2))
                m.d.comb += self.load_data.eq(
                    Cat(self.load_data_half,
                        Repl(self.decoder.load_signed &
                             self.load_data_half[15], 16)))
            with m.Case(LoadStoreSize.Word):
                m.d.comb += self.store_byte_enables.eq(0xF)
                m.d.comb += self.memory.write_data.eq(
                    self.registers.rs2_read_data)
                m.d.comb += self.load_data.eq(self.memory.read_data)

        m.d.comb += self.next_pc_fallthrough.eq(self.pc + 4)
        m.d.comb += self.next_pc.eq(self.next_pc_fallthrough)
        m.d.sync += self.pc.eq(self.next_pc)

        with m.Switch(self.decoder.op):
            with m.Case(Op.Invalid):
                m.d.comb += self.next_pc.eq(self.pc)
            with m.Case(Op.LoadUpperImm):
                m.d.comb += self.registers.rd_write_enable.eq(True)
                m.d.comb += self.registers.rd_write_data.eq(
                    self.decoder.immediate)
            with m.Case(Op.AddUpperImmPC):
                m.d.comb += self.registers.rd_write_enable.eq(True)
                m.d.comb += self.registers.rd_write_data.eq(
                    self.decoder.immediate + self.pc)
            with m.Case(Op.JumpAndLink):
                m.d.comb += self.registers.rd_write_enable.eq(True)
                m.d.comb += self.registers.rd_write_data.eq(
                    self.next_pc_fallthrough)
                m.d.comb += self.next_pc.eq(self.pc + self.decoder.immediate)
            with m.Case(Op.JumpAndLinkReg):
                m.d.comb += self.registers.rd_write_enable.eq(True)
                m.d.comb += self.registers.rd_write_data.eq(
                    self.next_pc_fallthrough)
                m.d.comb += self.next_pc.eq((self.registers.rs1_read_data +
                                             self.decoder.immediate) & ~0x1)
            with m.Case(Op.BranchEQ):
                with m.If(self.registers.rs1_read_data == self.registers.rs2_read_data):
                    m.d.comb += self.next_pc.eq(self.pc +
                                                self.decoder.immediate)
            with m.Case(Op.BranchNE):
                with m.If(self.registers.rs1_read_data != self.registers.rs2_read_data):
                    m.d.comb += self.next_pc.eq(self.pc +
                                                self.decoder.immediate)
            with m.Case(Op.BranchLT):
                with m.If(self.rs1_read_data_signed < self.rs2_read_data_signed):
                    m.d.comb += self.next_pc.eq(self.pc +
                                                self.decoder.immediate)
            with m.Case(Op.BranchGE):
                with m.If(self.rs1_read_data_signed >= self.rs2_read_data_signed):
                    m.d.comb += self.next_pc.eq(self.pc +
                                                self.decoder.immediate)
            with m.Case(Op.BranchLTUnsigned):
                with m.If(self.registers.rs1_read_data < self.registers.rs2_read_data):
                    m.d.comb += self.next_pc.eq(self.pc +
                                                self.decoder.immediate)
            with m.Case(Op.BranchGEUnsigned):
                with m.If(self.registers.rs1_read_data >= self.registers.rs2_read_data):
                    m.d.comb += self.next_pc.eq(self.pc +
                                                self.decoder.immediate)
            with m.Case(Op.LoadByte, Op.LoadHalf, Op.LoadWord,
                        Op.LoadByteUnsigned, Op.LoadHalfUnsigned):
                m.d.comb += self.registers.rd_write_enable.eq(True)
                m.d.comb += self.registers.rd_write_data.eq(self.load_data)
            with m.Case(Op.StoreByte, Op.StoreHalf, Op.StoreWord):
                m.d.comb += self.memory.write_byte_enables.eq(
                    self.store_byte_enables)
            with m.Case(Op.AddImm):
                m.d.comb += self.registers.rd_write_enable.eq(True)
                m.d.comb += self.registers.rd_write_data.eq(
                    self.registers.rs1_read_data + self.decoder.immediate)
            with m.Case(Op.SetLTImm):
                m.d.comb += self.registers.rd_write_enable.eq(True)
                m.d.comb += self.registers.rd_write_data.eq(
                    Mux(self.rs1_read_data_signed < self.immediate_signed, 1, 0))
            with m.Case(Op.SetLTImmUnsigned):
                m.d.comb += self.registers.rd_write_enable.eq(True)
                m.d.comb += self.registers.rd_write_data.eq(
                    Mux(self.registers.rs1_read_data < self.decoder.immediate, 1, 0))
            with m.Case(Op.XorImm):
                m.d.comb += self.registers.rd_write_enable.eq(True)
                m.d.comb += self.registers.rd_write_data.eq(
                    self.registers.rs1_read_data ^ self.decoder.immediate)
            with m.Case(Op.OrImm):
                m.d.comb += self.registers.rd_write_enable.eq(True)
                m.d.comb += self.registers.rd_write_data.eq(
                    self.registers.rs1_read_data | self.decoder.immediate)
            with m.Case(Op.AndImm):
                m.d.comb += self.registers.rd_write_enable.eq(True)
                m.d.comb += self.registers.rd_write_data.eq(
                    self.registers.rs1_read_data & self.decoder.immediate)
            with m.Case(Op.ShiftLeftImm):
                m.d.comb += self.registers.rd_write_enable.eq(True)
                m.d.comb += self.registers.rd_write_data.eq(
                    self.registers.rs1_read_data << self.decoder.immediate[0:5])
            with m.Case(Op.ShiftRightImm):
                m.d.comb += self.registers.rd_write_enable.eq(True)
                with m.If(self.decoder.variant == OpVariant.Sub_ShiftSigned):
                    m.d.comb += self.registers.rd_write_data.eq(
                        self.rs1_read_data_signed >> self.decoder.immediate[0:5])
                with m.Else():
                    m.d.comb += self.registers.rd_write_data.eq(
                        self.registers.rs1_read_data >> self.decoder.immediate[0:5])
            with m.Case(Op.AddOrSub):
                m.d.comb += self.registers.rd_write_enable.eq(True)
                with m.If(self.decoder.variant == OpVariant.Sub_ShiftSigned):
                    m.d.comb += self.registers.rd_write_data.eq(
                        self.registers.rs1_read_data - self.registers.rs2_read_data)
                with m.Else():
                    m.d.comb += self.registers.rd_write_data.eq(
                        self.registers.rs1_read_data + self.registers.rs2_read_data)
            with m.Case(Op.SetLT):
                m.d.comb += self.registers.rd_write_enable.eq(True)
                m.d.comb += self.registers.rd_write_data.eq(
                    Mux(self.rs1_read_data_signed < self.rs2_read_data_signed, 1, 0))
            with m.Case(Op.SetLTUnsigned):
                m.d.comb += self.registers.rd_write_enable.eq(True)
                m.d.comb += self.registers.rd_write_data.eq(
                    Mux(self.registers.rs1_read_data < self.registers.rs2_read_data, 1, 0))
            with m.Case(Op.Xor):
                m.d.comb += self.registers.rd_write_enable.eq(True)
                m.d.comb += self.registers.rd_write_data.eq(
                    self.registers.rs1_read_data ^ self.registers.rs2_read_data)
            with m.Case(Op.Or):
                m.d.comb += self.registers.rd_write_enable.eq(True)
                m.d.comb += self.registers.rd_write_data.eq(
                    self.registers.rs1_read_data | self.registers.rs2_read_data)
            with m.Case(Op.And):
                m.d.comb += self.registers.rd_write_enable.eq(True)
                m.d.comb += self.registers.rd_write_data.eq(
                    self.registers.rs1_read_data & self.registers.rs2_read_data)
            with m.Case(Op.ShiftLeft):
                m.d.comb += self.registers.rd_write_enable.eq(True)
                m.d.comb += self.registers.rd_write_data.eq(
                    self.registers.rs1_read_data << self.registers.rs2_read_data[0:5])
            with m.Case(Op.ShiftRight):
                m.d.comb += self.registers.rd_write_enable.eq(True)
                with m.If(self.decoder.variant == OpVariant.Sub_ShiftSigned):
                    m.d.comb += self.registers.rd_write_data.eq(
                        self.rs1_read_data_signed >> self.registers.rs2_read_data[0:5])
                with m.Else():
                    m.d.comb += self.registers.rd_write_data.eq(
                        self.registers.rs1_read_data >> self.registers.rs2_read_data[0:5])
        return m


if __name__ == "__main__":
    file_name = os.path.dirname(__file__)
    file_name = os.path.dirname(file_name)
    file_name = os.path.join(file_name, "software/ram.bin")
    with open(file_name, "rb") as f:
        ram_bin = f.read()
        initial_words = [i[0] for i in struct.iter_unpack("<I", ram_bin)]
    cpu = CPU(initial_words=initial_words)
    main(cpu)
