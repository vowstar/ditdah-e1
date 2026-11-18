// SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com>
// SPDX-License-Identifier: MIT
package com.vowstar.ditdah.e1

import me.jiuyang.zaozi.*
import me.jiuyang.zaozi.default.{*, given}
import me.jiuyang.zaozi.reftpe.*
import me.jiuyang.zaozi.valuetpe.*

@generator
object DitDahE1JtagDtm
    extends Generator[DitDahE1Parameter, DitDahE1DebugLayers, JtagDtmIO, DitDahE1DebugProbe]:

  override def moduleName(parameter: DitDahE1Parameter): String = "DitDahE1JtagDtm"

  def architecture(parameter: DitDahE1Parameter) =
    val io = summon[Interface[JtagDtmIO]]

    val reset = Wire(new DebugClockReset.Signal)
    reset.value := (io.reset.asBool | !io.trstN).asReset
    val tapReset = DebugClockReset.release(io.tck, reset.value)
    given ClockScope = ClockScope.posedge(io.tck)
    given ResetScope = ResetScope.asyncActiveHigh(tapReset)
    val state = RegInit(0.U(4))
    val irShift = RegInit(1.B(5))
    val drShift = RegInit(0.B(41))
    val activeInstruction = ClockScope.negedge(io.tck) {
      val ir = RegInit(1.U(5))
      when(state === 0.U(4)) { ir := 1.U(5) }
      when(state === 15.U(4)) { ir := irShift.asUInt }
      ir
    }
    val transitions = Seq((1, 0), (1, 2), (3, 9), (4, 5), (4, 5), (6, 8), (6, 7), (4, 8),
      (1, 2), (10, 0), (11, 12), (11, 12), (13, 15), (13, 14), (11, 15), (1, 2))
    for ((low, high), index) <- transitions.zipWithIndex do
      when(state === index.U(4)) { state := io.tms.?(high.U(4), low.U(4)) }
    when(state === 10.U(4)) { irShift := 1.B(5) }
    when(state === 11.U(4)) { irShift := io.tdi.asBits ## irShift.bits(4, 1) }
    val stickyStatus = RegInit(0.U(2))
    val outstanding = RegInit(false.B)
    val responseData = RegInit(0.U(32))
    val address = RegInit(0.U(7))
    val dtmcs = 0.B(17) ## 1.B(3) ## stickyStatus.asBits ## 7.B(6) ## 1.B(4)
    val bridgeReset = DebugClockReset.release(io.tck, io.reset)
    val launch = Wire(Bool())
    val acknowledged = Wire(Bool())
    val available = Wire(Bool())
    ResetScope.asyncActiveHigh(bridgeReset) {
      val toggle = RegInit(false.B)
      val payload = RegInit(0.B(41))
      val busy = RegInit(false.B)
      val ackMeta = RegInit(false.B)
      val ackSync = RegInit(false.B)
      ackMeta := io.responseToggle
      ackSync := ackMeta
      available := !busy & !bridgeReset.asBool
      acknowledged := busy & (ackSync === toggle)
      when(launch) {
        payload := drShift
        toggle := !toggle
        busy := true.B
      }
      when(acknowledged) { busy := false.B }
      io.requestToggle := toggle
      io.requestAddr := payload.bits(40, 34).asUInt
      io.requestData := payload.bits(33, 2).asUInt
      io.requestOp := payload.bits(1, 0).asUInt
    }
    val completing = acknowledged & outstanding
    val completionStatus = (io.responseOp === 1.U(2)).?(2.U(2), io.responseOp)
    val captureStatus = (stickyStatus =/= 0.U(2)).?(stickyStatus, (outstanding & !completing).?(3.U(2),
      completing.?(completionStatus, 0.U(2))))
    when(completing) {
      outstanding := false.B
      address := io.responseAddr
      responseData := io.responseData
      when((stickyStatus === 0.U(2)) & (completionStatus =/= 0.U(2))) { stickyStatus := completionStatus }
    }
    when(state === 3.U(4)) {
      drShift := 0.B(41)
      when(activeInstruction === 1.U(5)) { drShift := parameter.jtagIdcode.B(41) }
      when(activeInstruction === 16.U(5)) { drShift := 0.B(9) ## dtmcs }
      when(activeInstruction === 17.U(5)) {
        drShift := address.asBits ## completing.?(io.responseData, responseData).asBits ## captureStatus.asBits
        when(captureStatus =/= 0.U(2)) { stickyStatus := captureStatus.asBits.bit(1).?(captureStatus, 2.U(2)) }
      }
    }
    when(state === 4.U(4)) {
      drShift := 0.B(40) ## io.tdi.asBits
      when((activeInstruction === 1.U(5)) | (activeInstruction === 16.U(5))) { drShift := 0.B(9) ## io.tdi.asBits ## drShift.bits(31, 1) }
      when(activeInstruction === 17.U(5)) { drShift := io.tdi.asBits ## drShift.bits(40, 1) }
    }
    val operation = drShift.bits(1, 0).asUInt
    val attempt = (state === 8.U(4)) & (activeInstruction === 17.U(5)) & (stickyStatus === 0.U(2)) &
      ((operation === 1.U(2)) | (operation === 2.U(2)))
    launch := attempt & !outstanding & available
    when((state === 8.U(4)) & (activeInstruction === 17.U(5)) & (stickyStatus === 0.U(2)) & (operation === 3.U(2))) {
      stickyStatus := DmiOp.FAILED.U(2)
    }
    when(attempt) {
      when(outstanding | !available) { stickyStatus := 3.U(2) }
      when(launch) {
        outstanding := true.B
        address := drShift.bits(40, 34).asUInt
      }
    }
    when((state === 8.U(4)) & (activeInstruction === 16.U(5)) & drShift.bit(16)) { stickyStatus := 0.U(2) }
    when((state === 0.U(4)) | ((state === 8.U(4)) & (activeInstruction === 16.U(5)) & drShift.bit(17))) {
      outstanding := false.B
      stickyStatus := 0.U(2)
      responseData := 0.U(32)
      address := 0.U(7)
    }
    val tdo = ClockScope.negedge(io.tck) {
      val value = RegInit(false.B)
      value := (state === 11.U(4)).?(irShift.bit(0), (state === 4.U(4)) & drShift.bit(0))
      value
    }
    io.tdo := tdo
    io.tdoEnable := (state === 4.U(4)) | (state === 11.U(4))
