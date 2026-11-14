#!/usr/bin/env python3
"""Compile the pad hook (src/pad/) into prebuilt feature definitions (tools/prebuilt/*.json).

The hook is written once against the USA release.  For every other release the hook site is
found by matching a window of USA instructions with the relocatable bits (branch
displacements, address halves, small-data offsets) masked out; it must match exactly once.

Needs devkitPPC and the retail main.dol of each release:

    python3 tools/build.py --dol RSRE01=path/to/usa/main.dol --dol RSRP01=path/to/pal/main.dol

End users never run this: the patcher ships the JSON it writes.
"""
import argparse
import json
import os
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from dol import Dol
from features import PREBUILT, TITLES, dump
from layout import CAVE_BASE
from ops import Feature, Hook
from regions import REGIONS

DEVKIT = os.environ.get('DEVKITPPC', '/opt/devkitpro/devkitPPC')
GCC = os.path.join(DEVKIT, 'bin', 'powerpc-eabi-')
SRC = os.path.join(HERE, '..', 'src', 'pad')

REF = 'RSRE01'
# the game's pad loop, just before the remote-mode converter: lwz r0,4(r17)
REF_SITE = 0x800B5D00
DISPLACED = 0x80110004
WINDOW = (-40, 24)          # instructions matched around the site

# KPADStatus: Classic Controller left stick (two floats); identical in every release
CL_LSTICK = 0x6C

VARIANTS = {'combo': ('USE_GC', 'USE_CC'), 'cc': ('USE_CC',), 'gc': ('USE_GC',)}
NOTE = 'pad loop: GameCube / Classic Controller buttons and left stick into the Wii Remote statuses'


def mask(w):
    op = w >> 26
    if op == 18:                                 # b / bl: keep opcode, AA, LK
        return w & 0xFC000003
    if op == 16:                                 # bc: keep everything but the displacement
        return w & 0xFFFF0003
    if op in (14, 15, 24, 25, 26, 27, 28, 29):   # addi / lis / ori / oris / xori / andi
        return w & 0xFFFF0000
    if 32 <= op <= 55:                           # loads / stores: drop the displacement
        return w & 0xFFFF0000
    return w


def text_sections(dol):
    """(address, words) of every text section"""
    for off, addr, size, idx in dol.secs:
        if idx < 7 and size:
            yield addr, struct.unpack('>%dI' % (size // 4), dol.data[off:off + size])


def find_site(ref, tgt):
    lo, hi = WINDOW
    for raddr, rwords in text_sections(ref):
        if raddr <= REF_SITE < raddr + 4 * len(rwords):
            i = (REF_SITE - raddr) // 4
            pat = [mask(w) for w in rwords[i + lo:i + hi]]
            break
    else:
        raise SystemExit('reference site not in a text section')
    hits = []
    for taddr, twords in text_sections(tgt):
        tm = [mask(w) for w in twords]
        n = len(pat)
        hits += [taddr + (j - lo) * 4 for j in range(len(tm) - n + 1) if tm[j] == pat[0] and tm[j:j + n] == pat]
    if len(hits) != 1:
        raise SystemExit('hook site: %d matches' % len(hits))
    return hits[0]


def compile_hook(defs, base):
    tmp = tempfile.mkdtemp(prefix='ssrpad')
    d = ['-D%s' % k if v is None else '-D%s=%s' % (k, v) for k, v in defs.items()]
    cflags = ['-O2', '-mcpu=750', '-mbig-endian', '-mhard-float', '-msdata=none', '-ffreestanding', '-fno-pic',
              '-fno-asynchronous-unwind-tables', '-fno-stack-protector', '-nostdlib', '-fno-builtin',
              '-Wall', '-Werror', '-fsingle-precision-constant']
    subprocess.check_call([GCC + 'gcc'] + cflags + d + ['-c', os.path.join(SRC, 'bridge.c'), '-o', tmp + '/b.o'])
    subprocess.check_call([GCC + 'gcc', '-mbig-endian', '-c', '-x', 'assembler-with-cpp'] + d +
                          [os.path.join(SRC, 'hooks.S'), '-o', tmp + '/h.o'])
    # linked at the address the trampoline will live at (its float constants are absolute)
    subprocess.check_call([GCC + 'ld', '-T', os.path.join(SRC, 'link.ld'), '--section-start=.text=0x%08X' % base,
                           '-o', tmp + '/p.elf', tmp + '/h.o', tmp + '/b.o'])
    subprocess.check_call([GCC + 'objcopy', '-O', 'binary', tmp + '/p.elf', tmp + '/p.bin'])
    b = open(tmp + '/p.bin', 'rb').read()
    return list(struct.unpack('>%dI' % (len(b) // 4), b))


def build(region, dol, ref):
    site = REF_SITE if region == REF else find_site(ref, dol)
    orig = struct.unpack('>I', dol.read(site, 4))[0]
    if orig != DISPLACED:
        raise SystemExit('%s: site 0x%08X holds 0x%08X, expected 0x%08X' % (region, site, orig, DISPLACED))
    out = {}
    for name, flags in VARIANTS.items():
        defs = {f: None for f in flags}
        defs['CL_LSTICK'] = '0x%X' % CL_LSTICK
        if os.environ.get('SSR_DEBUG'):
            defs['DEBUG_ADDR'] = '0x80002F00'
        w = compile_hook(defs, CAVE_BASE)
        assert w[-1] == 0x60000000, 'the stub must end in the nop slot'
        w[-1] = 0
        out[name] = Feature(name, TITLES[name], region, [Hook(site, orig, w, CAVE_BASE, NOTE)])
    return site, out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--dol', action='append', required=True, metavar='REGION=PATH',
                    help='retail main.dol of a release (the USA one is required: it is the reference)')
    ap.add_argument('--out', default=PREBUILT)
    a = ap.parse_args()
    dols = dict(x.split('=', 1) for x in a.dol)
    if REF not in dols:
        raise SystemExit('the USA main.dol (%s) is required' % REF)
    ref = Dol(dols[REF])
    os.makedirs(a.out, exist_ok=True)
    for region, path in sorted(dols.items()):
        if region not in REGIONS:
            raise SystemExit('unknown release %s' % region)
        site, feats = build(region, Dol(path), ref)
        for name, f in feats.items():
            p = os.path.join(a.out, '%s_%s.json' % (name, region))
            with open(p, 'w') as fh:
                json.dump(dump(f), fh, indent=2)
                fh.write('\n')
        print('%s: hook at 0x%08X, %d words' % (region, site, len(feats['combo'].ops[0].payload)))


if __name__ == '__main__':
    main()
