"""Verificação de assinatura Ed521 (EdDSA sobre a curva E-521), só com a stdlib.

É o esquema das urnas eletrônicas (certificados "AC UE20xx" do TSE, OID 1.3.6.1.4.1.44588.2.1),
definido na IN ICP-Brasil nº 15/2018 no molde do Ed448 (RFC 8032):
  curva  x² + y² = 1 + d·x²·y²  sobre p = 2^521 − 1, d = −376014, cofator 4
  hash   SHAKE256 com 132 bytes de saída
  chaves e pontos codificados em 66 bytes little-endian (y + bit de sinal de x)
"""
import hashlib

P = 2 ** 521 - 1
D = -376014 % P
L = 2 ** 519 - 337554763258501705789107630418782636071904961214051226618635150085779108655765
GX = 0x752cb45c48648b189df90cb2296b2878a3bfd9f42fc6c818ec8bf3c9c0c6203913f6ecc5ccc72434b1ae949d568fc99c6059d0fb13364838aa302a940a2f19ba6c
GY = 0xc
B = (GX, GY, 1, GX * GY % P)          # coordenadas estendidas (X, Y, Z, T)
TAM = 66


def _add(p, q):
    x1, y1, z1, t1 = p
    x2, y2, z2, t2 = q
    a = x1 * x2 % P
    b = y1 * y2 % P
    c = D * t1 % P * t2 % P
    dd = z1 * z2 % P
    e = ((x1 + y1) * (x2 + y2) - a - b) % P
    f = (dd - c) % P
    g = (dd + c) % P
    h = (b - a) % P                     # a = 1 (curva não torcida)
    return (e * f % P, g * h % P, f * g % P, e * h % P)


def _mul(k, p):
    r = (0, 1, 1, 0)
    while k:
        if k & 1:
            r = _add(r, p)
        p = _add(p, p)
        k >>= 1
    return r


def _igual(p, q):
    return (p[0] * q[2] - q[0] * p[2]) % P == 0 and (p[1] * q[2] - q[1] * p[2]) % P == 0


def _sqrt(a):
    # p ≡ 3 (mod 4): raiz = a^((p+1)/4)
    r = pow(a, (P + 1) // 4, P)
    return r if r * r % P == a % P else None


def decodifica(s):
    if len(s) != TAM:
        return None
    n = int.from_bytes(s, "little")
    sinal = n >> (8 * TAM - 1)
    y = n & ((1 << (8 * TAM - 1)) - 1)
    if y >= P:
        return None
    u = (y * y - 1) % P
    v = (D * y * y - 1) % P
    x = _sqrt(u * pow(v, P - 2, P) % P)
    if x is None:
        return None
    if x == 0 and sinal:
        return None
    if x & 1 != sinal:
        x = P - x
    return (x, y, 1, x * y % P)


def _dom(ph, ctx=b""):
    return b"SigEd521" + bytes([ph, len(ctx)]) + ctx


def verifica(pub, msg, sig, ph=0, ctx=b"", dom=True):
    """True se `sig` (132 bytes) é assinatura Ed521 válida de `msg` pela chave `pub` (66 bytes)."""
    if len(sig) != 2 * TAM or len(pub) != TAM:
        return False
    A = decodifica(pub)
    R = decodifica(sig[:TAM])
    if A is None or R is None:
        return False
    S = int.from_bytes(sig[TAM:], "little")
    if S >= L:
        return False
    pre = _dom(ph, ctx) if dom else b""
    k = int.from_bytes(hashlib.shake_256(pre + sig[:TAM] + pub + msg).digest(2 * TAM), "little") % L
    # verificação com cofator: [4][S]B == [4]R + [4][k]A
    esq = _mul(4 * S, B)
    dir_ = _mul(4, _add(R, _mul(k, A)))
    return _igual(esq, dir_)


def chave_do_certificado(pem):
    """Extrai os 66 bytes da chave pública Ed521 de um certificado PEM da urna."""
    import base64
    from der import parse
    corpo = b"".join(l for l in pem.strip().splitlines() if not l.startswith(b"-----"))
    cert = parse(base64.b64decode(corpo))[0][2]
    tbs = cert[0][2]
    for _, _, campo in tbs:
        # SubjectPublicKeyInfo = SEQ { SEQ { OID ... }, BIT STRING }
        if isinstance(campo, list) and len(campo) == 2 and isinstance(campo[0][2], list) \
                and campo[1][1] == 3 and isinstance(campo[1][2], bytes):
            bits = campo[1][2]
            return bits[1:] if bits[0] == 0 else bits
    return None
