"""Sonic and the Secret Rings releases on Wii.

RSRE01: USA / NTSC-U
RSRP01: Europe / PAL (UK, Australia, Germany, France, Italy, Spain)
"""

REGIONS = {
    'RSRE01': {
        'label': 'Sonic and the Secret Rings (USA)',
        'short': 'USA',
        'id6': 'RSRE8P',
        'version': 0,
        'features': ('combo', 'cc', 'gc'),
        'dol_md5': 'b07dc68e1623382fb228bd62ccb921a3',
        'dol_size': 6265440,
    },
    'RSRP01': {
        'label': 'Sonic and the Secret Rings (Europe)',
        'short': 'EUR',
        'id6': 'RSRP8P',
        'version': 0,
        'features': ('combo', 'cc', 'gc'),
        'dol_md5': '06403d885e75b85e7262e0059829f642',
        'dol_size': 6265376,
    },
}

ALL_REGIONS = dict(REGIONS)
