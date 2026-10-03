"""Where the hook trampolines and data live in the injected low-memory section.

0x80001800-0x80003000 is the Wii's boot-time scratch area, which the game never
touches after booting. The first 0x20 bytes are skipped.
"""
CAVE_BASE = 0x80001820
CAVE_LIMIT = 0x80003000

# Classic Controller trampolines window
CC_BASE = 0x80001820
CC_END = 0x80002000

# GameCube controller hook trampolines window
GC_BASE = 0x80002000
GC_END = 0x80002F00

# State data window if needed
DATA_BASE = 0x80002F00
DATA_END = 0x80002F40

WINDOWS = {
    'cc': (CC_BASE, CC_END),
    'gc': (GC_BASE, GC_END),
    'data': (DATA_BASE, DATA_END),
}
