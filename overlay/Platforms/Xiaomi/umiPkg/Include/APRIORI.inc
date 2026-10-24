# Derived from this umi's original 84-entry DXE APRIORI list, SHA-256
# 8d0fc7193d28024d497d35f56c0256fb860b1b2cd3cbc3efa5dfa89937c5f73f.
# Keep the relative stock order of selected binaries and source equivalents.
# APRIORI deliberately bypasses DEPEX, as it did for DisplayDxe in stock XBL;
# the binaries and their original DEPEX sections are not changed.
# This is a pruned subset with replacement core services, NOT the stock boot
# environment. PCD and UniXNUDxe are additional local components.
APRIORI DXE {
  # stock index 0: DxeCore
  INF MdeModulePkg/Core/Dxe/DxeMain.inf
  # local dependency of the source core, absent from the stock list
  INF MdeModulePkg/Universal/PCD/Dxe/Pcd.inf
  # stock index 1: EnvDxe
  INF Binaries/umi/QcomPkg/Drivers/EnvDxe/EnvDxe.inf
  # stock index 2: RscRtDxe
  INF MdeModulePkg/Universal/ReportStatusCodeRouter/RuntimeDxe/ReportStatusCodeRouterRuntimeDxe.inf
  # stock index 3: SCHandlerRtDxe
  INF MdeModulePkg/Universal/StatusCodeHandler/RuntimeDxe/StatusCodeHandlerRuntimeDxe.inf
  # stock index 4: RuntimeDxe
  INF MdeModulePkg/Core/RuntimeDxe/RuntimeDxe.inf
  # stock index 5: ArmCpuDxe
  INF ArmPkg/Drivers/CpuDxe/CpuDxe.inf
  # stock index 6: ArmGicDxe
  INF ArmPkg/Drivers/ArmGicDxe/ArmGicDxe.inf
  # stock index 7: MetronomeDxe
  INF EmbeddedPkg/MetronomeDxe/MetronomeDxe.inf
  # stock index 8: ArmTimerDxe
  INF ArmPkg/Drivers/TimerDxe/TimerDxe.inf
  # stock index 9: SmemDxe
  INF Binaries/umi/QcomPkg/Drivers/SmemDxe/SmemDxe.inf
  # stock index 10: DALSys
  INF Binaries/umi/QcomPkg/Drivers/DALSYSDxe/DALSYSDxe.inf
  # stock index 11: HWIODxeDriver
  INF Binaries/umi/QcomPkg/Drivers/HWIODxe/HWIODxe.inf
  # stock index 12: ChipInfo
  INF Binaries/umi/QcomPkg/Drivers/ChipInfoDxe/ChipInfoDxe.inf
  # stock index 13: PlatformInfoDxeDriver
  INF Binaries/umi/QcomPkg/Drivers/PlatformInfoDxe/PlatformInfoDxe.inf
  # stock index 14: HALIOMMU omitted in attempt 05 (attach-path isolation).
  # stock index 15: ULogDxe
  INF Binaries/umi/QcomPkg/Drivers/ULogDxe/ULogDxe.inf
  # stock index 16: CmdDbDxe
  INF Binaries/umi/QcomPkg/Drivers/CmdDbDxe/CmdDbDxe.inf
  # stock index 17: PwrUtilsDxe -- omitted (umi-specific, not in cepheus binaries)
  # stock index 18: NpaDxe
  INF Binaries/umi/QcomPkg/Drivers/NpaDxe/NpaDxe.inf
  # stock index 19: RpmhDxe
  INF Binaries/umi/QcomPkg/Drivers/RpmhDxe/RpmhDxe.inf
  # stock index 20: PdcDxe
  INF Binaries/umi/QcomPkg/Drivers/PdcDxe/PdcDxe.inf
  # stock index 21: VcsDxe -- omitted (umi-specific, not in cepheus binaries)
  # stock index 22: ClockDxe
  INF Binaries/umi/QcomPkg/Drivers/ClockDxe/ClockDxe.inf
  # stock index 23: SPMI
  INF Binaries/umi/QcomPkg/Drivers/SPMIDxe/SPMIDxe.inf
  # stock index 24: ShmBridgeDxe
  INF Binaries/umi/QcomPkg/Drivers/ShmBridgeDxe/ShmBridgeDxeLA.inf
  # stock index 25: ScmDxe
  INF Binaries/umi/QcomPkg/Drivers/TzDxe/ScmDxeLA.inf
  # stock index 26: DALTLMM
  INF Binaries/umi/QcomPkg/Drivers/TLMMDxe/TLMMDxe.inf
  # stock index 27: ResetRuntimeDxe
  INF MdeModulePkg/Universal/ResetSystemRuntimeDxe/ResetSystemRuntimeDxe.inf
  # stock index 28: PmicDxe
  INF Binaries/umi/QcomPkg/Drivers/PmicDxe/PmicDxeLa.inf
  # stock index 36: TzDxe
  INF Binaries/umi/QcomPkg/Drivers/TzDxe/TzDxeLA.inf
  # stock index 37: VariableDxe
  INF MdeModulePkg/Universal/Variable/RuntimeDxe/VariableRuntimeDxe.inf
  # stock index 41: SPI -- omitted (umi-specific, not in cepheus binaries)
  # stock index 42: I2C
  INF Binaries/umi/QcomPkg/Drivers/I2CDxe/I2CDxe.inf
  # stock index 43: DisplayDxe
  INF Binaries/umi/QcomPkg/Drivers/DisplayDxe/DisplayDxe.inf
  # stock index 47: CPRDxe
  INF Binaries/umi/QcomPkg/Drivers/CPRDxe/CPRDxe.inf
  # stock index 48: WatchdogTimer
  INF MdeModulePkg/Universal/WatchdogTimerDxe/WatchdogTimer.inf
  # stock index 52: EmbeddedMonotonicCounter
  INF EmbeddedPkg/EmbeddedMonotonicCounter/EmbeddedMonotonicCounter.inf
  # stock index 53: RealTimeClock
  INF EmbeddedPkg/RealTimeClockRuntimeDxe/RealTimeClockRuntimeDxe.inf
  # stock index 54: PrintDxe
  INF MdeModulePkg/Universal/PrintDxe/PrintDxe.inf
  # stock index 55: DevicePathDxe
  INF MdeModulePkg/Universal/DevicePathDxe/DevicePathDxe.inf
  # stock index 56: CapsuleRuntimeDxe, with unsupported-update/null backend
  INF MdeModulePkg/Universal/CapsuleRuntimeDxe/CapsuleRuntimeDxe.inf
  # stock index 57: HiiDatabase
  INF MdeModulePkg/Universal/HiiDatabaseDxe/HiiDatabaseDxe.inf
  # stock index 59: QcomBds
  INF MdeModulePkg/Universal/BdsDxe/BdsDxe.inf
  # stock index 81: ConPlatformDxe
  INF MdeModulePkg/Universal/Console/ConPlatformDxe/ConPlatformDxe.inf
  # stock index 82: ConSplitterDxe
  INF MdeModulePkg/Universal/Console/ConSplitterDxe/ConSplitterDxe.inf
  # stock index 83: GraphicsConsoleDxe
  INF MdeModulePkg/Universal/Console/GraphicsConsoleDxe/GraphicsConsoleDxe.inf
  # local registration, after the selected stock console chain
  INF UniXNUPkg/Driver/UniXNUDxe/UniXNUDxe.inf
}