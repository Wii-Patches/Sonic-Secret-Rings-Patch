#!/usr/bin/env python3
"""Generate prebuilt feature definitions (tools/prebuilt/<feature>_<region>.json)

Outputs:
  - cc_RSRE01.json, cc_RSRP01.json, cc_RSRJ01.json
  - gc_RSRE01.json, gc_RSRP01.json, gc_RSRJ01.json
"""
import json
import os
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from dol import Dol
from ops import Patch, Hook, Blob, Feature
from layout import CC_BASE, GC_BASE, CAVE_BASE
from regions import REGIONS
from features import PREBUILT, dump

DKP = os.environ.get('DEVKITPPC', '/opt/devkitpro/devkitPPC')
AS = os.path.join(DKP, 'bin', 'powerpc-eabi-as')
OBJDUMP = os.path.join(DKP, 'bin', 'powerpc-eabi-objdump')
OBJCOPY = os.path.join(DKP, 'bin', 'powerpc-eabi-objcopy')

RETAIL_DOLS = {
    'RSRE01': '/tmp/retail_us/sys/main.dol',
    'RSRP01': '/tmp/retail_pal/sys/main.dol',
    'RSRJ01': '/tmp/retail_jp/sys/main.dol',
}

def assemble_file(src_path, base_addr):
    with tempfile.TemporaryDirectory() as tmp:
        obj_path = os.path.join(tmp, 'out.o')
        bin_path = os.path.join(tmp, 'out.bin')
        subprocess.run([AS, '-mregnames', '-mgekko', '-mbig', src_path, '-o', obj_path], check=True)
        dump_out = subprocess.run([OBJDUMP, '-t', obj_path], capture_output=True, text=True).stdout
        syms = {}
        for line in dump_out.splitlines():
            parts = line.split()
            if len(parts) >= 2:
                sym_name = parts[-1]
                try:
                    sym_offset = int(parts[0], 16)
                    syms[sym_name] = base_addr + sym_offset
                except ValueError:
                    pass
        subprocess.run([OBJCOPY, '-O', 'binary', obj_path, bin_path], check=True)
        with open(bin_path, 'rb') as f:
            code = f.read()
        return code, syms

def b_insn(target, frm, link=False):
    off = target - frm
    return 0x48000000 | (off & 0x03FFFFFC) | (1 if link else 0)

def build_cc(region):
    info = REGIONS[region]
    dol = Dol(RETAIL_DOLS[region])
    src_path = os.path.join(HERE, '..', 'src', 'cc_hooks.s')
    base_addr = CC_BASE
    code_bytes, syms = assemble_file(src_path, base_addr)

    ops = []
    # 1. Injected section blob containing the assembled routines
    ops.append(Blob(base_addr, code_bytes, 'Classic Controller routines'))

    # 2. Button hook
    btn_site = info['btn_hook']
    orig_btn = dol.read(btn_site, 8)
    btn_target = syms['cc_button_hook']
    new_btn = struct.pack('>2I', b_insn(btn_target, btn_site, link=True), 0x60000000)
    ops.append(Patch(btn_site, new_btn, orig_btn, 'Button read hook -> Classic Controller mapping'))

    # 3. Tilt hook
    tilt_site = info['tilt_hook']
    orig_tilt = dol.read(tilt_site, 4)
    tilt_target = syms['cc_tilt_hook']
    new_tilt = struct.pack('>I', b_insn(tilt_target, tilt_site, link=True))
    ops.append(Patch(tilt_site, new_tilt, orig_tilt, 'Tilt hook -> Classic Controller left stick'))

    return Feature('cc', 'Classic Controller Support', region, ops)

