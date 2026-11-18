# SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com>
# SPDX-License-Identifier: MIT

import random

import cocotb
from cocotb.triggers import with_timeout

from test_ditdah_e1 import (
    assert_trace, collect_trace, i_type, pack_words, r_type, start_core, u_type,
)


def load_constant(value, rd):
    return [u_type((value + 0x800) & 0xFFFFFFFF, rd, 0x37),
            i_type(value, rd, 0, rd)]


@cocotb.test()
async def all_integer_products(dut):
    rng = random.Random(42)
    operands = [0, 1, 0x7FFFFFFF, 0x80000000, 0xFFFFFFFF]
    pairs = [(a, b) for a in operands for b in operands]
    pairs.extend([(511, 511), (512, 511), (511, 512)])
    pairs.extend((rng.getrandbits(32), rng.getrandbits(32)) for _ in range(12))
    words = []
    expected = []
    for a, b in pairs:
        words += load_constant(a, 1) + load_constant(b, 2)
        for op in range(4):
            lhs = a - (1 << 32) if op in (1, 2) and a >> 31 else a
            rhs = b - (1 << 32) if op == 1 and b >> 31 else b
            value = (lhs * rhs >> (32 if op else 0)) & 0xFFFFFFFF
            rd = 3 + op
            expected.append((len(words), rd, value))
            words.append(r_type(1, 2, 1, op, rd))
    await start_core(dut, pack_words(words))
    events = await with_timeout(collect_trace(dut, len(words), max_cycles=10000), 200, "us")
    for index, rd, value in expected:
        assert_trace(events[index], index * 4, words[index], rd=rd, rd_wdata=value)


@cocotb.test()
async def divide_encoding_traps(dut):
    insn = r_type(1, 2, 1, 4, 3)
    await start_core(dut, pack_words([insn]))
    event, = await with_timeout(collect_trace(dut, 1), 10, "us")
    assert_trace(event, 0, insn, trap=True, cause=1)
