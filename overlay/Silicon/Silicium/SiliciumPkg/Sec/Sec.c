#include "UmiSmmuTrace.h"
/**
  Copyright (c) 2011-2017, ARM Limited. All rights reserved.
  SPDX-License-Identifier: BSD-2-Clause-Patent
**/

#include <Library/PcdLib.h>
#include <Library/DebugLib.h>
#include <Library/PrePiLib.h>
#include <Library/DebugAgentLib.h>
#include <Library/BaseMemoryLib.h>
#include <Library/SerialPortLib.h>
#include <Library/PlatformSecLib.h>
#include <Library/PrePiHobListPointerLib.h>
#include <Library/CacheMaintenanceLib.h>
#include <Library/MemoryMapHelperLib.h>
#include <Library/TimerLib.h>
#include <Library/HobLib.h>

#include "Sec.h"

// First argument (x0) of the previous stage, saved by ModuleEntryPoint.S
extern UINT64  gSecEntryArg0;

// IMEM progress cookie: write 32-bit stage IDs to the restart_reason register.
// This address (0x146BF65C) survives warm reset and can be read from Linux
// via the qcom,msm-imem DT node. Each write is followed by DSB to ensure
// the store reaches the register before any subsequent operation that might
// hang or fault.
#define IMEM_COOKIE_ADDR  0x146BF65CULL
#define PROGRESS(Code)  do { \
  *(volatile UINT32 *)(UINTN)IMEM_COOKIE_ADDR = (Code); \
  __asm__ volatile ("dsb sy" ::: "memory"); \
} while (0)

#ifndef MDEPKG_NDEBUG
#ifndef UMI_SKIP_EARLY_FRAMEBUFFER
STATIC
VOID
ClearFrameBuffer (VOID)
{
  EFI_MEMORY_REGION_DESCRIPTOR FrameBufferRegion;

  // Locate "Display Reserved" Memory Region
  LocateMemoryRegionByName ("Display Reserved", &FrameBufferRegion);
  LocateMemoryRegionByName ("Display_Reserved", &FrameBufferRegion);

  // Clear Memory Region
  if (FrameBufferRegion.Address != 0 && FrameBufferRegion.Length != 0) {
    ZeroMem ((VOID *)FrameBufferRegion.Address, FrameBufferRegion.Length);
  }
}

#endif // UMI_SKIP_EARLY_FRAMEBUFFER

STATIC
VOID
PrintFirmwareVersion (VOID)
{
  // umi has no qualified framebuffer until real GOP is installed.
#ifndef UMI_SKIP_EARLY_FRAMEBUFFER
  ClearFrameBuffer ();
#endif

  // Print UEFI Version Message
  DEBUG ((EFI_D_WARN, "\n"));
  DEBUG ((EFI_D_WARN, "Project Silicium for %a %a\n",            FixedPcdGetPtr (PcdSmbiosSystemManufacturer), FixedPcdGetPtr (PcdSmbiosSystemModel)));
  DEBUG ((EFI_D_WARN, "Firmware Version %s Build at %a on %a\n", PcdGetPtr (PcdFirmwareVersionString), __TIME__, __DATE__));
  DEBUG ((EFI_D_WARN, "\n"));
}
#endif

STATIC
EFI_STATUS
InitializeMemory (VOID)
{
  EFI_STATUS                    Status;
  EFI_MEMORY_REGION_DESCRIPTOR  UefiMemoryRegion;
  EFI_HOB_HANDOFF_INFO_TABLE   *HobList;

  // Locate "DXE Heap" Memory Region
  LocateMemoryRegionByName ("DXE Heap", &UefiMemoryRegion);
  LocateMemoryRegionByName ("DXE_Heap", &UefiMemoryRegion);

  // Save UEFI Memory Details
  UINTN UefiMemoryBase = UefiMemoryRegion.Address;
  UINTN UefiMemorySize = UefiMemoryRegion.Length;

  // Verify UEFI Memory Base
  if (UefiMemoryBase == 0 && UefiMemorySize == 0) {
    DEBUG ((EFI_D_ERROR, "Failed to Locate \"DXE Heap\" Memory Region!\n"));
    return EFI_NOT_FOUND;
  }

  // Initialize HOB List
  HobList = HobConstructor ((VOID *)UefiMemoryBase, UefiMemorySize, (VOID *)UefiMemoryBase, (VOID *)(UefiMemoryBase + UefiMemorySize));
  PrePeiSetHobList (HobList);

  // Initialize MMU & Memory HOBs
  Status = MemoryPeim (UefiMemoryBase, UefiMemorySize);
  if (EFI_ERROR (Status)) {
    return Status;
  }

  // Build Stack HOB
  BuildStackHob (FixedPcdGet64 (PcdCPUCoresStackBase), FixedPcdGet32 (PcdCPUCorePrimaryStackSize));

  return EFI_SUCCESS;
}

