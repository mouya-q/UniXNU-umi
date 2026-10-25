#!/usr/bin/env python3
"""
Assemble a complete Android boot image v1 for `fastboot boot` (temporary boot,
no partition write). The image contains:

  kernel  = gzip(BootShim.bin + SILICIUM_UEFI.fd)
  ramdisk = FAT32 payload image (kernel.macho + ADT + trust cache)

After `fastboot boot umi-xnu-boot.img`, ABL loads the kernel to kernel_addr,
the ramdisk to ramdisk_addr (0xA0000000), and records linux,initrd-start/end
in the DTB /chosen. UmiRamPayloadDxe reads those values to find the FAT32
volume in RAM. Reboot returns to Android — nothing was flashed.

Boot image header conforms to AOSP boot_img_hdr_v1 definition:
  https://android.googlesource.com/platform/system/tools/mkbootimg/+refs/heads/master/include/bootimg/bootimg.h

usage: make-umi-bootimg.py [--bootshim PATH] [--uefi-fd PATH]
                           [--payload PATH] [--output PATH]
"""
import argparse
import gzip
import hashlib
import struct
import sys
import zlib
from pathlib import Path

# Memory map constants — must match the known-good Mu-umi-0.img baseline
# that ABL actually accepts on Xiaomi Mi 10 (umi, SM8250).
#   page_size   = 2048  (ABL rejects 4096)
#   base        = 0x10000000
#   kernel_addr = base + 0x00008000 = 0x10008000
#   tags_addr   = base + 0x00000100 = 0x10000100  (ABL requires non-zero)
#   ramdisk_addr = 0xA0000000  (UmiRamPayloadDxe BOOT_BASE; ABL loads 64 MiB
#                              payload here; UmiRamPayloadDxe scans this window)
PAGE_SIZE = 2048
BASE_ADDR = 0x10000000
KERNEL_ADDR = 0x10008000
TAGS_ADDR = 0x10000100
RAMDISK_ADDR = 0xA0000000
SECOND_ADDR = 0x00000000
ANDROID_MAGIC = b'ANDROID!'

# AOSP boot_img_hdr_v1 struct size.
# v0 fields: 1632 bytes (magic + sizes/addrs + os_version + name + cmdline +
#             id + extra_cmdline).  v1 adds recovery_dtbo_size(4) +
#             recovery_dtbo_addr(8) + header_size(4) = 16 bytes.
# Total v1 struct = 1648 bytes = 0x670.
HEADER_SIZE_V1 = 1648           # 0x670

# FAT32 payload invariants (must match payload.img from CI Run #25)
EXPECTED_PAYLOAD_SIZE = 67108864   # 64 MiB
EXPECTED_TRUSTCACHE_SHA256 = "7416ca4f8377146626bb284e2133c76bee6cb4e3ee0af5d648b186235a7323a7"
TRUSTCACHE_FAT_PATH = "::/EFI/UniXNU/Payloads/kernel.macho.trustcache"

# Kernel decompressed invariants
EXPECTED_BOOTSHIM_SIZE = 304
EXPECTED_UEFI_FD_SIZE = 3145728   # 3 MiB


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _pad_to_page(data: bytes, page_size: int = PAGE_SIZE) -> bytes:
    """Pad *data* with zeros to the next page boundary."""
    remainder = len(data) % page_size
    if remainder == 0:
        return b''
    return b'\x00' * (page_size - remainder)


