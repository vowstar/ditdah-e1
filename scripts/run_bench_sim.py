#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com>
# SPDX-License-Identifier: MIT
"""Reproducible RTL benchmark scoring for DitDahE1.

Builds CoreMark/Dhrystone for the selected ISA, runs the no-trace netlist under a
standalone Verilator harness (bench/sim/ditdah_e1_bench_tb.sv) against two
memory models, and emits frequency-normalised CoreMark/MHz and DMIPS/MHz.
Cycle counts are exact (simulator) between the in-program timing markers.
Scores are RTL cycle-accurate, not EEMBC-certified.
"""

import argparse
import json
import os
import struct
import subprocess
import sys
from pathlib import Path

from build_benchmarks import BENCHMARK_ISAS

REPO_ROOT = Path(__file__).resolve().parents[1]

# CoreMark performance-run seeds (validatable CRC at TOTAL_DATA_SIZE=2000).
COREMARK_SEEDS = (0, 0, 0x66)
COREMARK_TOTAL_DATA_SIZE = 2000

# (name, read wait-states, write wait-states, human description)
MEMORY_MODELS = [
    ("tcm_0ws", 0, 0, "0 wait-state tightly-coupled SRAM (intrinsic core)"),
    ("axi_2ws", 2, 2, "AXI-Lite with 2 read + 2 write wait-states"),
]

BENCH_MAGIC = 0xDD32BEEF
BENCH_IDS = {"coremark": 1, "dhrystone": 2}


def run(cmd, cwd=REPO_ROOT, **kw):
    subprocess.run(cmd, cwd=cwd, check=True, **kw)


