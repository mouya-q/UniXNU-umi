# Reproducing the umi development workspace

This is the source snapshot used for the Mi 10 bring-up through attempt 80. The
public `board.toml` and `umi_defconfig` still select the small source-only baseline.
The Hello configuration is assembled by the explicit bring-up tools; running
`unixnu build` with the default board file does not produce that configuration.

The tested host is macOS arm64 with Xcode command-line tools, Python 3.11 or newer,
Git, LLVM/LLD, device-tree-compiler and mtools. Host protocol tests use Clang's
AddressSanitizer and UndefinedBehaviorSanitizer. Linux builds are not qualified.

## Source checkouts

```sh
git clone https://github.com/reAAAq/UniXNU-umi
git clone https://github.com/reAAAq/uefi-umi
git clone https://github.com/UniXNU/UniXNU
git clone https://github.com/UniXNU/UniXNU-sheng
```

Use the commits in `UniXNU-umi/source-lock.json`. In each checkout, run
`git checkout <the-corresponding-commit>`; initialize the UEFI submodules needed
by the build (`Mu_Basecore`, `Common/Mu`, `Common/Mu_OEM_Sample`, `Silicium-ACPI`
and the OpenSSL submodule). Do not substitute current upstream `main`: upstream
has since split its drivers into repositories and changed several interfaces.

Create a separate workspace next to the clones:

```sh
python3 UniXNU-umi/bringup/setup-workspace.py \
  --workspace umi-work \
  --unixnu UniXNU --uefi uefi-umi --sheng UniXNU-sheng
cd umi-work
python3 devices/umi/scripts/check-umi-repository.py \
  --unixnu sources/UniXNU --out out/repository-check
python3 -m unittest discover -s tests -p 'test_umi_touch_trace.py'
```

The setup tool refuses an existing output directory or mismatched source pins.
It copies host scripts and tests, then links the three source checkouts and this
device repository. Firmware staging modifies the supplied UEFI checkout, so use
a dedicated checkout. Generated outputs stay under `umi-work/out/`.

## Source kernel baseline

```sh
python3 tools/build_umi_xnu.py --stage all --profile phone -j 6
```

This fetches the pinned public source dependencies, builds the support archives
and source kernel. It does not prelink Apple components or produce a complete
Hello image. The base is XNU `10063.141.1` / Darwin `23.6.0`; the original donor
kernel is `10063.142.1.703.8`. They are distinct version pins.

## Hello configuration and required local inputs

The tested phone profile adds prelinked crypto, PMGR service integration, GIC
diagnostics, eight-core startup, native UFS, authenticated OS/SystemOS mounting,
persistent Data, legacy display and the ST FTS/HID path. The source
entry points are `build_umi_xnu.py`, `build_umi_prelink.py`,
`build_umi_data_display.py`, `prepare_umi_uefi.py` and `build_umi_uefi.py`.

Full reproduction is not yet a single clean-clone command. These tools still
consume local generated records, including:

- Extracted iPad7,1 / 17.7.11 / 21H461 inputs, matching `ipsw-inputs.json`.
- ABI metadata under `out/umi/storage-abi/`, verified policy/trust-cache inputs,
  and matching reference Mach-O files used by the original driver bindings.
- A packed APFS Data seed and its adjacent identity JSON; OS/SystemOS image
  metadata; the corresponding root, prelink and ADT provenance records.
- The phone's measured boot/DTBO/FDT evidence and verified XBL import manifest.

Some archive recipes retain paths named `qemu-*` from the earlier ABI research.
These are input records, not a requirement to run QEMU for each phone build.
`--reuse-storage-from 55` is a local incremental-build shortcut and is not a
fresh-clone build instruction. Packaging those provenance-generation steps into
a self-contained build flow remains follow-up work.

For the currently tested firmware path, use `--display-profile inherited
--input-profile buttons --payload-profile ram --loader-profile darwinboot`.
The final root profile uses a 124 MiB payload and a `0x130000000` owned-memory
window on the tested 12 GiB handset, rather than the baseline board's 64 MiB
payload and 256 MiB window.

IPSW contents, trust caches, Data seeds, vendor firmware, generated kernels and
device dumps are intentionally absent. The original one-device partition-write
scripts are also absent: their serial and partition assumptions are not a
general installer. Re-measure another handset before any partition operation.

## Trust cache bundle

The payload step accepts a trust cache bundle with `--trust-cache` (or an
owner-signed one with `--owner-trust-cache`). The bundle is built entirely
inside this repository; no IPSW member larger than a few hundred kilobytes is
ever downloaded.

```sh
python3 scripts/fetch-ipsw-members.py StaticTrustCache Cryptex1,SystemTrustCache
python3 bringup/tools/prepare_umi_trustcache.py
```

`scripts/fetch-ipsw-members.py` opens the IPSW URL of `board.toml [ipsw]` as a
seekable HTTP-range stream (`RangeFile`) and resolves component names through
`BuildManifest.plist`. Only `BuildManifest.plist` (749 KiB) and the two
`*.dmg.trustcache` members (59,519 and 1,871 bytes) are fetched; the 6.37 GiB
archive stays on Apple's CDN. Every member is checked against the pins of
`board.toml [ipsw.sha256]` before it is used.

`bringup/tools/prepare_umi_trustcache.py` reads the cached members, verifies the
`j120ap` Erase build identity (`ApChipID 0x8011`, `ApBoardID 0x0C`), unpacks the
DER/IM4P wrappers (`trst` and `trcs`), validates the module headers and entry
counts, and writes `out/umi/trustcache/original-static-system.bundle`
(61,356 bytes, SHA-256 `7416ca4f8377146626bb284e2133c76bee6cb4e3ee0af5d648b186235a7323a7`).
The bundle header is `struct.pack("<3I", 2, 12, 12 + len(module0))` followed by
the two modules; `modules_modified` and `own_entries_added` are both `false`.