def build_boot_image(bootshim: bytes, uefi_fd: bytes, payload: bytes) -> bytes:
    """Assemble an Android boot image v1 with kernel + ramdisk."""
    blob = bootshim + uefi_fd
    kernel_gz = gzip.compress(blob, 6)

    kernel_size = len(kernel_gz)
    ramdisk_size = len(payload)

    k_pages = (kernel_size + PAGE_SIZE - 1) // PAGE_SIZE
    r_pages = (ramdisk_size + PAGE_SIZE - 1) // PAGE_SIZE
    total_size = PAGE_SIZE * (1 + k_pages + r_pages)

    # Build header (v1, padded to one page at PAGE_SIZE)
    header = bytearray(PAGE_SIZE)
    header[0:8] = ANDROID_MAGIC
    struct.pack_into('<I', header, 8, kernel_size)        # kernel_size
    struct.pack_into('<I', header, 12, KERNEL_ADDR)       # kernel_addr
    struct.pack_into('<I', header, 16, ramdisk_size)      # ramdisk_size
    struct.pack_into('<I', header, 20, RAMDISK_ADDR)      # ramdisk_addr
    struct.pack_into('<I', header, 24, 0)                 # second_size
    struct.pack_into('<I', header, 28, SECOND_ADDR)       # second_addr
    struct.pack_into('<I', header, 32, TAGS_ADDR)         # tags_addr (ABL requires non-zero)
    struct.pack_into('<I', header, 36, PAGE_SIZE)         # page_size
    struct.pack_into('<I', header, 40, 1)                 # header_version
    # v1 additional fields start at offset 1632
    struct.pack_into('<I', header, 1632, 0)               # recovery_dtbo_size
    struct.pack_into('<Q', header, 1636, 0)               # recovery_dtbo_addr
    struct.pack_into('<I', header, 1644, HEADER_SIZE_V1)  # header_size = 0x670

    # Compute AOSP-standard id = SHA256(header_padding + kernel + kernel_padding
    #                                  + ramdisk + ramdisk_padding)[:32]
    # This matches what mkbootimg produces and what ABL expects.
    sha = hashlib.sha256()
    sha.update(b'\x00' * (PAGE_SIZE - HEADER_SIZE_V1))   # header padding
    sha.update(kernel_gz)                                 # kernel data
    sha.update(_pad_to_page(kernel_gz))                   # kernel padding
    sha.update(payload)                                   # ramdisk data
    sha.update(_pad_to_page(payload))                     # ramdisk padding
    img_id = sha.digest()[:32]
    header[576:608] = img_id                              # id (8 × uint32 = 32 bytes)

    image = bytearray(total_size)
    image[0:PAGE_SIZE] = header
    image[PAGE_SIZE:PAGE_SIZE + kernel_size] = kernel_gz
    ramdisk_offset = PAGE_SIZE + k_pages * PAGE_SIZE
    image[ramdisk_offset:ramdisk_offset + ramdisk_size] = payload

    return bytes(image)