def build_gc(region):
    info = REGIONS[region]
    dol = Dol(RETAIL_DOLS[region])
    src_path = os.path.join(HERE, '..', 'src', 'gc_hooks.s')
    base_addr = GC_BASE
    code_bytes, syms = assemble_file(src_path, base_addr)

    ops = []
    # 1. Injected section blob
    ops.append(Blob(base_addr, code_bytes, 'GameCube Controller routines'))

    # 2. Poller hook (ensures SI channel 0 polling is running)
    poll_site = info['poll_hook']
    orig_poll = dol.read(poll_site, 8)
    poll_target = syms['gc_poller_hook']
    new_poll = struct.pack('>2I', b_insn(poll_target, poll_site, link=True), 0x60000000)
    ops.append(Patch(poll_site, new_poll, orig_poll, 'KPADRead SI hardware poller enable hook'))

    # 3. Button hook
    btn_site = info['btn_hook']
    orig_btn = dol.read(btn_site, 8)
    btn_target = syms['gc_button_hook']
    new_btn = struct.pack('>2I', b_insn(btn_target, btn_site, link=True), 0x60000000)
    ops.append(Patch(btn_site, new_btn, orig_btn, 'Button read hook -> GameCube Controller mapping'))

    # 4. Tilt hook
    tilt_site = info['tilt_hook']
    orig_tilt = dol.read(tilt_site, 4)
    tilt_target = syms['gc_tilt_hook']
    new_tilt = struct.pack('>I', b_insn(tilt_target, tilt_site, link=True))
    ops.append(Patch(tilt_site, new_tilt, orig_tilt, 'Tilt hook -> GameCube stick tilt'))

    return Feature('gc', 'GameCube Controller Support', region, ops)

def build_combo(region):
    info = REGIONS[region]
    dol = Dol(RETAIL_DOLS[region])
    src_path = os.path.join(HERE, '..', 'src', 'gc_cc_hooks.s')
    base_addr = CAVE_BASE
    code_bytes, syms = assemble_file(src_path, base_addr)

    ops = []
    # 1. Injected section blob
    ops.append(Blob(base_addr, code_bytes, 'Classic & GameCube Controller routines'))

    # 2. Poller hook
    poll_site = info['poll_hook']
    orig_poll = dol.read(poll_site, 8)
    poll_target = syms['hook_poller']
    new_poll = struct.pack('>2I', b_insn(poll_target, poll_site, link=True), 0x60000000)
    ops.append(Patch(poll_site, new_poll, orig_poll, 'KPADRead SI hardware poller enable hook'))

    # 3. Button hook
    btn_site = info['btn_hook']
    orig_btn = dol.read(btn_site, 8)
    btn_target = syms['hook_buttons']
    new_btn = struct.pack('>2I', b_insn(btn_target, btn_site, link=True), 0x60000000)
    ops.append(Patch(btn_site, new_btn, orig_btn, 'Button read hook -> Classic & GameCube Controller mapping'))

    # 4. Tilt hook
    tilt_site = info['tilt_hook']
    orig_tilt = dol.read(tilt_site, 4)
    tilt_target = syms['hook_tilt']
    new_tilt = struct.pack('>I', b_insn(tilt_target, tilt_site, link=True))
    ops.append(Patch(tilt_site, new_tilt, orig_tilt, 'Tilt hook -> Classic & GameCube analog stick steering'))

    return Feature('combo', 'Classic & GameCube Controller Suite', region, ops)

def main():
    os.makedirs(PREBUILT, exist_ok=True)
    for reg in ('RSRE01', 'RSRP01', 'RSRJ01'):
        # Combo
        f_combo = build_combo(reg)
        p_combo = os.path.join(PREBUILT, f'combo_{reg}.json')
        with open(p_combo, 'w') as fh:
            json.dump(dump(f_combo), fh, indent=2)
        print(f"Generated {p_combo} ({len(f_combo.ops)} ops)")

        # CC
        f_cc = build_cc(reg)
        p_cc = os.path.join(PREBUILT, f'cc_{reg}.json')
        with open(p_cc, 'w') as fh:
            json.dump(dump(f_cc), fh, indent=2)
        print(f"Generated {p_cc} ({len(f_cc.ops)} ops)")

        # GC
        f_gc = build_gc(reg)
        p_gc = os.path.join(PREBUILT, f'gc_{reg}.json')
        with open(p_gc, 'w') as fh:
            json.dump(dump(f_gc), fh, indent=2)
        print(f"Generated {p_gc} ({len(f_gc.ops)} ops)")

if __name__ == '__main__':
    main()

