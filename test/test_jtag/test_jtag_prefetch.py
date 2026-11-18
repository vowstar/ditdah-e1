# SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com>
# SPDX-License-Identifier: MIT

import cocotb
from cocotb.triggers import ClockCycles

import test_jtag as jtag
from test_ditdah_e1.test_ditdah_e1 import (
    accept_axi_read_request, send_axi_read_response, start_core_without_axi_slave,
)


@cocotb.test()
async def debug_read_waits_for_speculative_fetch(dut):
    dut.jtag_tck.value = 0
    dut.jtag_trstN.value = 0
    dut.jtag_tms.value = 1
    dut.jtag_tdi.value = 0
    await start_core_without_axi_slave(dut)
    await accept_axi_read_request(dut, 0, 6)
    await accept_axi_read_request(dut, 4, 6)
    await send_axi_read_response(dut, 0x10500073)
    await ClockCycles(dut.clk, 2)
    assert int(dut.status_sleep.value)

    dtm = jtag.JtagDtm(dut)
    await dtm.reset()
    await dtm.scan_ir(dtm.IR_DMI)
    await dtm.write(jtag.DM_CONTROL, jtag.DM_ACTIVE)
    await dtm.write(jtag.DM_CONTROL, jtag.DM_ACTIVE | jtag.DM_HALT_REQ)
    await jtag.wait_status(dtm, jtag.STATUS_ALL_HALTED)
    await dtm.write(jtag.DM_DATA1, 0x100)
    await dtm.write(jtag.DM_COMMAND, jtag.CMD_ACCESS_MEMORY | jtag.CMD_SIZE_32)
    assert await dtm.read(jtag.DM_ABSTRACTCS) & (1 << 12)
    assert not int(dut.axi_ar_valid.value)

    await send_axi_read_response(dut, 0, resp=2)
    await accept_axi_read_request(dut, 0x100, 2)
    await send_axi_read_response(dut, 0x12345678)
    await jtag.wait_abstract(dtm)
    assert await dtm.read(jtag.DM_DATA0) == 0x12345678
