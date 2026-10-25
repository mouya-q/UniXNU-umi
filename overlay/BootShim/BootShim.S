/* BootShim probe v5 -- colors only + x0 DT handoff restore.
 *
 * Based on probe v2 (which successfully showed RED->GREEN->BLUE then hung
 * at SEC entry). The critical fix: restore x0 (DTB pointer) before jumping
 * to SEC. In probe v2, x0 was overwritten by framebuffer address loads
 * during color painting, so SEC received x0=0x9C000000 instead of the
 * device tree pointer. This is a likely cause of the SEC hang.
 *
 * No PMSG or IMEM writes -- those addresses (0xB0200000, 0x146BF65C)
 * are not mapped in ABL's MMU and cause data abort -> immediate device
 * reset to fastboot (confirmed by probe v4 failure).
 *
 * FB Markers (painted at FB_BASE, 0x40000 = 256 KiB, top of screen):
 *   RED    (0xFFFF0000) -- before FD copy
 *   GREEN  (0xFF00FF00) -- after FD copy, before cache clean
 *   BLUE   (0xFF0000FF) -- after cache clean, before jump to SEC
 *   WHITE  (0xFFFFFFFF) -- SEC started (if seen, SEC got past entry)
 *
 * If device freezes: last FB color shows where it hung.
 * No PSCI reset -- we want to see where it stops, not loop.
 * Kernel header preserved for ABL gzip path compatibility.
 */

_Head:
  adr   x1, _Payload
  b     _Start

#if REQUIRES_KERNEL_HEADER == 1
_StackBase:
  .quad FD_BASE

_StackSize:
  .quad FD_SIZE + (_Payload - _Head)
  .quad 0
  .quad 0
  .quad 0
  .quad 0
  .ascii "ARM\x64"
  .long 0
#endif

_Start:
  mov   x11, x1            /* save _Payload addr */
  mov   x12, x0            /* save DT handoff (x0) */

  /* === Stage 1: RED -- before FD copy === */
  ldr   x0, =0x9c000000
  ldr   x2, =0x40000
  ldr   x3, =0xFFFF0000      /* RED in XRGB32 */
_PaintRed:
  stp   x3, x3, [x0], #16
  subs  x2, x2, #16
  b.ne  _PaintRed
  dsb   sy

  /* === FD copy === */
  mov   x4, x11             /* x4 = _Payload (source) */
  ldr   x5, =FD_BASE        /* x5 = FD_BASE (dest) */
  cmp   x4, x5
  beq   _SkipCopy
  ldr   x6, =FD_SIZE

_CopyLoop:
  ldp   x2, x3, [x4], #16
  stp   x2, x3, [x5], #16
  subs  x6, x6, #16
  b.ne  _CopyLoop
  ldr   x5, =FD_BASE

_SkipCopy:
  /* === Stage 2: GREEN -- after FD copy, before cache clean === */
  ldr   x0, =0x9c000000
  ldr   x2, =0x40000
  ldr   x3, =0xFF00FF00      /* GREEN in XRGB32 */
_PaintGreen:
  stp   x3, x3, [x0], #16
  subs  x2, x2, #16
  b.ne  _PaintGreen
  dsb   sy

  /* === Cache clean === */
  dsb   sy
  mrs   x9, ctr_el0
  ubfx  x9, x9, #16, #4
  mov   x10, #4
  lsl   x9, x10, x9
  sub   x10, x9, #1
  bic   x8, x5, x10
  ldr   x7, =FD_SIZE
  add   x7, x5, x7

_CleanLoop:
  dc    cvac, x8
  add   x8, x8, x9
  cmp   x8, x7
  b.lo  _CleanLoop
  dsb   sy
  ic    iallu
  dsb   sy
  isb

  /* === Stage 3: BLUE -- after cache clean, before jump to SEC === */
  ldr   x0, =0x9c000000
  ldr   x2, =0x40000
  ldr   x3, =0xFF0000FF      /* BLUE in XRGB32 */
_PaintBlue:
  stp   x3, x3, [x0], #16
  subs  x2, x2, #16
  b.ne  _PaintBlue
  dsb   sy

  /* === Jump to SEC (ModuleEntryPoint at FD_BASE) === */
  /* Restore DT handoff (x0) saved at _Start before jumping to SEC.
   * Without this, SEC receives x0=0x9C000000 (last FB address) instead
   * of the device tree pointer, likely causing the SEC hang seen in v2. */
  mov   x0, x12

  br    x5

  /* If SEC returns (shouldn't), paint WHITE and spin */
  ldr   x0, =0x9c000000
  ldr   x2, =0x40000
  mov   x3, #-1              /* WHITE */
_PaintWhite:
  stp   x3, x3, [x0], #16
  subs  x2, x2, #16
  b.ne  _PaintWhite
  dsb   sy

_Dead:
  wfe
  b     _Dead

.text
.ltorg
.align 4

_Payload: