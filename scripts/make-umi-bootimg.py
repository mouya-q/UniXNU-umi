#!/usr/bin/env python3
"""
Assemble an Android boot image v1 for `fastboot boot` (temporary boot,
no partition write).  Mirrors the upstream unixnu bootimg.build() flow:

  kernel  = gzip(BootShim.bin + SILICIUM_UEFI.fd) + DTB    (Image.gz-dtb)
  ramdisk = FAT32 payload image (or empty)

The DTB is appended after the gzip stream — this is the Image.gz-dtb
format that ABL expects.  The boot image header is produced by the
Mu-Silicium mkbootimg.py (AOSP), not hand-written, guaranteeing format
fidelity.

Parameters from board.toml [bootimg.image]:
  header_version = 1, pagesize = 4096, base = 0,
  kernel_offset = 0x8000, tags_offset = 0x1e00000

ramdisk_offset is NOT passed (upstream doesn't either); mkbootimg uses
its default 0x01000000.

usage: make-umi-bootimg.py [--bootshim PATH] [--uefi-fd PATH]
                            [--dtb PATH] [--payload PATH] [--output PATH]
"""
import argparse
import gzip
import hashlib
import json
import os
import struct
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path

# board.toml [bootimg.image] constants
PAGE_SIZE = 4096
BASE_ADDR = 0
KERNEL_OFFSET = 0x8000
TAGS_OFFSET = 0x1e00000
HEADER_VERSION = 1

# Input size invariants (CI-verified)
EXPECTED_BOOTSHIM_SIZE = 304
EXPECTED_UEFI_FD_SIZE = 3_145_728    # 3 MiB
EXPECTED_PAYLOAD_SIZE = 67_108_864   # 64 MiB

# Mu-Silicium mkbootimg.py
MKBOOTIMG = Path(__file__).resolve().parents[1] / (
    "uefi-umi-main/Resources/Scripts/mkbootimg.py")

FDT_MAGIC = 0xd00dfeed


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verify_kernel_dtb(kernel_blob: bytes, combined: bytes, dtb: bytes):
    """Verify the Image.gz-dtb: gzip stream + appended DTB."""
    assert kernel_blob[:2] == b'\x1f\x8b', (
        f"kernel does not start with gzip magic, got {kernel_blob[:2].hex()}")
    d = zlib.decompressobj(16 + zlib.MAX_WBITS)
    decompressed = d.decompress(kernel_blob)
    assert d.eof, "gzip stream did not end cleanly"
    assert d.unused_data == dtb, (
        f"trailing data after gzip ({len(d.unused_data)} bytes) "
        f"!= DTB ({len(dtb)} bytes)")
    assert decompressed == combined, (
        "decompressed kernel != BootShim + UEFI FD")


