# SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com>
# SPDX-License-Identifier: MIT

import cocotb
from cocotb.triggers import ClockCycles, Timer, with_timeout

from test_ditdah_e1 import (
    accept_axi_read_request, assert_trace, collect_trace, j_type, send_axi_read_response,
    start_core_without_axi_slave,
)


@cocotb.test()
async def prefetch_stops_at_last_word_of_reset_window(dut):
    await start_core_without_axi_slave(dut)
    events = cocotb.start_soon(collect_trace(dut, 2))
    await accept_axi_read_request(dut, 0, 6)
    await accept_axi_read_request(dut, 4, 6)
    jump = j_type(0xfffc, 0)
    await send_axi_read_response(dut, jump)
    await accept_axi_read_request(dut, 0xfffc, 6)
    await send_axi_read_response(dut, 0)
    await ClockCycles(dut.clk, 3)
    await Timer(1, unit="ns")
    assert not int(dut.axi_ar_valid.value)
    loop = j_type(0, 0)
    await send_axi_read_response(dut, loop)
    first, last = await with_timeout(events, 10, "us")
    assert_trace(first, 0, jump, next_pc=0xfffc)
    assert_trace(last, 0xfffc, loop, next_pc=0xfffc)
