#!/usr/bin/env python3
"""
Inject the trust cache bundle into the FAT32 payload image.

The payload.img is a 64 MiB FAT32 superfloppy (volume label "UMIXNU").
This script copies the trust cache bundle to
EFI/UniXNU/Payloads/kernel.macho.trustcache inside the FAT volume,
using mtools (mcopy) for in-place file injection.

usage: inject-trustcache.py --payload PATH --bundle PATH [--verify]
"""
import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

TRUSTCACHE_FAT_PATH = "::/EFI/UniXNU/Payloads/kernel.macho.trustcache"
EXPECTED_BUNDLE_SHA256 = "7416ca4f8377146626bb284e2133c76bee6cb4e3ee0af5d648b186235a7323a7"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--payload', type=Path, required=True,
                    help='FAT32 payload image (payload.img)')
    ap.add_argument('--bundle', type=Path, required=True,
                    help='Trust cache bundle (original-static-system.bundle)')
    ap.add_argument('--verify', action='store_true',
                    help='Verify FAT round-trip after injection')
    args = ap.parse_args()

    if not args.payload.is_file():
        print(f"error: payload not found: {args.payload}", file=sys.stderr)
        sys.exit(1)
    if not args.bundle.is_file():
        print(f"error: bundle not found: {args.bundle}", file=sys.stderr)
        sys.exit(1)

    bundle = args.bundle.read_bytes()
    bundle_sha = sha256(bundle)

    print(f"Payload:  {args.payload} ({args.payload.stat().st_size} bytes)")
    print(f"Bundle:   {args.bundle} ({len(bundle)} bytes)")
    print(f"SHA256:   {bundle_sha}")

    if bundle_sha != EXPECTED_BUNDLE_SHA256:
        print(f"ERROR: bundle SHA256 mismatch!", file=sys.stderr)
        print(f"  expected: {EXPECTED_BUNDLE_SHA256}", file=sys.stderr)
        print(f"  actual:   {bundle_sha}", file=sys.stderr)
        print(f"Refusing to inject — trust cache bundle does not match pinned hash.", file=sys.stderr)
        sys.exit(1)

    # Inject using mcopy
    print(f"\nInjecting -> {TRUSTCACHE_FAT_PATH}")
    subprocess.run([
        'mcopy', '-i', str(args.payload),
        str(args.bundle), TRUSTCACHE_FAT_PATH
    ], check=True)

    # List contents
    print("\nFAT32 contents:")
    subprocess.run([
        'mdir', '-i', str(args.payload), '::/EFI/UniXNU/Payloads/'
    ], check=True)

    # Verify round-trip
    if args.verify:
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.bundle') as tmp:
            tmp_path = Path(tmp.name)
            subprocess.run([
                'mtype', '-i', str(args.payload), TRUSTCACHE_FAT_PATH
            ], stdout=open(tmp_path, 'wb'), check=True)
            extracted = tmp_path.read_bytes()
            assert extracted == bundle, "FAT round-trip mismatch"
            print(f"\nRound-trip verification: PASS ({len(extracted)} bytes)")

    print("\nDone. Payload image is ready for boot image assembly.")


if __name__ == '__main__':
    main()