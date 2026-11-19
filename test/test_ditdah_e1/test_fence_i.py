# SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com>
# SPDX-License-Identifier: MIT

import os

import cocotb
from cocotb.triggers import with_timeout

from test_ditdah_e1 import (
    assert_trace, axi_backpressure_generators, collect_trace, i_type, pack_words,
    s_type, start_core, u_type,
)


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
