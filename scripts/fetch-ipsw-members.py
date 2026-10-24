#!/usr/bin/env python3
"""Fetch individual members of the target IPSW using HTTP range requests.

An IPSW is a multi-gigabyte zip archive. Only the members that the board asks
for are downloaded; the archive is read through a seekable HTTP-range stream,
so the IPSW itself is never fetched as a whole.

Members are cached under out/umi-xnu/ipsw/<build>/ and checked against the
pins of board.toml [ipsw.sha256]. BuildManifest.plist is always fetched because
the device identity (product, build, device class) is resolved from it.
"""
import hashlib
import json
import plistlib
import sys
import time
import tomllib
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHUNK = 8 << 20


class Error(Exception):
    pass


class RangeFile:
    """A read-only, seekable view of a remote file fetched with HTTP range requests."""

    def __init__(self, url, block=CHUNK, retries=4):
        self.url, self.block, self.retries = url, block, retries
        self.position = 0
        self.cache = {}
        request = urllib.request.Request(url, method='HEAD')
        with urllib.request.urlopen(request, timeout=60) as response:
            self.size = int(response.headers['Content-Length'])
        probe = urllib.request.Request(url, headers={'Range': 'bytes=0-0'})
        with urllib.request.urlopen(probe, timeout=60) as response:
            if response.status != 206:
                raise Error(f'{url} does not support range requests')

    def __len__(self):
        return self.size

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.position

    def seek(self, offset, whence=0):
        if whence == 0:
            self.position = offset
        elif whence == 1:
            self.position += offset
        elif whence == 2:
            self.position = self.size + offset
        else:
            raise ValueError(f'invalid whence: {whence}')
        return self.position

    def _block(self, index):
        if index not in self.cache:
            if len(self.cache) >= 4:
                self.cache.pop(next(iter(self.cache)))
            start = index * self.block
            end = min(start + self.block, self.size) - 1
            for attempt in range(self.retries):
                try:
                    request = urllib.request.Request(
                        self.url, headers={'Range': f'bytes={start}-{end}'})
                    with urllib.request.urlopen(request, timeout=120) as response:
                        data = response.read()
                    if len(data) != end - start + 1:
                        raise OSError('short range response')
                    self.cache[index] = data
                    break
                except (OSError, urllib.error.URLError):
                    if attempt == self.retries - 1:
                        raise
                    time.sleep(2 ** attempt)
        return self.cache[index]

    def read(self, n=-1):
        if n is None or n < 0:
            n = self.size - self.position
        want = min(n, self.size - self.position)
        done = 0
        out = bytearray(want)
        while done < want:
            index, inside = divmod(self.position, self.block)
            block_data = self._block(index)[inside:inside + want - done]
            out[done:done + len(block_data)] = block_data
            done += len(block_data)
            self.position += len(block_data)
        return bytes(out)

    def readinto(self, buffer):
        data = self.read(len(buffer))
        buffer[:len(data)] = data
        return len(data)


