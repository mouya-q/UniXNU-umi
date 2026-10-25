#!/usr/bin/env python3
"""
Assemble a complete Android boot image for `fastboot boot` (temporary boot,
no partition write). The image contains:

  kernel  = gzip(BootShim.bin + SILICIUM_UEFI.fd)
  ramdisk = FAT32 payload image (kernel.macho + ADT + trust cache)

After `fastboot boot umi-xnu-boot.img`, ABL loads the kernel to kernel_addr,
the ramdisk to ramdisk_addr (0xA0000000), and records linux,initrd-start/end
in the DTB /chosen. UmiRamPayloadDxe reads those values to find the FAT32
volume in RAM. Reboot returns to Android — nothing was flashed.

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

# Memory map constants (must match UmiRamPayloadDxe and board.toml)
PAGE_SIZE = 4096
KERNEL_ADDR = 0x10008000      # board.toml kernel_offset
RAMDISK_ADDR = 0xA0000000     # UmiRamPayloadDxe BOOT_BASE
SECOND_ADDR = 0x00000000
ANDROID_MAGIC = b'ANDROID!'


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_boot_image(bootshim: bytes, uefi_fd: bytes, payload: bytes) -> bytes:
    """Assemble an Android boot image v1 with kernel + ramdisk."""
    blob = bootshim + uefi_fd
    kernel_gz = gzip.compress(blob, 6)

    kernel_size = len(kernel_gz)
    ramdisk_size = len(payload)

    k_pages = (kernel_size + PAGE_SIZE - 1) // PAGE_SIZE
    r_pages = (ramdisk_size + PAGE_SIZE - 1) // PAGE_SIZE
    total_size = PAGE_SIZE * (1 + k_pages + r_pages)

    # Build header (v1, padded to one page)
    header = bytearray(PAGE_SIZE)
    header[0:8] = ANDROID_MAGIC
    struct.pack_into('<I', header, 8, kernel_size)
    struct.pack_into('<I', header, 12, KERNEL_ADDR)
    struct.pack_into('<I', header, 16, ramdisk_size)
    struct.pack_into('<I', header, 20, RAMDISK_ADDR)
    struct.pack_into('<I', header, 24, 0)              # second_size
    struct.pack_into('<I', header, 28, SECOND_ADDR)     # second_addr
    struct.pack_into('<I', header, 32, 0)               # tags_addr (no DTB in image)
    struct.pack_into('<I', header, 36, PAGE_SIZE)
    struct.pack_into('<I', header, 40, 1)               # header_version
    # v1 fields at offset 1632+
    struct.pack_into('<I', header, 1632, 0)              # recovery_dtbo_size
    struct.pack_into('<Q', header, 1636, 0)              # recovery_dtbo_addr
    struct.pack_into('<I', header, 1644, PAGE_SIZE)      # header_size

    image = bytearray(total_size)
    image[0:PAGE_SIZE] = header
    image[PAGE_SIZE:PAGE_SIZE + kernel_size] = kernel_gz
    ramdisk_offset = PAGE_SIZE + k_pages * PAGE_SIZE
    image[ramdisk_offset:ramdisk_offset + ramdisk_size] = payload

    return bytes(image)


def verify_boot_image(img: bytes, bootshim: bytes, uefi_fd: bytes, payload: bytes):
    """Round-trip verify the assembled boot image."""
    assert img[:8] == ANDROID_MAGIC, "bad magic"
    ks = struct.unpack_from('<I', img, 8)[0]
    rs = struct.unpack_from('<I', img, 16)[0]
    ps = struct.unpack_from('<I', img, 36)[0]
    hv = struct.unpack_from('<I', img, 40)[0]
    ra = struct.unpack_from('<I', img, 20)[0]

    assert ps == PAGE_SIZE, f"page_size mismatch: {ps}"
    assert hv == 1, f"header_version mismatch: {hv}"
    assert ra == RAMDISK_ADDR, f"ramdisk_addr mismatch: 0x{ra:x}"

    # Kernel decompress
    d = zlib.decompressobj(16 + zlib.MAX_WBITS)
    dc = d.decompress(img[PAGE_SIZE:PAGE_SIZE + ks])
    assert dc[:len(bootshim)] == bootshim, "BootShim mismatch"
    assert dc[len(bootshim):len(bootshim) + len(uefi_fd)] == uefi_fd, "UEFI FD mismatch"

    # Ramdisk round-trip
    k_pages = (ks + ps - 1) // ps
    ro = PAGE_SIZE + k_pages * ps
    extracted = img[ro:ro + rs]
    assert extracted == payload, "ramdisk payload mismatch"

    return {
        "kernel_size": ks,
        "ramdisk_size": rs,
        "page_size": ps,
        "header_version": hv,
        "ramdisk_addr": ra,
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

    print(f"BootShim:    {len(bootshim):>10} bytes  ({args.bootshim})")
    print(f"UEFI FD:     {len(uefi_fd):>10} bytes  ({args.uefi_fd})")
    print(f"Payload:     {len(payload):>10} bytes  ({args.payload})")

    img = build_boot_image(bootshim, uefi_fd, payload)
    info = verify_boot_image(img, bootshim, uefi_fd, payload)

    args.output.write_bytes(img)

    print(f"\n=== Boot image v1 ===")
    print(f"kernel_size:   {info['kernel_size']}")
    print(f"ramdisk_size:  {info['ramdisk_size']}")
    print(f"ramdisk_addr:  0x{info['ramdisk_addr']:08x}")
    print(f"page_size:     {info['page_size']}")
    print(f"total bytes:   {info['total_bytes']} ({info['total_bytes']/1024/1024:.1f} MB)")
    print(f"sha256:        {info['sha256']}")
    print(f"\nOutput: {args.output}")

    print(f"\nUsage:")
    print(f"  fastboot boot {args.output}")
    print(f"  # Reboot to return to Android — nothing was flashed.")


if __name__ == '__main__':
    main()
