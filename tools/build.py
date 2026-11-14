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
from ops import Feature, Hook
from regions import REGIONS

DEVKIT = os.environ.get('DEVKITPPC', '/opt/devkitpro/devkitPPC')
GCC = os.path.join(DEVKIT, 'bin', 'powerpc-eabi-')
SRC = os.path.join(HERE, '..', 'src', 'pad')

REF = 'RSRE01'
# (name, USA site, what the site holds, note)
# (name, USA site, what the site holds, variants that use it, note); REMOTE must come first
# (it holds the shared state the others link against)
HOOKS = [
    ('REMOTE', 0x800B5D00, 0x80110004, ('combo', 'cc', 'gc'),
     'pad loop, remote mode: GameCube / Classic Controller as the Wii Remote (buttons, tilt, shake)'),
    ('TOP', 0x800B5894, 0x80110004, ('combo', 'gc'),
     'pad loop, every channel: the GameCube controller as a Wii Remote when none is connected'),
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
                           '--defsym=wpad_probe=%s' % defs.get('WPAD_PROBE', '0'),
                           '--defsym=game_conv=%s' % defs.get('GAME_CONV', '0'),
                           '--defsym=loop_next=%s' % defs.get('LOOP_NEXT', '0'),
                           '-o', tmp + '/p.elf'] + (['--defsym=pad_state=' + defs['PAD_STATE']] if 'PAD_STATE' in defs else []) + [ tmp + '/h.o', tmp + '/b.o'])
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
    for name, usa, want, _, _ in HOOKS:
        site = usa if region == REF else find_site(ref, dol, usa)
        orig = struct.unpack('>I', dol.read(site, 4))[0]
        if orig != want:
            raise SystemExit('%s: %s site 0x%08X holds 0x%08X, expected 0x%08X' % (region, name, site, orig, want))
        sites[name] = (site, orig)
    # the game's own code the TOP hook calls, found from the loop's calls (relative to the sites)
    top, rem = sites['TOP'][0], sites['REMOTE'][0]
    game = {'WPAD_PROBE': '0x%08X' % bl_target(dol, top + 0x20),     # bl WPADProbe
            'GAME_CONV': '0x%08X' % bl_target(dol, rem + 0x14),       # bl <remote converter>
            'LOOP_NEXT': '0x%08X' % (rem + 0xC0)}                     # addi r26,r26,56
    if struct.unpack('>I', dol.read(rem + 0xC0, 4))[0] != 0x3B5A0038:
        raise SystemExit('%s: loop increment not where expected' % region)
    out = {}
    for fname, flags in VARIANTS.items():
        ops, cur, state = [], CAVE_BASE, None
        for name, _, _, used, note in HOOKS:
            if fname not in used:
                continue
            defs = {f: None for f in flags}
            if state is not None:
                defs['PAD_STATE'] = '0x%08X' % state
            defs.update(game)
            w = compile_hook(name, defs, cur)
            assert w[-1] == 0x60000000, 'the stub must end in the nop slot'
            w[-1] = 0
            if name == 'REMOTE':
                state = cur + 4
            site, orig = sites[name]
            ops.append(Hook(site, orig, w, cur, note))
            cur += (len(w) * 4 + 31) & ~31
        if cur > CAVE_LIMIT:
            raise SystemExit('hooks overflow the injected section')
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
