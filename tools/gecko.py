"""Parse a Gecko code list (04 / 06 / C2 lines) back into raw operations."""


def parse(text):
    lines = [l.split()[:2] for l in text.splitlines() if l.strip() and not l.lstrip().startswith(('*', '$', '#'))]
    i, out = 0, []
    while i < len(lines):
        a, b = lines[i]
        kind, addr = int(a[:2], 16), 0x80000000 | (int(a[2:], 16) & 0x01FFFFFF)
        if kind == 0x04:
            out.append(('04', addr, [int(b, 16)]))
            i += 1
        elif kind == 0x06:
            n = int(b, 16)
            nl = (n + 7) // 8
            raw = b''.join(bytes.fromhex(x) for ln in lines[i + 1:i + 1 + nl] for x in ln)
            out.append(('06', addr, raw[:n]))
            i += 1 + nl
        elif kind == 0xC2:
            n = int(b, 16)
            ws = [int(x, 16) for ln in lines[i + 1:i + 1 + n] for x in ln]
            out.append(('C2', addr, ws))
            i += 1 + n
        else:
            raise ValueError('unsupported code line: %s %s' % (a, b))
    return out