def verify_boot_image(img: bytes, bootshim: bytes, uefi_fd: bytes, payload: bytes):
    """Round-trip verify the assembled boot image against AOSP v1 spec."""
    # --- Header field validation ---
    assert img[:8] == ANDROID_MAGIC, f"bad magic: {img[:8]!r}"

    ks = struct.unpack_from('<I', img, 8)[0]       # kernel_size
    ka = struct.unpack_from('<I', img, 12)[0]      # kernel_addr
    rs = struct.unpack_from('<I', img, 16)[0]      # ramdisk_size
    ra = struct.unpack_from('<I', img, 20)[0]      # ramdisk_addr
    ss = struct.unpack_from('<I', img, 24)[0]      # second_size
    sa = struct.unpack_from('<I', img, 28)[0]      # second_addr
    ta = struct.unpack_from('<I', img, 32)[0]      # tags_addr
    ps = struct.unpack_from('<I', img, 36)[0]      # page_size
    hv = struct.unpack_from('<I', img, 40)[0]      # header_version
    rds = struct.unpack_from('<I', img, 1632)[0]   # recovery_dtbo_size
    rda = struct.unpack_from('<Q', img, 1636)[0]   # recovery_dtbo_addr
    hs = struct.unpack_from('<I', img, 1644)[0]    # header_size

    assert ps == PAGE_SIZE, f"page_size mismatch: {ps} != {PAGE_SIZE}"
    assert hv == 1, f"header_version mismatch: {hv}"
    assert hs == HEADER_SIZE_V1, (
        f"header_size mismatch: {hs} (0x{hs:x}) != {HEADER_SIZE_V1} (0x{HEADER_SIZE_V1:x}). "
        f"boot_img_hdr_v1 struct size must be 0x670 per AOSP definition."
    )
    assert ra == RAMDISK_ADDR, f"ramdisk_addr mismatch: 0x{ra:x} != 0x{RAMDISK_ADDR:x}"
    assert ka == KERNEL_ADDR, f"kernel_addr mismatch: 0x{ka:x} != 0x{KERNEL_ADDR:x}"
    assert ss == 0, f"second_size should be 0, got {ss}"
    assert ta == TAGS_ADDR, (
        f"tags_addr mismatch: 0x{ta:08x} != 0x{TAGS_ADDR:08x}. "
        f"ABL requires tags_addr = base(0x10000000) + 0x100."
    )
    assert rds == 0, f"recovery_dtbo_size should be 0, got {rds}"
    assert rda == 0, f"recovery_dtbo_addr should be 0, got 0x{rda:x}"

    # --- id field: must be non-zero (AOSP SHA256 of image payload) ---
    id_bytes = img[576:608]
    assert id_bytes != b'\x00' * 32, (
        "id field is all zeros — ABL may reject image. "
        "id must be SHA256(header_pad + kernel + kernel_pad + ramdisk + ramdisk_pad)[:32]."
    )

    # --- Total image size must be an exact page multiple ---
    expected_total = PAGE_SIZE * (1 + (ks + ps - 1) // ps + (rs + ps - 1) // ps)
    assert len(img) == expected_total, (
        f"image size {len(img)} != expected {expected_total} "
        f"(header + kernel pages + ramdisk pages)"
    )
    assert len(img) % ps == 0, f"image size {len(img)} not aligned to page_size {ps}"

    # --- Kernel region: must start at page boundary, end within declared range ---
    kernel_region = img[ps:ps + ks]
    assert kernel_region[:2] == b'\x1f\x8b', (
        f"kernel data does not start with gzip magic 0x1f8b, got {kernel_region[:2].hex()}"
    )

    # --- Kernel decompression: exact stream, no trailing garbage ---
    d = zlib.decompressobj(16 + zlib.MAX_WBITS)
    dc = d.decompress(kernel_region)
    unused = d.unused_data
    assert len(unused) == 0, (
        f"gzip stream has {len(unused)} trailing bytes after decompressed data"
    )
    expected_decompressed = len(bootshim) + len(uefi_fd)
    assert len(dc) == expected_decompressed, (
        f"decompressed kernel size {len(dc)} != expected {expected_decompressed} "
        f"(BootShim {len(bootshim)} + UEFI FD {len(uefi_fd)})"
    )
    assert dc[:len(bootshim)] == bootshim, "BootShim bytes mismatch in decompressed kernel"
    assert dc[len(bootshim):] == uefi_fd, "UEFI FD bytes mismatch in decompressed kernel"

    # --- Ramdisk round-trip: exact byte-for-byte match ---
    k_pages = (ks + ps - 1) // ps
    ro = ps + k_pages * ps
    ramdisk_end = ro + rs
    assert ramdisk_end == len(img), (
        f"ramdisk end 0x{ramdisk_end:x} != image end 0x{len(img):x}; "
        f"trailing {len(img) - ramdisk_end} bytes after ramdisk"
    )
    extracted = img[ro:ro + rs]
    assert extracted == payload, "ramdisk payload byte mismatch"

    return {
        "kernel_size": ks,
        "ramdisk_size": rs,
        "page_size": ps,
        "header_version": hv,
        "header_size": hs,
        "kernel_addr": ka,
        "ramdisk_addr": ra,
        "tags_addr": ta,
        "ramdisk_offset": ro,
        "decompressed_kernel": len(dc),
        "sha256": sha256(img),
        "total_bytes": len(img),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--bootshim', type=Path,
                    default=Path('/sdcard/Download/umi-uefi-run15/BootShim.bin'))
    ap.add_argument('--uefi-fd', type=Path,
                    default=Path('/sdcard/Download/umi-uefi-run15/SILICIUM_UEFI.fd'))
    ap.add_argument('--payload', type=Path,
                    default=Path('/sdcard/Download/umi-xnu-artifacts-run25/payload.img'))
    ap.add_argument('--output', type=Path,
                    default=Path('/sdcard/Download/umi-xnu-boot.img'))
    args = ap.parse_args()

    bootshim = args.bootshim.read_bytes()
    uefi_fd = args.uefi_fd.read_bytes()
    payload = args.payload.read_bytes()

    # Pre-build input validation
    assert len(bootshim) == EXPECTED_BOOTSHIM_SIZE, (
        f"BootShim size {len(bootshim)} != expected {EXPECTED_BOOTSHIM_SIZE}"
    )
    assert len(uefi_fd) == EXPECTED_UEFI_FD_SIZE, (
        f"UEFI FD size {len(uefi_fd)} != expected {EXPECTED_UEFI_FD_SIZE}"
    )
    assert len(payload) == EXPECTED_PAYLOAD_SIZE, (
        f"Payload size {len(payload)} != expected {EXPECTED_PAYLOAD_SIZE}"
    )

    print(f"BootShim:    {len(bootshim):>10} bytes  ({args.bootshim})")
    print(f"UEFI FD:     {len(uefi_fd):>10} bytes  ({args.uefi_fd})")
    print(f"Payload:     {len(payload):>10} bytes  ({args.payload})")

    img = build_boot_image(bootshim, uefi_fd, payload)
    info = verify_boot_image(img, bootshim, uefi_fd, payload)

    args.output.write_bytes(img)

    print(f"\n=== Boot image v1 (AOSP-conformant) ===")
    print(f"kernel_size:     {info['kernel_size']}")
    print(f"kernel_addr:     0x{info['kernel_addr']:08x}")
    print(f"ramdisk_size:    {info['ramdisk_size']}")
    print(f"ramdisk_addr:    0x{info['ramdisk_addr']:08x}")
    print(f"page_size:       {info['page_size']}")
    print(f"header_version:  {info['header_version']}")
    print(f"header_size:     {info['header_size']} (0x{info['header_size']:x})")
    print(f"tags_addr:       0x{info['tags_addr']:08x}")
    print(f"total bytes:     {info['total_bytes']} ({info['total_bytes']/1024/1024:.1f} MB)")
    print(f"sha256:          {info['sha256']}")
    print(f"\nOutput: {args.output}")

    print(f"\nUsage:")
    print(f"  fastboot boot {args.output}")
    print(f"  # Reboot to return to Android — nothing was flashed.")


if __name__ == '__main__':
    main()