The CI workflow `.github/workflows/build-trustcache-umi.yml` runs the same two
steps, asserts the expected SHA-256 and, when invoked with
`workflow_dispatch.inputs.upload=true`, publishes the bundle as the
`unixnu-umi-trustcache-<run_attempt>` artifact (7 day retention). Its download
URL is the value to pass as `trust_cache_url` to UniXNU's `macos.yml` workflow.
Do not modify the module contents or add entries. A modified bundle fails the
payload step's `board.toml [payload]` allow-list and breaks the AMFI query that
`bringup/tools/check_umi_trustcache_qemu.py` qualifies.

## RAM-only boot image (no partition write)

The complete boot image for `fastboot boot` (temporary boot, no flash) is
assembled from three artifacts: the UEFI boot image (BootShim + SILICIUM_UEFI.fd),
the FAT32 payload image (kernel.macho + ADT), and the trust cache bundle.

### Prerequisites

Download these CI artifacts first:

| Artifact | CI source | Contents |
|---|---|---|
| `BootShim.bin` + `SILICIUM_UEFI.fd` | `build-uefi-umi.yml` Run #15 | 304 B shim + 3 MiB UEFI FD |
| `payload.img` | `macos.yml` Run #25 | 64 MiB FAT32 (kernel.macho + ADT) |
| `original-static-system.bundle` | `build-trustcache-umi.yml` Run #6 | 61,356 B trust cache bundle |

### Assembly

```sh
# 1. Inject trust cache into the FAT32 payload image
python3 scripts/inject-trustcache.py \
  --payload payload.img \
  --bundle original-static-system.bundle \
  --verify

# 2. Assemble the complete boot image
python3 scripts/make-umi-bootimg.py \
  --bootshim BootShim.bin \
  --uefi-fd SILICIUM_UEFI.fd \
  --payload payload.img \
  --output umi-xnu-boot.img
```

The output `umi-xnu-boot.img` (~65 MiB) is a standard Android boot image v1:

```
Header (4 KiB, page_size=4096, header_version=1)
  kernel_size:   gzip(BootShim.bin + SILICIUM_UEFI.fd)
  ramdisk_size:  FAT32 payload (64 MiB)
  ramdisk_addr:  0xA0000000   ← UmiRamPayloadDxe BOOT_BASE
  kernel_addr:   0x10008000
Kernel (gzip, ~177 pages)
Ramdisk (FAT32, 16384 pages)
```

### Boot flow

```
fastboot boot umi-xnu-boot.img
    ↓  (no partition is written)
ABL decompresses kernel → BootShim (304 B) at 0x10008000
ABL loads ramdisk → 0xA0000000, records linux,initrd-start/end in DTB /chosen
    ↓
BootShim: copies UEFI FD to 0x9FC00000, flushes cache, jumps to SEC
    ↓
UEFI (Mu-Silicium): UmiRamPayloadDxe reads DTB /chosen initrd range
    → finds FAT32 volume at 0xA0000000 (256 MiB window)
    → mounts as read-only block device
    ↓
DarwinBoot: reads kernel.macho + kernel.macho.adt + kernel.macho.trustcache
    from FAT32 → launches XNU with -v keepsyms=1 kt_fixed_zones=120
    ↓
Reboot → ABL loads original boot_a → Android (nothing was flashed)
```

### Returning to Android

Just reboot the phone. `fastboot boot` loads the image into RAM only; the
boot partition and userdata are untouched. After a reboot, ABL reads the
original Android kernel from the boot partition and starts normally.

If the phone was booted into fastboot mode (power + volume down), use
`fastboot reboot` to return to Android. If the phone was booted from a
`fastboot boot` session, a normal reboot (or power + volume down → fastboot
→ `fastboot reboot`) returns to Android.

## Touch and log checks

Attempt 80 uses `umi-fts-gpi=1` for native GPI DMA I²C. The startup path enables
the board's native always-on PM8150B GPIO5 rail before the FTS supply/reset
sequence, requiring the tested PMIC/pin profile and EE0 ownership and verifying
the enable readback after 4 ms. Do not reuse these board constants on other devices.
The native reference is the
[LineageOS SM8250 kernel at 71b13e6](https://github.com/LineageOS/android_kernel_xiaomi_sm8250/tree/71b13e62f057a649b77fe4062feb73ee72ad609c);
source hashes are recorded under `package/touch/*-reference.json`.
Those reference files retain their build-time status for provenance; current
hardware results are recorded separately in `docs/validation.json`.

`tools/check_umi_touch.py --attempt <number>` runs the C++ protocol/fault tests,
CRC decoder checks and RAM-console budget check. Its final layout audit requires
the original public ST parser at the path used by
`tools/check_umi_fts_sysinfo_layout.py`. Obtain `ftsCore.c` and `ftsCore.h` from
[MiCode umi-q-oss at db67ca6](https://github.com/MiCode/Xiaomi_Kernel_OpenSource/tree/db67ca6001320efc1f945c270635434fc403a9d4/drivers/input/touchscreen/fts_521/fts_lib);
the script verifies the parser hash before using it.

`tools/decode_umi_xnu_trace.py` and the `umi_*_trace.py` modules decode retained
RAM logs. Incomplete records remain incomplete; a successful HID attachment is
not counted as a physical touch report. Tests that consume generated payloads
or device evidence require those local inputs and are not clean-clone smoke tests.