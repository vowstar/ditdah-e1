# DitDah-E1

DitDah-E1 (formerly DitDah32) is a two-stage, single-issue RV32E core for always-on controllers and PHY control. It has 16 integer registers and one AXI4-Lite master port for instructions and data.

The core supports Zicsr, direct machine-mode traps, software, timer and external interrupts, MRET and WFI. Compressed instructions (Zca) default on. Zba, Zmmul, Zifencei, instruction prefetch and single-hart JTAG debug default off. [Instruction set](doc/instruction_table.md)

The diagram shows the default configuration with compressed instructions. [Microarchitecture](doc/microarchitecture.md)

[![Default RV32E datapath with Zca enabled, showing fetch and load/store sharing one AXI4-Lite port](doc/ditdah_e1_microarchitecture.drawio.svg)](doc/microarchitecture.md)

## Build and verify

```sh
nix develop
OUTPUT_DIR=result/production build-ditdah-e1
make verify-smoke      # Build RTL and run unit tests
make verify-signoff    # Run the full verification campaign
```

Use `--no-c` to disable compressed instructions or `--jtag` to enable the RISC-V Debug 1.0 subset. For hardware integration, secure the debug port and supply a device ID with `--jtag-idcode ID`. Run `build-ditdah-e1 --help` for all options. [Verification](doc/verification.md) · [Verification limits](doc/open_gaps.md)

## RTL releases

Download trace-free SystemVerilog for the standard core, the JTAG variant, Anlogic EG4 or the RV32E configuration used for the 7 nm layout. Each archive includes `filelist.f`. [Release downloads](https://github.com/vowstar/ditdah-e1/releases)

For the EG4 build with JTAG disabled, replace `DitDahE1Gpr.sv` in the filelist with `fpga/DitDahE1Gpr.v` and supply the `EG_LOGIC_DRAM` primitive.

## 7 nm layout

The pictured RV32E core uses Zba, Zmmul and a 64 KiB instruction-prefetch window with C and JTAG disabled.

| Measurement on the filled layout | Result |
| --- | ---: |
| Standard-cell area | 869.638 µm² |
| Shortest passing period at 0.75 V, 25 °C (typical) | 1.425 ns |
| Estimated core power at 500 MHz from CoreMark switching activity, excluding memory | 367.7 µW |
| One validated CoreMark iteration in gate simulation with zero memory wait states | 665,163 cycles |

[![Filled 7 nm DitDah-E1 core layout](https://github.com/user-attachments/assets/98bf037e-0950-44de-aae4-5fcff4102fd4)](https://github.com/vowstar/ditdah-e1/issues/2#issuecomment-6982396350)

## License

The project uses the [MIT license](LICENSE). Vendored components retain their [upstream licenses](doc/third_party.md).

## Credits

- Core and debug design draws on [DitDah-E2](https://github.com/vowstar/ditdah-e2), [Ibex](https://github.com/lowRISC/ibex), [Rocket Chip](https://github.com/chipsalliance/rocket-chip) and the [RISC-V Debug Specification](https://github.com/riscv/riscv-debug-spec).
- Verification draws on [PicoRV32](https://github.com/YosysHQ/picorv32), [riscv-formal and NERV](https://github.com/YosysHQ/riscv-formal), [riscv-arch-test](https://github.com/riscv-non-isa/riscv-arch-test), [Spike](https://github.com/riscv-software-src/riscv-isa-sim) and [Sail-RISCV](https://github.com/riscv/sail-riscv).
- The hardware generator and toolchain use [Zaozi](https://github.com/xinpian-tech/zaozi), [LLVM](https://github.com/llvm/llvm-project) and [CIRCT](https://github.com/llvm/circt). Build and packaging draw on [T1](https://github.com/chipsalliance/t1), [UART_Zaozi](https://github.com/vowstar/uart_zaozi) and [mvn-trace-forge](https://github.com/Avimitin/mvn-trace-forge).
