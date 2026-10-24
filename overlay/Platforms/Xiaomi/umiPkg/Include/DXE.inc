# Baseline core services and consoles. The explicit RAM payload profile adds
# source DiskIo/FAT and a read-only RAM block device in the generated checkout.
# Persistent UFS/SD/USB devices and firmware updater applications are absent.
  INF MdeModulePkg/Core/Dxe/DxeMain.inf
  INF MdeModulePkg/Universal/PCD/Dxe/Pcd.inf
  INF MdeModulePkg/Core/RuntimeDxe/RuntimeDxe.inf
  INF ArmPkg/Drivers/CpuDxe/CpuDxe.inf
  INF MdeModulePkg/Universal/SecurityStubDxe/SecurityStubDxe.inf
  INF MdeModulePkg/Universal/WatchdogTimerDxe/WatchdogTimer.inf
  INF MdeModulePkg/Universal/ReportStatusCodeRouter/RuntimeDxe/ReportStatusCodeRouterRuntimeDxe.inf
  INF MdeModulePkg/Universal/StatusCodeHandler/RuntimeDxe/StatusCodeHandlerRuntimeDxe.inf
  INF MdeModulePkg/Universal/Variable/RuntimeDxe/VariableRuntimeDxe.inf
  INF EmbeddedPkg/EmbeddedMonotonicCounter/EmbeddedMonotonicCounter.inf
  INF MdeModulePkg/Universal/ResetSystemRuntimeDxe/ResetSystemRuntimeDxe.inf
  INF EmbeddedPkg/RealTimeClockRuntimeDxe/RealTimeClockRuntimeDxe.inf
  INF EmbeddedPkg/MetronomeDxe/MetronomeDxe.inf
  INF MdeModulePkg/Universal/PrintDxe/PrintDxe.inf
  INF MdeModulePkg/Universal/DevicePathDxe/DevicePathDxe.inf
  INF MdeModulePkg/Universal/CapsuleRuntimeDxe/CapsuleRuntimeDxe.inf
  INF MdeModulePkg/Universal/Console/ConPlatformDxe/ConPlatformDxe.inf
  INF MdeModulePkg/Universal/Console/ConSplitterDxe/ConSplitterDxe.inf
  INF MdeModulePkg/Universal/Console/GraphicsConsoleDxe/GraphicsConsoleDxe.inf
  INF MdeModulePkg/Universal/HiiDatabaseDxe/HiiDatabaseDxe.inf
  INF MdeModulePkg/Universal/SetupBrowserDxe/SetupBrowserDxe.inf
  INF ArmPkg/Drivers/ArmGicDxe/ArmGicDxe.inf
  INF ArmPkg/Drivers/TimerDxe/TimerDxe.inf
  INF MdeModulePkg/Universal/BdsDxe/BdsDxe.inf

# Exact paths are populated from this handset's XBL export. Preserve each
# original DEPEX. APRIORI retains the selected stock ordering (see README).
  INF Binaries/umi/QcomPkg/Drivers/EnvDxe/EnvDxe.inf
  INF Binaries/umi/QcomPkg/Drivers/TzDxe/ScmDxeLA.inf
  INF Binaries/umi/QcomPkg/Drivers/TzDxe/TzDxeLA.inf
  INF Binaries/umi/QcomPkg/Drivers/SmemDxe/SmemDxe.inf
  INF Binaries/umi/QcomPkg/Drivers/DALSYSDxe/DALSYSDxe.inf
  INF Binaries/umi/QcomPkg/Drivers/HWIODxe/HWIODxe.inf
  INF Binaries/umi/QcomPkg/Drivers/ChipInfoDxe/ChipInfoDxe.inf
  INF Binaries/umi/QcomPkg/Drivers/PlatformInfoDxe/PlatformInfoDxe.inf
  # Attempt 05: retain ABL's MDP mapping; isolate the HALIOMMU attach hang.
  # Attempt 05 confirmed DisplayDxe returns Success without HALIOMMU.
  INF Binaries/umi/QcomPkg/Drivers/ULogDxe/ULogDxe.inf
  INF Binaries/umi/QcomPkg/Drivers/CmdDbDxe/CmdDbDxe.inf
  INF Binaries/umi/QcomPkg/Drivers/NpaDxe/NpaDxe.inf
  INF Binaries/umi/QcomPkg/Drivers/RpmhDxe/RpmhDxe.inf
  INF Binaries/umi/QcomPkg/Drivers/PdcDxe/PdcDxe.inf
  INF Binaries/umi/QcomPkg/Drivers/ClockDxe/ClockDxe.inf
  INF Binaries/umi/QcomPkg/Drivers/I2CDxe/I2CDxe.inf
  INF Binaries/umi/QcomPkg/Drivers/SPMIDxe/SPMIDxe.inf
  INF Binaries/umi/QcomPkg/Drivers/TLMMDxe/TLMMDxe.inf
  INF Binaries/umi/QcomPkg/Drivers/PmicDxe/PmicDxeLa.inf
  INF Binaries/umi/QcomPkg/Drivers/CPRDxe/CPRDxe.inf
  INF Binaries/umi/QcomPkg/Drivers/ShmBridgeDxe/ShmBridgeDxeLA.inf
  INF Binaries/umi/QcomPkg/Drivers/DisplayDxe/DisplayDxe.inf