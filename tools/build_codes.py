#!/usr/bin/env python3
"""Generate Gecko code lists (.txt and Dolphin .ini) and Riivolution XML files."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import features
from regions import ALL_REGIONS

CODES_DIR = os.path.join(HERE, '..', 'codes')
RIIV_DIR = os.path.join(HERE, '..', 'riivolution')

os.makedirs(CODES_DIR, exist_ok=True)
os.makedirs(RIIV_DIR, exist_ok=True)

def generate_gecko_for_region(region_id):
    meta = ALL_REGIONS[region_id]
    game_title = meta['label']
    valid_feats = meta.get('features', ())

    # 1. Plain text format
    txt_path = os.path.join(CODES_DIR, f"{region_id}.txt")
    lines = [
        f"{game_title} [{region_id}]",
        "Classic Controller + GameCube Controller Code Suite",
        ""
    ]
    for feat_name in valid_feats:
        if features.available(feat_name, region_id):
            feat = features.load(feat_name, region_id)
            lines.append(f"{feat.title} [{region_id}]")
            for gl in feat.gecko_lines():
                lines.append(gl)
            lines.append("")

    with open(txt_path, 'w') as f:
        f.write('\n'.join(lines) + '\n')

    # 2. Dolphin INI format
    ini_path = os.path.join(CODES_DIR, f"{region_id}.ini")
    ini_lines = [
        f"# {game_title} - [{region_id}]",
        "[Gecko]",
    ]
    for feat_name in valid_feats:
        if features.available(feat_name, region_id):
            feat = features.load(feat_name, region_id)
            ini_lines.append(f"${feat.title}")
            for gl in feat.gecko_lines():
                if not gl.startswith('*'):
                    ini_lines.append(gl)
    ini_lines.append("")
    ini_lines.append("[Gecko_Enabled]")
    if features.available('combo', region_id):
        feat = features.load('combo', region_id)
        ini_lines.append(f"${feat.title}")

    with open(ini_path, 'w') as f:
        f.write('\n'.join(ini_lines) + '\n')

def generate_riivolution():
    xml_path = os.path.join(RIIV_DIR, "SonicSecretRings.xml")
    lines = [
        '<wiidisc version="1">',
        '  <id game="RSR">',
        '    <region type="E" />',
        '    <region type="P" />',
        '    <region type="J" />',
        '  </id>',
        '  <options>',
        '    <section name="Sonic and the Secret Rings Controller Patch">',
        '      <option name="Controller Support">',
        '        <choice name="Classic & GameCube Controller Suite (Recommended)">',
        '          <patch id="combo" />',
        '        </choice>',
        '        <choice name="Classic Controller Only">',
        '          <patch id="cc" />',
        '        </choice>',
        '        <choice name="GameCube Controller Only">',
        '          <patch id="gc" />',
        '        </choice>',
        '      </option>',
        '    </section>',
        '  </options>',
    ]

    for fkey in ('combo', 'cc', 'gc'):
        lines.append(f'  <patch id="{fkey}">')
        for reg in ('RSRE01', 'RSRP01', 'RSRJ01'):
            if features.available(fkey, reg):
                feat = features.load(fkey, reg)
                lines.append(f'    <!-- {reg}: {feat.title} -->')
                for el in feat.memory_elements():
                    lines.append(f'    {el}')
        lines.append('  </patch>')

    lines.append('</wiidisc>')
    with open(xml_path, 'w') as f:
        f.write('\n'.join(lines) + '\n')

def main():
    for reg in ALL_REGIONS:
        generate_gecko_for_region(reg)
        print(f"Generated Gecko codes for {reg}")
    generate_riivolution()
    print("Generated Riivolution XML")

if __name__ == '__main__':
    main()
