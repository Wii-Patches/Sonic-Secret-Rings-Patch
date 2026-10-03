"""Sonic and the Secret Rings releases on Wii.

RSRE01: USA / NTSC-U
RSRP01: Europe / PAL (UK, Australia, Germany, France, Italy, Spain)
RSRJ01: Japan / NTSC-J
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
        'btn_hook': 0x80556D54,
        'tilt_hook': 0x8055766C,
        'poll_hook': 0x80556940,
        'kpad_base': 0x80692B60,
    },
    'RSRP01': {
        'label': 'Sonic and the Secret Rings (Europe)',
        'short': 'EUR',
        'id6': 'RSRP8P',
        'version': 0,
        'features': ('combo', 'cc', 'gc'),
        'dol_md5': '06403d885e75b85e7262e0059829f642',
        'dol_size': 6265376,
        'btn_hook': 0x80556D20,
        'tilt_hook': 0x80557638,
        'poll_hook': 0x8055690C,
        'kpad_base': 0x80692B60,
    },
    'RSRJ01': {
        'label': 'Sonic to Himitsu no Ring (Japan)',
        'short': 'JPN',
        'id6': 'RSRJ8P',
        'version': 0,
        'features': ('combo', 'cc', 'gc'),
        'dol_md5': 'b07dc68e1623382fb228bd62ccb921a3',
        'dol_size': 6265440,
        'btn_hook': 0x80556D54,
        'tilt_hook': 0x8055766C,
        'poll_hook': 0x80556940,
        'kpad_base': 0x80692B60,
    },
}

ALL_REGIONS = dict(REGIONS)
