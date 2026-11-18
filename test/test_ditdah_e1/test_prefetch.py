# SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com>
# SPDX-License-Identifier: MIT

import cocotb
from cocotb.triggers import ClockCycles, Timer, with_timeout

from test_ditdah_e1 import (
    AXI_ERROR_CAUSE, AXI_SLVERR, accept_axi_read_request, assert_trace,
    collect_trace, i_type, j_type, pack_words, r_type, send_axi_read_response,
    start_core,
    start_core_without_axi_slave,
)


@cocotb.test()
async def wrong_path_error_does_not_trap(dut):
    await start_core_without_axi_slave(dut)
    traces = cocotb.start_soon(collect_trace(dut, 2))
    await accept_axi_read_request(dut, 0, 6)
    await accept_axi_read_request(dut, 4, 6)
    jump = j_type(64, 0)
    await send_axi_read_response(dut, jump)
    await accept_axi_read_request(dut, 64, 6)
    await send_axi_read_response(dut, 0, resp=AXI_SLVERR)
    await ClockCycles(dut.clk, 3)
    await Timer(1, unit="ns")
    assert not int(dut.axi_ar_valid.value)
    add = i_type(7, 0, 0, 1)
    await send_axi_read_response(dut, add)
    branch, target = await with_timeout(traces, 10, "us")
    assert_trace(branch, 0, jump, next_pc=64)
    assert_trace(target, 64, add, rd=1, rd_wdata=7)


@cocotb.test()
async def fault_on_requested_prefetch(dut):
    await start_core_without_axi_slave(dut)
    traces = cocotb.start_soon(collect_trace(dut, 2))
    await accept_axi_read_request(dut, 0, 6)
    await accept_axi_read_request(dut, 4, 6)
    await send_axi_read_response(dut, i_type(3, 0, 0, 1))
    await send_axi_read_response(dut, 0, resp=AXI_SLVERR)
    first, fault = await with_timeout(traces, 10, "us")
    assert first["rd_wdata"] == 3
    assert (fault["pc"], fault["trap"], fault["cause"]) == (4, 1, AXI_ERROR_CAUSE)
    assert (fault["mcause"], fault["mtval"], fault["mepc"]) == (1, 4, 4)

@cocotb.test()
async def shift_add_addressing(dut):
    words = [i_type(-1, 0, 0, 1), i_type(13, 0, 0, 2)]
    words.extend(r_type(0x10, 2, 1, funct3, 3) for funct3 in (2, 4, 6))
    words.append(r_type(0x10, 2, 16, 2, 3))
    await start_core(dut, pack_words(words))
    events = await with_timeout(collect_trace(dut, len(words)), 10, "us")
    for i, value in enumerate((11, 9, 5), start=2):
        assert_trace(events[i], i * 4, words[i], rd=3, rd_wdata=value)
    assert_trace(events[-1], 20, words[-1], trap=True, cause=3)
