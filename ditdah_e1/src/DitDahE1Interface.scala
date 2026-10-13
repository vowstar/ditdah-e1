// SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com>
// SPDX-License-Identifier: MIT
package com.vowstar.ditdah.e1

import me.jiuyang.zaozi.*
import me.jiuyang.zaozi.default.{*, given}
import me.jiuyang.zaozi.reftpe.*
import me.jiuyang.zaozi.valuetpe.*

class DitDahE1Layers(parameter: DitDahE1Parameter) extends LayerInterface(parameter):
  def layers = Seq(Layer("DV"))

class Decoupled[T <: Data](gen: T) extends Bundle:
  val ready = Flipped(Bool())
  val valid = Aligned(Bool())
  val bits  = Aligned(gen)

class AxiAw(parameter: DitDahE1Parameter) extends Bundle:
  val addr = Aligned(UInt(parameter.xlen))
  val prot = Aligned(UInt(3))

class AxiW(parameter: DitDahE1Parameter) extends Bundle:
  val data = Aligned(UInt(parameter.xlen))
  val strb = Aligned(UInt(4))

class AxiB extends Bundle:
  val resp = Aligned(UInt(2))

class AxiAr(parameter: DitDahE1Parameter) extends Bundle:
  val addr = Aligned(UInt(parameter.xlen))
  val prot = Aligned(UInt(3))

class AxiR(parameter: DitDahE1Parameter) extends Bundle:
  val data = Aligned(UInt(parameter.xlen))
  val resp = Aligned(UInt(2))

class AxiLiteBundle(parameter: DitDahE1Parameter) extends Bundle:
  val aw = Aligned(new Decoupled(new AxiAw(parameter)))
  val w  = Aligned(new Decoupled(new AxiW(parameter)))
  val b  = Flipped(new Decoupled(new AxiB))
  val ar = Aligned(new Decoupled(new AxiAr(parameter)))
  val r  = Flipped(new Decoupled(new AxiR(parameter)))

class InterruptBundle extends Bundle:
  val software = Flipped(Bool())
  val timer    = Flipped(Bool())
  val external = Flipped(Bool())
  val pending  = Aligned(Bool())

class StatusBundle extends Bundle:
  val trap  = Aligned(Bool())
  val busy  = Aligned(Bool())
  val sleep = Aligned(Bool())

class JtagBundle extends Bundle:
  val tck   = Flipped(Clock())
  val tms   = Flipped(Bool())
  val tdi   = Flipped(Bool())
  val tdo   = Aligned(Bool())
  val trstN = Flipped(Bool())

class DitDahE1IO(parameter: DitDahE1Parameter) extends HWBundle(parameter):
  val clock = Flipped(Clock())
  val reset = Flipped(Reset())

  val axi    = Aligned(new AxiLiteBundle(parameter))
  val irq    = Aligned(new InterruptBundle)
  val status = Aligned(new StatusBundle)
  val jtag   = Option.when(parameter.enableJtag)(Aligned(new JtagBundle))
