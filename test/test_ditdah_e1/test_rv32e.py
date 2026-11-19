# SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com>
# SPDX-License-Identifier: MIT

import os

import cocotb
from cocotb.triggers import with_timeout

from test_ditdah_e1 import (
    CSR_MEPC, CSR_MISA, assert_trace, axi_backpressure_generators, b_type,
    collect_trace, csrrs, csrrw, i_type, j_type, pack_words, r_type, s_type,
    start_core, u_type,
)


@cocotb.test()
async def base_profile_csrs(dut):
    words = [csrrs(CSR_MISA, 0, 1), i_type(7, 0, 0, 2),
             csrrw(CSR_MEPC, 2, 0), csrrs(CSR_MEPC, 0, 3)]
    await start_core(dut, pack_words(words))
    events = await with_timeout(collect_trace(dut, len(words)), 10, "us")
    assert_trace(events[0], 0, words[0], rd=1, rd_wdata=0x40000010)
    assert_trace(events[3], 12, words[3], rd=3, rd_wdata=4)


@cocotb.test()
async def compressed_encoding_traps(dut):
    word = 0x12340001
    await start_core(dut, pack_words([word]))
    event, = await with_timeout(collect_trace(dut, 1), 10, "us")
    assert_trace(event, 0, word, trap=True, cause=1, next_pc=0)
    assert (event["mcause"], event["mtval"]) == (2, 1)


@cocotb.test()
@cocotb.parametrize(transfer=[
    b_type(2, 0, 0, 0),
    j_type(2, 1),
    i_type(7, 0, 0, 1, opcode=0x67),
])
async def misaligned_transfer(dut, transfer):
    fallthrough = b_type(2, 0, 0, 1)
    await start_core(dut, pack_words([fallthrough, transfer]))
    before, fault = await with_timeout(collect_trace(dut, 2), 10, "us")
    assert_trace(before, 0, fallthrough, next_pc=4)
    assert_trace(fault, 4, transfer, trap=True, cause=9, next_pc=0)
    assert (fault["mcause"], fault["mtval"], fault["mepc"]) == (0, 6, 4)


@cocotb.test()
@cocotb.parametrize(fence=[0x0000100F, 0xFFFF9F8F])
async def instruction_fetch_after_store(dut, fence):
    patched = i_type(7, 0, 0, 3)
    words = [
        u_type(patched, 1, 0x37),
        i_type(patched & 0xFFF, 1, 0, 1),
        s_type(16, 1, 0, 2),
        fence,
        i_type(0, 0, 0, 3),
    ]
    enabled = os.environ.get("TEST_ZIFENCEI") == "1"
    await start_core(dut, pack_words(words), axi_pause_generators=axi_backpressure_generators())
    events = await with_timeout(collect_trace(dut, 5 if enabled else 4), 20, "us")
    assert_trace(events[3], 12, fence, trap=not enabled, cause=0 if enabled else 1)
    if enabled:
        assert_trace(events[4], 16, patched, rd=3, rd_wdata=7)

@cocotb.test(skip=os.environ.get("TEST_MINIMAL") != "1")
@cocotb.parametrize(insn=[r_type(1, 0, 0, 0, 1), r_type(0x10, 0, 0, 2, 1)])
async def minimal_arithmetic_extensions_trap(dut, insn):
    await start_core(dut, pack_words([insn]))
    event, = await with_timeout(collect_trace(dut, 1), 10, "us")
    assert_trace(event, 0, insn, trap=True, cause=1, next_pc=0)
