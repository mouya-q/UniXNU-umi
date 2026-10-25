/* BootShim probe -- headless bring-up diagnostic.
 *
 * Strategy: paint the display white, wait 5 seconds, then PSCI SYSTEM_RESET.
 * If the device self-reboots after ~5s, this code ran -> BootShim executed
 * correctly and the hang is downstream in SEC.
 * If the device stays frozen with no reboot, BootShim never executed ->
 * the hang is in ABL load/decompression.
 *
 * The kernel header is preserved for ABL's gzip path compatibility.
 * All probe parameters are hardcoded to avoid Makefile macro dependency.
 *
 * Original design: uefi-sheng BootShim.S / BootShimProbe.S.
 * PSCI SYSTEM_RESET = 0x84000009 (ARM DEN 0022).
 */

#define PSCI_SYSTEM_RESET 0x84000009

/* Probe parameters -- hardcoded for umi (Mi 10, SM8250) */
#define FB_BASE   0x9c000000   /* Display Reserved (MemoryMapLib.c) */
#define FB_FILL   0x100000      /* 1 MiB -- fills ~1/35 of the 35 MiB region */
#define PROBE_DELAY_S 5         /* seconds to show the white marker */

_Head:
  adr   x1, _Payload
  b     _Start

#if REQUIRES_KERNEL_HEADER == 1
_StackBase:
  .quad FD_BASE         /* Text Offset */

_StackSize:
  .quad FD_SIZE + (_Payload - _Head) /* Complete shim and payload */
  .quad 0               /* Flags */
  .quad 0               /* Reserved */
  .quad 0               /* Reserved */
  .quad 0               /* Reserved */
  .ascii "ARM\x64"      /* ARM64 Magic */
  .long 0               /* Reserved */
#endif

_Start:
  mov   x11, x1          /* save _Payload addr */
  mov   x12, x0          /* save DT handoff (x0) */

  /* --- Step 1: Paint the top of the frame buffer white --- */
  ldr   x0, =FB_BASE
  ldr   x2, =FB_FILL
  mov   x3, #-1           /* all-ones = white in every 32-bit RGB/BGR layout */
_Paint:
  stp   x3, x3, [x0], #16
  subs  x2, x2, #16
  b.ne  _Paint
  dsb   sy

  /* --- Step 2: Wait PROBE_DELAY_S seconds on the generic timer --- */
  mrs   x4, cntfrq_el0
  cbnz  x4, 1f
  ldr   x4, =19200000     /* fallback: SM8250 timer frequency */
1:
  mov   x5, #PROBE_DELAY_S
  mul   x4, x4, x5        /* target tick count = freq * seconds */
  isb
  mrs   x5, cntpct_el0
  add   x4, x4, x5        /* target = now + delay */
2:
  isb
  mrs   x5, cntpct_el0
  cmp   x5, x4
  b.lo  2b

  /* --- Step 3: PSCI SYSTEM_RESET via SMC --- */
  ldr   w0, =PSCI_SYSTEM_RESET
  mov   x1, xzr
  mov   x2, xzr
  mov   x3, xzr
  smc   #0

  /* If SMC returns (shouldn't for SYSTEM_RESET), spin */
_Dead:
  wfe
  b     _Dead

.text
.ltorg
.align 4

_Payload: