// SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com>
// SPDX-License-Identifier: MIT
package com.vowstar.ditdah.e1

import me.jiuyang.zaozi.*

case class DitDahE1Parameter(
  resetVector: Int = 0,
  enableTrace: Boolean = false,
  enableSva: Boolean = false,
  enableJtag: Boolean = false,
  jtagIdcode: Long = 1L,
  enableC: Boolean = true,
  enableZifencei: Boolean = false,
  enableZmmul: Boolean = false,
  multiplyBitsPerCycle: Int = 1,
  fastSmallMultiply: Boolean = false,
  isolateMultiplyOperands: Boolean = false,
  prefetchWindowBits: Int = 0,
  enableZba: Boolean = false
) extends Parameter:
  require((resetVector & 0x3) == 0, "resetVector must be 32-bit aligned")
  require(resetVector >= 0, "resetVector must be non-negative in the initial scaffold")
  require(jtagIdcode >= 0L && jtagIdcode <= 0xffffffffL, "jtagIdcode must fit in 32 bits")
  require(!enableJtag || (jtagIdcode & 1L) == 1L, "jtagIdcode bit 0 must be one")

  require(Set(1, 2, 4).contains(multiplyBitsPerCycle), "multiplyBitsPerCycle must be 1, 2, or 4")

  require(prefetchWindowBits == 0 || (prefetchWindowBits >= 3 && prefetchWindowBits <= 30),
    "prefetchWindowBits must be zero or between 3 and 30")

  val xlen: Int = 32
  val registerCount: Int = 16
  val registerIndexBits: Int = 4
  val pcAlignmentBits: Int = if enableC then 1 else 2

given upickle.default.ReadWriter[DitDahE1Parameter] = upickle.default.macroRW