def fetch_members(url, members, build, sha256_pins, ipsw_config):
    """Download the named IPSW members into out/umi-xnu/ipsw/<build/>.

    A member may be a BuildManifest component name (StaticTrustCache,
    Cryptex1,SystemTrustCache, KernelCache, ...) or a literal archive path.
    Component names are resolved through BuildManifest.plist so that the board
    is the single source of truth for the IPSW layout.
    """
    cache = ROOT / 'out' / 'umi-xnu' / 'ipsw' / build
    cache.mkdir(parents=True, exist_ok=True)

    manifest_path = cache / 'BuildManifest.plist'
    if not manifest_path.is_file():
        raise Error('BuildManifest.plist must be fetched first')
    manifest = plistlib.loads(manifest_path.read_bytes())

    identity = None
    for item in manifest.get('BuildIdentities', []):
        info = item.get('Info', {})
        try:
            chip_id = int(item.get('ApChipID', '0'), 16)
            board_id = int(item.get('ApBoardID', '0'), 16)
        except (TypeError, ValueError):
            continue
        if (info.get('DeviceClass') == ipsw_config.get('device_class')
                and info.get('RestoreBehavior') == 'Erase'
                and chip_id == ipsw_config.get('chip_id', 0)
                and board_id == ipsw_config.get('board_id', 0)):
            identity = item
            break
    if identity is None:
        raise Error(f'no Erase build identity for device class '
                    f'{ipsw_config.get("device_class")} in this IPSW')

    needed = []
    for member in members:
        if member in identity['Manifest']:
            needed.append((member, identity['Manifest'][member]['Info']['Path']))
        else:
            needed.append((member, member))

    remote = RangeFile(url)
    results = {}

    print(f'opening {url} ({remote.size >> 20} MiB) via range requests')
    with zipfile.ZipFile(remote) as zf:
        for component, archive_name in needed:
            try:
                info = zf.getinfo(archive_name)
            except KeyError:
                raise Error(f'{archive_name!r} (component {component!r}) '
                            f'is not a member of this IPSW') from None
            dest = cache / Path(archive_name).name
            pin = sha256_pins.get(Path(archive_name).name)

            if dest.is_file() and dest.stat().st_size == info.file_size:
                cached_sha = hashlib.sha256(dest.read_bytes()).hexdigest()
                if pin is None or cached_sha == pin:
                    print(f'  cached   {archive_name} ({info.file_size} bytes)')
                    results[component] = dest
                    continue
                dest.unlink()

            print(f'  fetching {archive_name} ({info.file_size} bytes) ...', end=' ')
            data = zf.read(archive_name)
            dest.write_bytes(data)
            actual = hashlib.sha256(data).hexdigest()
            if pin and actual != pin:
                dest.unlink()
                raise Error(
                    f'{archive_name} sha256 {actual} does not match the pinned '
                    f'{pin} of board.toml [ipsw.sha256]')
            print(f'ok ({actual[:16]}...)')
            results[component] = dest

    return results


def main():
    board_path = ROOT / 'board.toml'
    board = tomllib.loads(board_path.read_text())
    ipsw = board.get('ipsw')
    if not ipsw:
        sys.exit(f'{board_path} has no [ipsw] section')

    url = ipsw.get('url')
    build = ipsw.get('build')
    if not url or not build:
        sys.exit('[ipsw] needs url and build')

    members = sys.argv[1:] or ipsw.get('fetch', [])
    if not members:
        sys.exit('no members to fetch: pass them on the command line or list them in [ipsw].fetch')

    sha256_pins = ipsw.get('sha256', {})
    ipsw_config = {
        'product': ipsw.get('product'),
        'version': ipsw.get('version'),
        'build': build,
        'device_class': ipsw.get('device_class'),
        'chip_id': ipsw.get('chip_id', 0),
        'board_id': ipsw.get('board_id', 0),
    }
    print(f'IPSW: {url}')
    print(f'product {ipsw.get("product")} / {ipsw.get("version")} build {build} '
          f'(device class {ipsw.get("device_class")})')
    print(f'members: {", ".join(members)}')

    fetched = fetch_members(url, members, build, sha256_pins, ipsw_config)
    cache = ROOT / 'out' / 'umi-xnu' / 'ipsw' / build
    provenance = {
        'url': url,
        'product': ipsw.get('product'),
        'version': ipsw.get('version'),
        'build': build,
        'device_class': ipsw.get('device_class'),
        'members': {name: {'file': dest.name, 'bytes': dest.stat().st_size}
                    for name, dest in fetched.items()},
        'pins_checked': True,
    }
    prov_path = cache / 'fetch.json'
    prov_path.write_text(json.dumps(provenance, indent=2) + '\n')
    print(f'wrote {len(fetched)} member(s) to {ROOT / "out" / "umi-xnu" / "ipsw" / build}')
    print(f'provenance: {prov_path}')


if __name__ == '__main__':
    try:
        main()
    except Error as error:
        sys.exit(f'fetch-ipsw-members: {error}')