"""Patch a whole Sonic and the Secret Rings disc image: extract with wit, patch sys/main.dol, rebuild.

The rebuilt image replaces the original in place, keeping its filename and
folder (USB loaders key off the `/wbfs/<Title> [ID6]/` layout); the untouched
original is kept next to it as `<name>.bak`.
"""
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import features
import patcher
from dol import Dol
from regions import ALL_REGIONS


def find_wit():
    """Locate wiimms ISO Tool (wit). Bundled binary wins over PATH."""
    name = 'wit.exe' if os.name == 'nt' else 'wit'
    if getattr(sys, 'frozen', False):
        for base in (getattr(sys, '_MEIPASS', None), os.path.dirname(sys.executable)):
            if base:
                bundled = os.path.join(base, name)
                if os.path.isfile(bundled):
                    return bundled
    return shutil.which('wit')


def find_file(root, name):
    for r, _, files in os.walk(root):
        if name in files:
            return os.path.join(r, name)
    return None


def read_disc_id(fst):
    boot = find_file(fst, 'boot.bin')
    if not boot:
        return None
    with open(boot, 'rb') as f:
        header = f.read(8)
    return header[0:6].decode('ascii', 'replace'), header[7]


def run_patch(image_path, log, done, which=('cc', 'gc'), ios=None, dest=None):
    """Patch `image_path` in place or to `dest`."""
    try:
        wit = find_wit()
        if wit is None:
            raise RuntimeError('wit (Wiimms ISO Tool) not found: not bundled with this build and not on PATH')

        fmt = '--iso' if (dest or image_path).lower().endswith('.iso') else '--wbfs'

        with tempfile.TemporaryDirectory(prefix='secret_rings_patch_') as tmp:
            fst = os.path.join(tmp, 'fst')
            log('extracting %s...' % os.path.basename(image_path))
            r = subprocess.run([wit, 'extract', image_path, '--dest', fst, '--psel', 'data',
                                '--overwrite', '-q'], capture_output=True, text=True)
            if r.returncode:
                raise RuntimeError('extract failed:\n' + (r.stderr or r.stdout))

            got = read_disc_id(fst)
            if not got:
                raise RuntimeError('could not read sys/boot.bin from the extracted disc')
            disc_id, disc_ver = got
            if disc_id not in ALL_REGIONS:
                raise RuntimeError('%s is not a recognized Sonic and the Secret Rings release.\n\n'
                                   'Supported:\n%s' % (disc_id, '\n'.join(
                                       '  %s: %s' % (k, v['label']) for k, v in ALL_REGIONS.items())))

            region = disc_id
            reg_info = ALL_REGIONS[region]
            log('disc: %s (%s)' % (region, reg_info['label']))

            dol_path = find_file(fst, 'main.dol')
            if not dol_path or os.path.basename(os.path.dirname(dol_path)) != 'sys':
                raise RuntimeError('could not find sys/main.dol in the extracted disc')
            dol = Dol(dol_path)

            have = patcher.status(dol, region)
            valid_feats = reg_info.get('features', patcher.ORDER)
            selected = [w for w in valid_feats if w in which]
            if not selected:
                raise RuntimeError('no applicable patches selected for this title')

            todo = []
            for name in selected:
                st = have.get(name)
                if st == 'patched':
                    log('  %s is already applied in this disc' % features.TITLES[name])
                elif st == 'clean':
                    todo.append(name)
                else:
                    raise RuntimeError('main.dol does not match clean retail %s (%s): already modified '
                                       'by something else, or not an unmodified dump.'
                                       % (region, reg_info['label']))

            if not todo:
                log('All selected patches are already applied; nothing to do.')
                done(True, 'Already patched')
                return

            log('applying patches: %s...' % ', '.join(features.TITLES[n] for n in todo))
            patcher.patch(dol, region, todo)
            dol.save(dol_path)

            out_dest = dest or image_path
            backup = image_path + '.bak'
            if not dest and not os.path.exists(backup):
                log('creating backup at %s...' % os.path.basename(backup))
                shutil.copy2(image_path, backup)

            log('rebuilding disc image to %s...' % os.path.basename(out_dest))
            reb = subprocess.run([wit, 'copy', fst, out_dest, fmt, '--overwrite', '-q'],
                                 capture_output=True, text=True)
            if reb.returncode:
                raise RuntimeError('rebuild failed:\n' + (reb.stderr or reb.stdout))

            log('done!')
            done(True, 'Successfully patched')
    except Exception as e:
        log('Error: %s' % str(e))
        done(False, str(e))
