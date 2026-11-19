# SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com>
# SPDX-License-Identifier: MIT

import cocotb
from cocotb.triggers import with_timeout

from test_ditdah_e1 import (
    accept_axi_read_request, assert_trace, c_li, collect_trace, j_type, pack_halfwords,
    pack_words, r_type, send_axi_read_response, start_core, start_core_without_axi_slave,
)


@cocotb.test()
async def compressed_and_straddled_arithmetic(dut):
    setup = c_li(1, 7)
    mul = r_type(1, 1, 1, 0, 2)
    shift_add = r_type(0x10, 1, 2, 2, 3)
    await start_core(dut, pack_halfwords([setup]) + pack_words([mul, shift_add]))
    first, second, third = await with_timeout(collect_trace(dut, 3), 10, "us")
    assert_trace(first, 0, setup, length=2, rd=1, rd_wdata=7)
    assert_trace(second, 2, mul, rd=2, rd_wdata=49)
    assert_trace(third, 6, shift_add, rd=3, rd_wdata=105)


@cocotb.test()
async def prefetched_word_and_reused_halfword(dut):
    await start_core_without_axi_slave(dut)
    trace = cocotb.start_soon(collect_trace(dut, 3))
    await accept_axi_read_request(dut, 0, 6)
    await accept_axi_read_request(dut, 4, 6)
    insns = [c_li(i, i) for i in (1, 2, 3)]
    await send_axi_read_response(dut, (insns[1] << 16) | insns[0])
    await send_axi_read_response(dut, insns[2])
    for i, event in enumerate(await with_timeout(trace, 10, "us")):
        assert_trace(event, 2 * i, insns[i], length=2, rd=i + 1, rd_wdata=i + 1)


@cocotb.test()
async def redirected_fetch_with_back_to_back_responses(dut):
    await start_core_without_axi_slave(dut)
    events = cocotb.start_soon(collect_trace(dut, 2))
    await accept_axi_read_request(dut, 0, 6)
    await accept_axi_read_request(dut, 4, 6)
    jump = j_type(16, 0)
    await send_axi_read_response(dut, jump)
    await accept_axi_read_request(dut, 16, 6)
    await send_axi_read_response(dut, c_li(1, 1))
    target = c_li(2, 7)
    await send_axi_read_response(dut, target)
    first, second = await with_timeout(events, 10, "us")
    assert_trace(first, 0, jump, next_pc=16)
    assert_trace(second, 16, target, length=2, rd=2, rd_wdata=7)
