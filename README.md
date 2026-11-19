# DitDah-E1

DitDah-E1 (formerly DitDah32) is a two-stage, single-issue RV32E processor for always-on controllers and PHY control. It has 16 integer registers and one AXI4-Lite port for instructions and data.

<p align="center">
  <a href="https://github.com/vowstar/ditdah-e1/issues/2#issuecomment-6982396350"><img src="https://github.com/user-attachments/assets/98bf037e-0950-44de-aae4-5fcff4102fd4" alt="Filled 7 nm layout of the RV32E multiply and prefetch configuration" width="640"></a>
</p>

| Measured 7 nm implementation (C off) | Result |
| --- | ---: |
| Routed standard-cell area | 869.638 µm² |
| Shortest passing clock period at 0.75 V, 25 °C (typical) | 1.425 ns |
| Core power at 500 MHz, excluding external memory | 367.7 µW |
| One validated CoreMark iteration, zero memory wait states | 665,163 cycles |

The pictured layout predates v1.7.0 and uses its default feature set. Timing uses parasitics extracted after metal fill. The power estimate uses switching activity from the validated CoreMark iteration in gate-level simulation. [Pictured implementation and measurements](https://github.com/vowstar/ditdah-e1/issues/2#issuecomment-6982396350) · [7 nm implementation with C](https://github.com/vowstar/ditdah-e1/issues/2#issuecomment-7005801650)

## Microarchitecture

[![Default core showing instruction prefetch, word-aligned decode, integer multiply and the shared AXI4-Lite port](doc/ditdah_e1_microarchitecture.drawio.svg)](doc/microarchitecture.md)

| Build profile | Core features | Instruction fetch |
| --- | --- | --- |
| Default | RV32E, Zicsr, Zba, Zmmul | Sequential prefetch in the aligned 64 KiB window containing the reset vector |
| Compressed | Default plus C (Zca) | Same as default |
| Full | Compressed plus Zifencei (`FENCE.I`) and JTAG debug | Same as default |
| Minimal | RV32E, Zicsr | Demand reads only |

On one validated CoreMark iteration, default firmware took 665,163 cycles with zero memory wait states. Compressed firmware took 727,703 cycles and reduced the code section from 10,496 to 7,652 bytes. The same uncompressed binary took 665,163 cycles on both cores. With two read and write wait states, compressed firmware finished in 1,489,816 cycles and default firmware in 1,684,171.

All profiles use the `ilp32e` ABI and support machine-mode traps, software, timer and external interrupts, MRET and WFI. Map the prefetch window to side-effect-free executable memory. [Instruction set](doc/instruction_table.md) · [Microarchitecture](doc/microarchitecture.md)

## Build and verify

```sh
nix develop
OUTPUT_DIR=result/production build-ditdah-e1
OUTPUT_DIR=result/minimal build-ditdah-e1 --minimal
make verify-smoke
make verify-signoff
```

`--c` enables compressed instructions. Use `--c --zifencei --jtag` to generate the full profile. JTAG implements a single-hart RISC-V Debug 1.0 subset. Secure the debug port and set a device ID with `--jtag-idcode ID`. [Verification](doc/verification.md) · [Debug support and limits](doc/open_gaps.md)

## RTL releases

Download the unsuffixed archive for the default core. Compile firmware with `-march=rv32e_zicsr_zba_zmmul -mabi=ilp32e`. Choose `-minimal` for base RV32E with Zicsr, `-compressed` for firmware containing 16-bit instructions or `-full` for all production features. The `-jtag` and `-fpga` archives add debug and EG4 register-file support respectively to the default core. Each archive includes a filelist and a machine-readable configuration. [Release downloads and profile table](https://github.com/vowstar/ditdah-e1/releases/tag/v1.7.0)

For EG4, replace `DitDahE1Gpr.sv` in the filelist with `fpga/DitDahE1Gpr.v` and supply the `EG_LOGIC_DRAM` primitive.

## License

The project uses the [MIT license](LICENSE). Vendored components retain their [upstream licenses](doc/third_party.md).

## Credits

- Core and debug design draws on [DitDah-E2](https://github.com/vowstar/ditdah-e2), [Ibex](https://github.com/lowRISC/ibex), [Rocket Chip](https://github.com/chipsalliance/rocket-chip) and the [RISC-V Debug Specification](https://github.com/riscv/riscv-debug-spec).
- Verification draws on [PicoRV32](https://github.com/YosysHQ/picorv32), [riscv-formal and NERV](https://github.com/YosysHQ/riscv-formal), [riscv-arch-test](https://github.com/riscv-non-isa/riscv-arch-test), [Spike](https://github.com/riscv-software-src/riscv-isa-sim) and [Sail-RISCV](https://github.com/riscv/sail-riscv).
- The hardware generator and toolchain use [Zaozi](https://github.com/xinpian-tech/zaozi), [LLVM](https://github.com/llvm/llvm-project) and [CIRCT](https://github.com/llvm/circt). Build and packaging draw on [T1](https://github.com/chipsalliance/t1), [UART_Zaozi](https://github.com/vowstar/uart_zaozi) and [mvn-trace-forge](https://github.com/Avimitin/mvn-trace-forge).