def bin_to_hex(bin_path, hex_path):
    data = bin_path.read_bytes()
    data += b"\x00" * ((-len(data)) % 4)
    words = struct.unpack("<%dI" % (len(data) // 4), data)
    hex_path.write_text("\n".join("%08x" % w for w in words) + "\n", encoding="utf-8")


def build_benchmarks(out_dir, coremark_iterations, dhrystone_runs, isa, omit_frame_pointer=False):
    run([
        sys.executable, "scripts/build_benchmarks.py",
        "--out-dir", str(out_dir),
        "--isa", isa,
        *(["--omit-frame-pointer"] if omit_frame_pointer else []),
        "--coremark-iterations", str(coremark_iterations),
        "--coremark-seed1", str(COREMARK_SEEDS[0]),
        "--coremark-seed2", str(COREMARK_SEEDS[1]),
        "--coremark-seed3", str(COREMARK_SEEDS[2]),
        "--coremark-total-data-size", str(COREMARK_TOTAL_DATA_SIZE),
        "--dhrystone-runs", str(dhrystone_runs),
    ])


def build_sim(netlist, tb, sim_dir):
    sim_dir.mkdir(parents=True, exist_ok=True)
    binary = sim_dir / "obj_dir" / "ditdah_e1_bench_sim"
    run([
        "verilator", "--binary", "--timing", "-j", "0",
        "-Wno-SELRANGE", "-Wno-WIDTH", "-Wno-BLKANDNBLK", "-Wno-MINTYPMAXDLY",
        "-Wno-CASEINCOMPLETE", "-Wno-UNOPTFLAT", "--bbox-unsup", "-Wno-fatal",
        "--top-module", "ditdah_e1_bench_tb", "-o", "ditdah_e1_bench_sim",
        str(netlist.parent / "DitDahE1Gpr.sv"), str(netlist), str(tb),
    ], cwd=sim_dir)
    if not binary.exists():
        raise SystemExit(f"verilator did not produce {binary}")
    return binary


def run_sim(binary, hex_path, manifest, read_latency, write_latency, max_cycles, pipelined_reads=False):
    out = subprocess.check_output([
        str(binary),
        f"+image={hex_path}",
        f"+result_addr={manifest['result_addr']}",
        f"+timing_addr={manifest['timing_addr']}",
        f"+read_latency={read_latency}",
        f"+write_latency={write_latency}",
        f"+max_cycles={max_cycles}",
        *(["+pipelined_reads"] if pipelined_reads else []),
    ], text=True)
    result, timing = None, None
    for line in out.splitlines():
        if line.startswith("BENCH_RESULT"):
            result = [int(x) for x in line.split()[1:]]
        elif line.startswith("BENCH_TIMING"):
            timing = dict(kv.split("=") for kv in line.split()[1:])
        elif line.startswith("FATAL"):
            raise SystemExit(f"sim: {line}")
    if result is None or timing is None:
        raise SystemExit(f"sim produced no result:\n{out}")
    return result, {k: int(v) for k, v in timing.items()}


def score_one(name, manifest, result, timing, freq_mhz):
    assert result[0] == BENCH_MAGIC, f"{name}: bad magic {result[0]:#x}"
    assert result[1] == BENCH_IDS[name], f"{name}: bad id {result[1]}"
    assert result[2] == 0, f"{name}: nonzero status, result={result}"
    if name == "coremark":
        assert result[5] == 1, f"{name}: CoreMark CRC not validated, result={result}"
        assert result[6] == 0, f"{name}: CoreMark reported errors, result={result}"
    assert timing["have_start"] and timing["have_stop"], f"{name}: timing markers missing"

    timed = timing["stop"] - timing["start"]
    assert timed > 0, f"{name}: nonpositive timed cycles"
    work = result[3]
    per_mhz = work * 1_000_000.0 / timed
    entry = {
        "work_units": work,
        "timed_cycles": timed,
        "cycles_to_trap": timing["total"],
        "cycles_per_work_unit": timed / work,
    }
    if name == "coremark":
        entry["coremark_per_mhz"] = per_mhz
        entry["coremark_per_second"] = per_mhz * freq_mhz
    else:
        entry["dhrystones_per_second"] = per_mhz * freq_mhz
        entry["dmips"] = per_mhz * freq_mhz / 1757.0
        entry["dmips_per_mhz"] = per_mhz / 1757.0
    return entry


def write_markdown(path, report):
    rows = []
    for model in report["memory_models"]:
        cm = report["results"][model["name"]]["coremark"]
        dh = report["results"][model["name"]]["dhrystone"]
        rows.append(
            f"| {model['description']} | {cm['coremark_per_mhz']:.3f} | "
            f"{dh['dmips_per_mhz']:.3f} |"
        )
    lines = [
        "# DitDahE1 RTL benchmark scores",
        "",
        "RTL cycle-accurate, frequency-normalised. Not EEMBC-certified.",
        "",
        f"- ISA/ABI: `{report['march']}` / `{report['mabi']}`",
        f"- CoreMark: {report['coremark_iterations']} iterations, seeds "
        f"{report['coremark_seeds']}, TOTAL_DATA_SIZE={report['coremark_total_data_size']}",
        f"- Dhrystone: {report['dhrystone_runs']} runs",
        f"- Toolchain flags: `{report['cflags']}`",
        "",
        "| Memory model | CoreMark/MHz | DMIPS/MHz |",
        "| --- | ---: | ---: |",
        *rows,
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--bench-dir", type=Path, default=REPO_ROOT / "result" / "bench-score")
    p.add_argument("--netlist", type=Path, default=REPO_ROOT / "result" / "DitDahE1.sv")
    p.add_argument("--isa", choices=BENCHMARK_ISAS, default="rv32e_zba_zmmul")
    p.add_argument("--omit-frame-pointer", action="store_true")
    p.add_argument("--pipelined-reads", action="store_true", help="accept a new address on the preceding read response")
    p.add_argument("--coremark-iterations", type=int, default=200)
    p.add_argument("--dhrystone-runs", type=int, default=100000)
    p.add_argument("--frequency-mhz", type=float, default=100.0)
    p.add_argument("--max-cycles", type=int, default=4_000_000_000)
    p.add_argument("--skip-build-bench", action="store_true")
    args = p.parse_args()

    if not args.netlist.exists():
        raise SystemExit(f"missing {args.netlist}; run build-ditdah-e1 first")
    if "trace_" in args.netlist.read_text(encoding="utf-8"):
        raise SystemExit(f"{args.netlist} has trace ports; score the no-trace netlist")

    bench_dir = args.bench_dir.resolve()
    if not args.skip_build_bench:
        build_benchmarks(bench_dir, args.coremark_iterations, args.dhrystone_runs, args.isa, args.omit_frame_pointer)

    tb = REPO_ROOT / "bench" / "sim" / "ditdah_e1_bench_tb.sv"
    sim_dir = bench_dir / "sim"
    expected_defines = {
        "coremark": {
            "DITDAH_E1_COREMARK_ITERATIONS": args.coremark_iterations,
            "TOTAL_DATA_SIZE": COREMARK_TOTAL_DATA_SIZE,
            **{f"DITDAH_E1_COREMARK_SEED{i}": seed
               for i, seed in enumerate(COREMARK_SEEDS, 1)},
        },
        "dhrystone": {"DITDAH_E1_DHRYSTONE_RUNS": args.dhrystone_runs},
    }
    manifests = {}
    for name in BENCH_IDS:
        manifests[name] = json.loads((bench_dir / name / f"{name}.manifest.json").read_text())
        for key, value in expected_defines[name].items():
            actual = manifests[name]["defines"].get(key)
            if actual != value:
                raise SystemExit(f"{name} image has {key}={actual}, expected {value}")
        if f"-march={args.isa}" not in manifests[name]["cflags"]:
            raise SystemExit(f"{name} image does not target {args.isa}")
        if args.omit_frame_pointer and "-fomit-frame-pointer" not in manifests[name]["cflags"]:
            raise SystemExit(f"{name} image lacks the requested frame-pointer options")
    binary = build_sim(args.netlist.resolve(), tb, sim_dir)
    hexes = {}
    for name in BENCH_IDS:
        hexes[name] = sim_dir / f"{name}.hex"
        bin_to_hex(REPO_ROOT / manifests[name]["bin"], hexes[name])

    results = {}
    for model_name, rlat, wlat, _desc in MEMORY_MODELS:
        results[model_name] = {}
        for name in BENCH_IDS:
            result, timing = run_sim(
                binary, hexes[name], manifests[name], rlat, wlat, args.max_cycles, args.pipelined_reads)
            results[model_name][name] = score_one(
                name, manifests[name], result, timing, args.frequency_mhz)
            s = results[model_name][name]
            key = "coremark_per_mhz" if name == "coremark" else "dmips_per_mhz"
            print(f"[{model_name}] {name}: {s[key]:.4f} "
                  f"{'CoreMark/MHz' if name == 'coremark' else 'DMIPS/MHz'} "
                  f"({s['timed_cycles']} cycles)")

    report = {
        "certification_status": "rtl_cycle_accurate_not_eembc_certified",
        "march": args.isa,
        "compiler": manifests["coremark"].get("compiler"),
        "pipelined_reads": args.pipelined_reads,
        "mabi": "ilp32e",
        "cflags": " ".join(manifests["coremark"]["cflags"]),
        "frequency_mhz": args.frequency_mhz,
        "coremark_iterations": args.coremark_iterations,
        "coremark_seeds": list(COREMARK_SEEDS),
        "coremark_total_data_size": COREMARK_TOTAL_DATA_SIZE,
        "dhrystone_runs": args.dhrystone_runs,
        "memory_models": [
            {"name": n, "read_wait_states": r, "write_wait_states": w, "description": d}
            for n, r, w, d in MEMORY_MODELS
        ],
        "results": results,
    }
    out_json = bench_dir / "benchmark_scores.json"
    out_md = bench_dir / "benchmark_scores.md"
    out_json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_markdown(out_md, report)
    print(f"wrote {os.path.relpath(out_json, REPO_ROOT)} and {os.path.relpath(out_md, REPO_ROOT)}")


if __name__ == "__main__":
    raise SystemExit(main())