def verify_boot_image(img: bytes, kernel_blob: bytes, ramdisk: bytes,
                      combined: bytes, dtb: bytes):
    """Round-trip verify the assembled boot image against AOSP v1 spec."""
    assert img[:8] == b'ANDROID!', f"bad magic: {img[:8]!r}"

    ks = struct.unpack_from('<I', img, 8)[0]
    ka = struct.unpack_from('<I', img, 12)[0]
    rs = struct.unpack_from('<I', img, 16)[0]
    ra = struct.unpack_from('<I', img, 20)[0]
    ss = struct.unpack_from('<I', img, 24)[0]
    ta = struct.unpack_from('<I', img, 32)[0]
    ps = struct.unpack_from('<I', img, 36)[0]
    hv = struct.unpack_from('<I', img, 40)[0]
    hs = struct.unpack_from('<I', img, 1644)[0]

    assert ps == PAGE_SIZE, f"page_size mismatch: {ps} != {PAGE_SIZE}"
    assert hv == HEADER_VERSION, f"header_version mismatch: {hv}"
    assert hs == 1648, f"header_size mismatch: {hs} != 1648"
    assert ka == BASE_ADDR + KERNEL_OFFSET, (
        f"kernel_addr mismatch: 0x{ka:x} != 0x{BASE_ADDR + KERNEL_OFFSET:x}")
    assert ta == BASE_ADDR + TAGS_OFFSET, (
        f"tags_addr mismatch: 0x{ta:x} != 0x{BASE_ADDR + TAGS_OFFSET:x}")
    assert ss == 0, f"second_size should be 0, got {ss}"

    k_pages = (ks + ps - 1) // ps
    r_pages = (rs + ps - 1) // ps if rs else 0
    expected_total = ps * (1 + k_pages + r_pages)
    assert len(img) == expected_total, (
        f"image size {len(img)} != expected {expected_total}")

    kernel_region = img[ps:ps + ks]
    verify_kernel_dtb(kernel_region, combined, dtb)

    if rs:
        ro = ps + k_pages * ps
        extracted = img[ro:ro + rs]
        assert extracted == ramdisk, "ramdisk payload mismatch"

    return {
        "kernel_size": ks,
        "kernel_addr": ka,
        "ramdisk_size": rs,
        "ramdisk_addr": ra,
        "page_size": ps,
        "header_version": hv,
        "header_size": hs,
        "tags_addr": ta,
        "sha256": sha256(img),
        "total_bytes": len(img),
    }


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--bootshim', type=Path,
                    default=Path('/sdcard/Download/umi-uefi-run15/BootShim.bin'))
    ap.add_argument('--uefi-fd', type=Path,
                    default=Path('/sdcard/Download/umi-uefi-run15/SILICIUM_UEFI.fd'))
    ap.add_argument('--dtb', type=Path,
                    default=Path('/sdcard/Download/umi-live.dtb'),
                    help='Device tree blob (e.g. /sys/firmware/fdt dump)')
    ap.add_argument('--payload', type=Path,
                    default=Path('/sdcard/Download/umi-xnu-artifacts-run25/payload.img'))
    ap.add_argument('--output', type=Path,
                    default=Path('/sdcard/Download/umi-xnu-boot.img'))
    ap.add_argument('--mkbootimg', type=Path, default=MKBOOTIMG,
                    help='Path to mkbootimg.py (Mu-Silicium)')
    args = ap.parse_args()

    bootshim = args.bootshim.read_bytes()
    uefi_fd = args.uefi_fd.read_bytes()
    dtb = args.dtb.read_bytes()
    payload = args.payload.read_bytes()

    assert len(bootshim) == EXPECTED_BOOTSHIM_SIZE, (
        f"BootShim size {len(bootshim)} != {EXPECTED_BOOTSHIM_SIZE}")
    assert len(uefi_fd) == EXPECTED_UEFI_FD_SIZE, (
        f"UEFI FD size {len(uefi_fd)} != {EXPECTED_UEFI_FD_SIZE}")
    assert len(payload) == EXPECTED_PAYLOAD_SIZE, (
        f"Payload size {len(payload)} != {EXPECTED_PAYLOAD_SIZE}")

    magic = struct.unpack_from('>I', dtb, 0)[0]
    total_size = struct.unpack_from('>I', dtb, 4)[0]
    assert magic == FDT_MAGIC, f"DTB magic 0x{magic:08x} != 0x{FDT_MAGIC:08x}"
    assert total_size <= len(dtb), (
        f"DTB total_size {total_size} > file size {len(dtb)}")
    if total_size < len(dtb):
        print(f"  Truncating DTB from {len(dtb)} to {total_size} bytes")
        dtb = dtb[:total_size]

    print(f"BootShim:    {len(bootshim):>10} bytes  ({args.bootshim})")
    print(f"UEFI FD:     {len(uefi_fd):>10} bytes  ({args.uefi_fd})")
    print(f"DTB:         {len(dtb):>10} bytes  ({args.dtb})")
    print(f"Payload:     {len(payload):>10} bytes  ({args.payload})")

    # kernel = gzip(BootShim + UEFI FD) + DTB  (Image.gz-dtb)
    combined = bootshim + uefi_fd
    kernel_gz = gzip.compress(combined, mtime=0)
    kernel_blob = kernel_gz + dtb

    print(f"\nKernel (Image.gz-dtb): {len(kernel_blob)} bytes")
    print(f"  gzip stream: {len(kernel_gz)} bytes")
    print(f"  appended DTB: {len(dtb)} bytes")

    verify_kernel_dtb(kernel_blob, combined, dtb)
    print("  Image.gz-dtb round-trip: OK")

    mkbootimg = args.mkbootimg
    if not mkbootimg.is_file():
        print(f"ERROR: mkbootimg.py not found at {mkbootimg}")
        sys.exit(1)

    with tempfile.TemporaryDirectory(prefix='umi-bootimg-') as tmp:
        tmpdir = Path(tmp)
        kernel_path = tmpdir / 'Image.gz-dtb'
        ramdisk_path = tmpdir / 'ramdisk'
        output_path = tmpdir / 'boot.img'

        kernel_path.write_bytes(kernel_blob)
        ramdisk_path.write_bytes(payload)

        cmd = [
            sys.executable, str(mkbootimg),
            '--kernel', str(kernel_path),
            '--ramdisk', str(ramdisk_path),
            '--header_version', str(HEADER_VERSION),
            '--pagesize', str(PAGE_SIZE),
            '--base', str(BASE_ADDR),
            '--kernel_offset', str(KERNEL_OFFSET),
            '--tags_offset', str(TAGS_OFFSET),
            '-o', str(output_path),
        ]
        print(f"\nmkbootimg command:")
        print(f"  {' '.join(cmd)}")

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"mkbootimg FAILED (exit {result.returncode})")
            print(f"  stdout: {result.stdout}")
            print(f"  stderr: {result.stderr}")
            sys.exit(1)
        if result.stdout.strip():
            print(f"mkbootimg output: {result.stdout.strip()}")

        img = output_path.read_bytes()

    info = verify_boot_image(img, kernel_blob, payload, combined, dtb)

    args.output.write_bytes(img)

    print(f"\n=== Boot image v1 (upstream-aligned, DTB-embedded) ===")
    print(f"kernel_size:     {info['kernel_size']}")
    print(f"kernel_addr:     0x{info['kernel_addr']:08x}")
    print(f"ramdisk_size:    {info['ramdisk_size']}")
    print(f"ramdisk_addr:    0x{info['ramdisk_addr']:08x}")
    print(f"page_size:       {info['page_size']}")
    print(f"header_version:  {info['header_version']}")
    print(f"header_size:     {info['header_size']} (0x{info['header_size']:x})")
    print(f"tags_addr:       0x{info['tags_addr']:08x}")
    print(f"total bytes:     {info['total_bytes']} "
          f"({info['total_bytes']/1024/1024:.1f} MB)")
    print(f"sha256:          {info['sha256']}")
    print(f"\nOutput: {args.output}")
    print(f"\nUsage:")
    print(f"  fastboot boot {args.output}")
    print(f"  # Reboot to return to Android — nothing was flashed.")


if __name__ == '__main__':
    main()