STATIC
VOID
SecMain (VOID)
{
  EFI_STATUS Status;

  PROGRESS (0x5EC01);
  SerialPortInitialize ();
  PROGRESS (0x5EC02);
  DEBUG ((EFI_D_ERROR, "UMI: SEC start\n"));
  // Do Platform Specific Initialization
  PROGRESS (0x5EC03);
  UmiSmmuSnapshot ("before-platform");
  PROGRESS (0x5EC04);
  PlatformInitialize ();
  PROGRESS (0x5EC05);
  UmiSmmuSnapshot ("after-platform");
  PROGRESS (0x5EC06);
  DEBUG ((EFI_D_ERROR, "UMI: platform initialized\n"));

#ifndef MDEPKG_NDEBUG
  // Initialize Serial Port
  PROGRESS (0x5EC07);
  Status = SerialPortInitialize ();
  if (EFI_ERROR (Status)) {
    PROGRESS (0xDEAD1);
    return;
  }

  // Print Firmware Version
  PROGRESS (0x5EC08);
  PrintFirmwareVersion ();

  // Initialize Debug Agent
  PROGRESS (0x5EC09);
  InitializeDebugAgent (DEBUG_AGENT_INIT_POSTMEM_SEC, NULL, NULL);
  SaveAndSetDebugTimerInterrupt (TRUE);
#endif

  DEBUG ((EFI_D_ERROR, "UMI: memory init start\n"));
  PROGRESS (0x5EC0A);
  // Initialize Memory
  Status = InitializeMemory ();
  DEBUG ((EFI_D_ERROR, "UMI: memory init returned %r\n", Status));
  if (EFI_ERROR (Status)) {
    PROGRESS (0xDEAD2);
    return;
  }

  // Build CPU HOB
  PROGRESS (0x5EC0B);
  BuildCpuHob (ArmGetPhysicalAddressBits (), PcdGet8 (PcdPrePiCpuIoSize));

  // Set the Boot Mode
  SetBootMode (BOOT_WITH_DEFAULT_SETTINGS);

  DEBUG ((EFI_D_ERROR, "UMI: platform PEI start\n"));
  PROGRESS (0x5EC0C);
  // Initialize Platform HOBs
  Status = PlatformPeim ();
  DEBUG ((EFI_D_ERROR, "UMI: platform PEI returned %r\n", Status));
  if (EFI_ERROR (Status)) {
    PROGRESS (0xDEAD3);
    return;
  }

  // Pass on what the previous stage handed over in x0 (a DT address for a
  // Linux-style boot loader), so a DXE driver can use it.
  {
    UINT64  EntryArg = gSecEntryArg0;

    BuildGuidDataHob (&gSiliciumEntryArgHobGuid, &EntryArg, sizeof (EntryArg));
  }

  // Run Library Cconstructors
  PROGRESS (0x5EC0D);
  ProcessLibraryConstructorList ();

  DEBUG ((EFI_D_ERROR, "UMI: FV decompress start\n"));
  PROGRESS (0x5EC0E);
  // Decompress all FVs
  Status = DecompressFirstFv ();
  DEBUG ((EFI_D_ERROR, "UMI: FV decompress returned %r\n", Status));
  if (EFI_ERROR (Status)) {
    DEBUG ((EFI_D_ERROR, "Failed to Decompress FV! Status = %r\n", Status));
    PROGRESS (0xDEAD4);
    return;
  }

  DEBUG ((EFI_D_ERROR, "UMI: DXE core load start\n"));
  PROGRESS (0x5EC0F);
  // Load DXE Core
  Status = LoadDxeCoreFromFv (NULL, 0);
  if (EFI_ERROR (Status)) {
    DEBUG ((EFI_D_ERROR, "Failed to Load DXE Core! Status = %r\n", Status));
    PROGRESS (0xDEAD5);
  }
}

VOID
SecEntry (VOID)
{
  PROGRESS (0x5EC00);

  // Disable Data Cache
  ArmDisableDataCache ();

  // Invalidate Instruction Cache
  ArmInvalidateInstructionCache ();

  // Enable Instruction Cache
  ArmEnableInstructionCache ();

  // Invalidate Stack & UEFI FD D-Cache
  InvalidateDataCacheRange ((VOID *)FixedPcdGet64 (PcdCPUCoresStackBase), FixedPcdGet32 (PcdCPUCorePrimaryStackSize));
  InvalidateDataCacheRange ((VOID *)FixedPcdGet64 (PcdFdBaseAddress),     FixedPcdGet32 (PcdFdSize));

  // Verify Exception Vector Table
  ASSERT (((UINTN)SecVectorTable & ARM_VECTOR_TABLE_ALIGNMENT) == 0);

  // Enable new Exception Vector Table
  ArmWriteVBar ((UINTN)SecVectorTable);

  // Enter Main SEC Function
  SecMain ();
}