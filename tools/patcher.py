"""Apply selected patches to any Sonic and the Secret Rings main.dol."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import features
from dol import Dol
from ops import apply_static
from regions import ALL_REGIONS

ORDER = ('combo', 'cc', 'gc')


def detect_region(dol):
    """Detect which Sonic and the Secret Rings release this main.dol is."""
    for region in ('RSRE01', 'RSRP01', 'RSRJ01'):
        if features.available('combo', region):
            f = features.load('combo', region)
            if not f.check_pristine(dol) or f.is_applied(dol):
                return region
        elif features.available('cc', region):
            f = features.load('cc', region)
            if not f.check_pristine(dol) or f.is_applied(dol):
                return region
    return None


def status(dol, region):
    """Return {feature_name: 'clean' | 'patched' | 'mismatch'} for all features valid on this game."""
    out = {}
    valid_features = ALL_REGIONS.get(region, {}).get('features', ORDER)
    for name in valid_features:
        if not features.available(name, region):
            continue
        f = features.load(name, region)
        if f.is_applied(dol):
            out[name] = 'patched'
        elif not f.check_pristine(dol):
            out[name] = 'clean'
        else:
            out[name] = 'mismatch'
    return out


def patch(dol, region, which):
    """Patch `dol` (a dol.Dol instance) in place with the features in `which`."""
    valid_features = ALL_REGIONS.get(region, {}).get('features', ORDER)
    feats = [features.load(n, region) for n in valid_features if n in which and features.available(n, region)]
    if not feats:
        raise ValueError('No valid patches selected for region %s' % region)
    apply_static(dol, feats)
    return [f.title for f in feats]


def patch_file(src, dst, region, which):
    dol = Dol(src)
    done = patch(dol, region, which)
    dol.save(dst)
    return done


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser(description='Patch a Sonic and the Secret Rings main.dol')
    ap.add_argument('src', help='Path to source main.dol')
    ap.add_argument('dst', help='Path to output patched main.dol')
    ap.add_argument('--region', choices=sorted(ALL_REGIONS), help='Region ID (auto-detected if omitted)')
    for n in ORDER:
        ap.add_argument('--' + n, action='store_true', help=features.TITLES[n])
    a = ap.parse_args()
    d = Dol(a.src)
    reg = a.region or detect_region(d)
    if not reg:
        sys.exit('Error: could not auto-detect region; please specify --region')
    which = [n for n in ORDER if getattr(a, n)] or list(ALL_REGIONS[reg]['features'])
    applied = patch_file(a.src, a.dst, reg, which)
    print(f"{reg} ({ALL_REGIONS[reg]['label']}) -> {', '.join(applied)}")
