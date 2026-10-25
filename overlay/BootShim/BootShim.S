/* BootShim progressive probe v3 -- locate exact hang point.
 *
 * Strategy: execute the real BootShim flow (FD copy, cache clean, jump to SEC)
 * but insert colored markers at each stage AND write progress codes to
 * persistent storage (pmsg ramoops region + IMEM cookie).
 *
 * FB Markers (painted at FB_BASE, 0x40000 = 256 KiB, top of screen):
 *   RED    (0xFFFF0000) -- before FD copy
 *   GREEN  (0xFF00FF00) -- after FD copy, before cache clean
 *   BLUE   (0xFF0000FF) -- after cache clean, before jump to SEC
 *   WHITE  (0xFFFFFFFF) -- SEC started (if seen, SEC got past entry)
 *
 * Persistent progress codes written to two locations:
 *   1. PMSG ramoops: 0xB0200000 (pmsg_size=2MB, not overwritten by kmsg)
 *      Format: 8 bytes per stage = [MAGIC=0xDEADBEEF][STAGE_ID]
 *      Stages: 1=RED, 2=GREEN, 3=BLUE, 4=SEC_ENTERED
 *   2. IMEM cookie: 0x146BF65C (restart_reason, survives warm reset)
 *      Format: 32-bit stage ID (overwrites reset reason)
 *
 * If device freezes: last FB color shows where it hung.
 * If device reboots (watchdog): pmsg/IMEM code shows last stage reached.
 *
 * No PSCI reset -- we want to see where it stops, not loop.
 * Kernel header preserved for ABL gzip path compatibility.
 */

/* Persistent storage addresses */
#define PMSG_BASE     0xB0200000    /* pmsg region (ramoops + 2MB) */
#define IMEM_COOKIE   0x146BF65C    /* restart_reason register */
#define PROGRESS_MAGIC 0xDEADBEEF

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

/* Helper macro: write progress code to both pmsg and IMEM cookie */
/* Input: w20 = stage_id, x21 = pmsg offset (increments by 8 each stage) */

_Start:
  mov   x11, x1            /* save _Payload addr */
  mov   x12, x0            /* save DT handoff (x0) */

  /* Initialize progress pointer */
  ldr   x21, =PMSG_BASE     /* x21 = pmsg write pointer */

  /* === Stage 1: RED -- before FD copy === */
  ldr   x0, =0x9c000000
  ldr   x2, =0x40000
  ldr   x3, =0xFFFF0000      /* RED in XRGB32 */
_PaintRed:
  stp   x3, x3, [x0], #16
  subs  x2, x2, #16
  b.ne  _PaintRed
  dsb   sy

  /* Write progress: stage 1 (RED) to pmsg + IMEM */
  mov   w20, #1
  ldr   x22, =PROGRESS_MAGIC
  stp   x22, x20, [x21], #16   /* write [MAGIC][STAGE_ID] to pmsg, advance */
  ldr   x23, =IMEM_COOKIE
  str   w20, [x23]             /* write stage_id to IMEM cookie */
  dsb   sy

  /* === FD copy (from production BootShim.S) === */
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

  /* Write progress: stage 2 (GREEN) to pmsg + IMEM */
  mov   w20, #2
  ldr   x22, =PROGRESS_MAGIC
  stp   x22, x20, [x21], #16
  ldr   x23, =IMEM_COOKIE
  str   w20, [x23]
  dsb   sy

  /* === Cache clean (from production BootShim.S) === */
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

  /* Write progress: stage 3 (BLUE) to pmsg + IMEM */
  mov   w20, #3
  ldr   x22, =PROGRESS_MAGIC
  stp   x22, x20, [x21], #16
  ldr   x23, =IMEM_COOKIE
  str   w20, [x23]
  dsb   sy

  /* === Jump to SEC (ModuleEntryPoint at FD_BASE) === */
  /* Write stage 4 before jumping -- if SEC hangs, we know we entered it */
  mov   w20, #4
  ldr   x22, =PROGRESS_MAGIC
  stp   x22, x20, [x21], #16
  ldr   x23, =IMEM_COOKIE
  str   w20, [x23]
  dsb   sy

  /* Restore DT handoff (x0) saved at _Start before jumping to SEC */
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

  /* Write stage 5 (SEC returned) */
  mov   w20, #5
  ldr   x22, =PROGRESS_MAGIC
  stp   x22, x20, [x21], #16
  ldr   x23, =IMEM_COOKIE
  str   w20, [x23]
  dsb   sy

_Dead:
  wfe
  b     _Dead

.text
.ltorg
.align 4

_Payload: