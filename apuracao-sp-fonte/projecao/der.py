"""Leitor DER mínimo (sem dependências) para os boletins de urna do TSE."""

def read_tlv(b, i):
    t = b[i]; i += 1
    cls, cons, num = t >> 6, bool(t & 0x20), t & 0x1F
    if num == 0x1F:
        num = 0
        while True:
            x = b[i]; i += 1
            num = (num << 7) | (x & 0x7F)
            if not x & 0x80:
                break
    l = b[i]; i += 1
    if l & 0x80:
        n = l & 0x7F
        l = int.from_bytes(b[i:i + n], "big"); i += n
    return cls, cons, num, i, i + l


def parse(b, i=0, end=None):
    """Árvore: lista de (cls, num, valor) — valor = lista (construído) ou bytes."""
    end = len(b) if end is None else end
    out = []
    while i < end:
        cls, cons, num, s, e = read_tlv(b, i)
        out.append((cls, num, parse(b, s, e) if cons else b[s:e]))
        i = e
    return out


def as_int(v):
    return int.from_bytes(v, "big", signed=True)
