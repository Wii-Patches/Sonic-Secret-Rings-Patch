#!/usr/bin/env python3
"""Compile the pad hooks (src/pad/) into prebuilt feature definitions (tools/prebuilt/*.json).

The hooks are written once against the USA release.  For every other release each hook site is
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
from layout import CAVE_BASE, CAVE_LIMIT
from ops import Feature, Hook, Patch
from regions import REGIONS

DEVKIT = os.environ.get('DEVKITPPC', '/opt/devkitpro/devkitPPC')
GCC = os.path.join(DEVKIT, 'bin', 'powerpc-eabi-')
SRC = os.path.join(HERE, '..', 'src', 'pad')

REF = 'RSRE01'
# (name, USA site, what the site holds, note)
HOOKS = [
    ('REMOTE', 0x800B5D00, 0x80110004,
     'pad loop, remote mode: GameCube / Classic Controller as the Wii Remote (buttons, tilt, shake)'),
]
# Work in progress, not shipped: playing with no Wii Remote at all.  HOOK_PAD (src/pad/) turns
# the game's own GameCube-pad record into a remote record, which gets through the menus, but a
# story stage still pauses ("Communications with the Wii Remote have been interrupted") from a
# check in the game's RSO modules that is not found yet.  It would also change how Party mode's
# native GameCube support behaves.  Add it back here (and to PATCHES) once that is solved:
#   ('PAD', 0x800B5D3C, None, 'pad loop, no Wii Remote: the GameCube controller as a Wii Remote'),
PAD_HOOK = False
# (USA address, what it holds, replacement, note): the controller manager's "is a Wii Remote
# connected on this channel" call, which a GameCube controller on its own can never satisfy
PATCHES = [] if True else [
    (0x80214CE0, 'bl 0x800B5E14', 0x38600001,
     'controller manager: accept a channel whose KPAD status has no error (a GameCube controller in pad mode)'),
]
WINDOW = (-40, 24)          # instructions matched around a site

VARIANTS = {'combo': ('USE_GC', 'USE_CC'), 'cc': ('USE_CC',), 'gc': ('USE_GC',)}


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


def find_site(ref, tgt, site):
    lo, hi = WINDOW
    for raddr, rwords in text_sections(ref):
        if raddr <= site < raddr + 4 * len(rwords):
            i = (site - raddr) // 4
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


def compile_hook(hook, defs, base):
    tmp = tempfile.mkdtemp(prefix='ssrpad')
    defs = dict(defs, **{'HOOK_' + hook: None})
    d = ['-D%s' % k if v is None else '-D%s=%s' % (k, v) for k, v in defs.items()]
    cflags = ['-O2', '-mcpu=750', '-mbig-endian', '-mhard-float', '-msdata=none', '-ffreestanding', '-fno-pic',
              '-fno-asynchronous-unwind-tables', '-fno-stack-protector', '-nostdlib', '-fno-builtin',
              '-Wall', '-Werror', '-fsingle-precision-constant']
    subprocess.check_call([GCC + 'gcc'] + cflags + d + ['-c', os.path.join(SRC, 'bridge.c'), '-o', tmp + '/b.o'])
    subprocess.check_call([GCC + 'gcc', '-mbig-endian', '-c', '-x', 'assembler-with-cpp'] + d +
                          [os.path.join(SRC, 'hooks.S'), '-o', tmp + '/h.o'])
    # linked at the address the trampoline will live at (its float constants are absolute)
    subprocess.check_call([GCC + 'ld', '-T', os.path.join(SRC, 'link.ld'), '--section-start=.text=0x%08X' % base,
                           '--defsym=pad_converter=%s' % defs.get('PAD_CONVERTER', '0'),
                           '-o', tmp + '/p.elf', tmp + '/h.o', tmp + '/b.o'])
    subprocess.check_call([GCC + 'objcopy', '-O', 'binary', tmp + '/p.elf', tmp + '/p.bin'])
    b = open(tmp + '/p.bin', 'rb').read()
    return list(struct.unpack('>%dI' % (len(b) // 4), b))


def bl_target(dol, site):
    w = struct.unpack('>I', dol.read(site, 4))[0]
    if w & 0xFC000003 != 0x48000001:
        raise SystemExit('0x%08X is not a bl' % site)
    off = w & 0x03FFFFFC
    return site + (off - 0x04000000 if off & 0x02000000 else off)


def build(region, dol, ref):
    sites = {}
    for name, usa, want, _ in HOOKS:
        site = usa if region == REF else find_site(ref, dol, usa)
        orig = struct.unpack('>I', dol.read(site, 4))[0]
        if want is not None and orig != want:
            raise SystemExit('%s: %s site 0x%08X holds 0x%08X, expected 0x%08X' % (region, name, site, orig, want))
        sites[name] = (site, orig)
    conv = bl_target(dol, sites['PAD'][0]) if 'PAD' in sites else 0
    patches = []
    for usa, want, new, note in PATCHES:
        addr = usa if region == REF else find_site(ref, dol, usa)
        ref_target = int(want.split()[1], 16)
        # the call must go to the same getter (relocated the same way as the call itself)
        if region == REF and bl_target(dol, addr) != ref_target:
            raise SystemExit('%s: 0x%08X is not %s' % (region, addr, want))
        patches.append(Patch(addr, struct.pack('>I', new), dol.read(addr, 4), note))
    out = {}
    for fname, flags in VARIANTS.items():
        ops, cur = [], CAVE_BASE
        for name, _, _, note in HOOKS:
            if name == 'PAD' and 'USE_GC' not in flags:
                continue
            defs = {f: None for f in flags}
            defs['PAD_CONVERTER'] = '0x%08X' % conv
            w = compile_hook(name, defs, cur)
            assert w[-1] == 0x60000000, 'the stub must end in the nop slot'
            w[-1] = 0
            site, orig = sites[name]
            ops.append(Hook(site, orig, w, cur, note))
            cur += (len(w) * 4 + 31) & ~31
        if cur > CAVE_LIMIT:
            raise SystemExit('hooks overflow the injected section')
        if 'USE_GC' in flags:
            ops += patches
        out[fname] = Feature(fname, TITLES[fname], region, ops)
    return sites, out


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
        sites, feats = build(region, Dol(path), ref)
        for name, f in feats.items():
            p = os.path.join(a.out, '%s_%s.json' % (name, region))
            with open(p, 'w') as fh:
                json.dump(dump(f), fh, indent=2)
                fh.write('\n')
        print('%s: %s' % (region, ', '.join('%s 0x%08X' % (k, v[0]) for k, v in sites.items())))


if __name__ == '__main__':
    main()
