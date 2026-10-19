"""Confere a integridade de um boletim de urna antes de usá-lo, só com a stdlib.

Cadeia verificada para cada seção:
  1. o hash que o TSE publica no aux.json é o SHA-256 do arquivo de assinaturas (vota.vsc);
  2. o certificado da urna (dentro do .vsc) foi emitido por uma AC das urnas do TSE;
  3. o SHA-512 do bu.dat é o que a urna listou no manifesto assinado;
  4. a assinatura da urna sobre esse hash é válida (Ed521 nas UE2020/UE2022, ECDSA P-521 nas anteriores).

Chaves das ACs: AC URNA (ECDSA P-521, emitida pela AC RAIZ UE), AC UE2020 e AC UE2022 (Ed521, emitidas
pela AC URNA v2) — as mesmas usadas pelo verificador público VAR UE.
"""
import base64, hashlib

import ed521
from der import parse, read_tlv

ACS = {
    "AC URNA": ("ecdsa", bytes.fromhex(
        "04008147413ae6ec78ea597c678d458b44097fe2d642a5190c8db022f078f85f6f1eaaf0d3fb5bea96ac757c30c7175189ae68"
        "236d54acab0dd9fd15c42b5618f033cf01cf3d7498e30f5b48883f7af2c35c567d40d28a116b7cdf1cf3d54ea7b1dd87f97236"
        "b0d48e5904b8f3965843b9e74e14603e146c62c6c229be869adec94cdb9d92")),
    "AC UE2020": ("ed521", bytes.fromhex(
        "5d3d764d1123a914efbf93892db3b63d2f3c5d37a0f14a2d36d44905cc7428b974355171df78c2a064e630b308b061a47fb0bd"
        "55715fc5b69419bfc92ed570aeb901")),
    "AC UE2022": ("ed521", bytes.fromhex(
        "371388c00ed81269ca7dd05735396caa96a8205efd7e2e96cf16557b52475e64e9289eb647684bcee2464d889b7155cec8af24"
        "f2be4d21a1a3ab15805cdf55d4ec00")),
}
OID_ECDSA = bytes.fromhex("2a8648ce3d0201")
OID_ED521 = bytes.fromhex("2b0601040182dc2c0201")

# ---------------------------------------------------------------- ECDSA P-521 (secp521r1)
_P = 2 ** 521 - 1
_A = _P - 3
_N = 0x01fffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffa51868783bf2f966b7fcc0148f709a5d03bb5c9b8899c47aebb6fb71e91386409
_G = (0x00c6858e06b70404e9cd9e3ecb662395b4429c648139053fb521f828af606b4d3dbaa14b5e77efe75928fe1dc127a2ffa8de3348b3c1856a429bf97e7e31c2e5bd66,
      0x011839296a789a3bc0045c8a5fb42c7d1bd998f54449579b446817afbd17273e662c97ee72995ef42640c550b9013fad0761353c7086a272c24088be94769fd16650)


def _jadd(p, q):
    if p is None:
        return q
    if q is None:
        return p
    x1, y1, z1 = p; x2, y2, z2 = q
    z1z1 = z1 * z1 % _P; z2z2 = z2 * z2 % _P
    u1 = x1 * z2z2 % _P; u2 = x2 * z1z1 % _P
    s1 = y1 * z2 * z2z2 % _P; s2 = y2 * z1 * z1z1 % _P
    if u1 == u2:
        return _jdbl(p) if s1 == s2 else None
    h = (u2 - u1) % _P; r = (s2 - s1) % _P
    hh = h * h % _P; hhh = h * hh % _P
    x3 = (r * r - hhh - 2 * u1 * hh) % _P
    y3 = (r * (u1 * hh - x3) - s1 * hhh) % _P
    return (x3, y3, h * z1 * z2 % _P)


def _jdbl(p):
    if p is None:
        return None
    x, y, z = p
    if y == 0:
        return None
    yy = y * y % _P; zz = z * z % _P
    s = 4 * x * yy % _P
    m = 3 * (x - zz) * (x + zz) % _P          # a = -3
    x3 = (m * m - 2 * s) % _P
    return (x3, (m * (s - x3) - 8 * yy * yy) % _P, 2 * y * z % _P)


def _jmul2(k1, p1, k2, p2):
    """k1·P1 + k2·P2 (truque de Shamir)."""
    p1 = (p1[0], p1[1], 1); p2 = (p2[0], p2[1], 1)
    p12 = _jadd(p1, p2)
    r = None
    for i in range(max(k1.bit_length(), k2.bit_length()) - 1, -1, -1):
        r = _jdbl(r)
        b1, b2 = (k1 >> i) & 1, (k2 >> i) & 1
        if b1 and b2:
            r = _jadd(r, p12)
        elif b1:
            r = _jadd(r, p1)
        elif b2:
            r = _jadd(r, p2)
    return r


def ecdsa_p521(pub, digest, sig):
    """pub = 04||x||y (133 bytes); sig = DER(r,s) ou r||s (132 bytes); digest = hash já calculado."""
    if len(pub) != 133 or pub[0] != 4:
        return False
    Q = (int.from_bytes(pub[1:67], "big"), int.from_bytes(pub[67:], "big"))
    if sig[:1] == b"\x30":
        r, s = (int.from_bytes(v, "big") for _, _, v in parse(sig)[0][2])
    elif len(sig) == 132:
        r, s = int.from_bytes(sig[:66], "big"), int.from_bytes(sig[66:], "big")
    else:
        return False
    if not (0 < r < _N and 0 < s < _N):
        return False
    e = int.from_bytes(digest, "big")
    if len(digest) * 8 > 521:
        e >>= len(digest) * 8 - 521
    w = pow(s, -1, _N)
    pt = _jmul2(e * w % _N, _G, r * w % _N, Q)
    if pt is None:
        return False
    x, _, z = pt
    return (x * pow(z * z % _P, -1, _P)) % _P % _N == r


# ---------------------------------------------------------------- certificado
def _pem_para_der(pem):
    if not pem.startswith(b"-----"):
        return pem
    return base64.b64decode(b"".join(l for l in pem.strip().splitlines() if not l.startswith(b"-----")))


def _cn(nome):
    for _, _, rdn in nome:
        for _, _, atv in rdn:
            if atv[0][2] == b"\x55\x04\x03":
                return atv[1][2].decode("utf-8", "replace")
    return None


def _le_certificado(pem):
    der = _pem_para_der(pem)
    _, _, _, s, e = read_tlv(der, 0)
    der = der[:e]                       # alguns certificados (UE2015) vêm com um byte sobrando no fim
    _, _, _, _, te = read_tlv(der, s)
    tbs_raw = der[s:te]
    cert = parse(der)[0][2]
    tbs = cert[0][2]
    sig = cert[2][2]
    sig = sig[1:] if sig[:1] == b"\x00" else sig
    nomes = [x for _, _, x in tbs if isinstance(x, list) and x and isinstance(x[0][2], list) and x[0][1] == 17]
    spki = next(x for _, _, x in tbs if isinstance(x, list) and len(x) == 2 and isinstance(x[0][2], list) and x[1][1] == 3)
    chave = spki[1][2][1:] if spki[1][2][:1] == b"\x00" else spki[1][2]
    return {"emissor": _cn(nomes[0]), "titular": _cn(nomes[-1]), "oid": spki[0][2][0][2],
            "chave": chave, "tbs": tbs_raw, "assinatura": sig}


def _assina_ok(tipo, chave, msg_ed, digest_ec, sig):
    if tipo == "ed521":
        return ed521.verifica(chave, msg_ed, sig)
    return ecdsa_p521(chave, digest_ec, sig)


# ---------------------------------------------------------------- boletim
def confere(hash_aux, vsc, bu, nome_bu):
    """Retorna (True, modelo) se a cadeia fecha, ou (False, motivo)."""
    try:
        publicado = bytes.fromhex(hash_aux).decode()
    except ValueError:
        return False, "hash do aux ilegível"
    # o TSE usa base64 padrão com "/" trocado por "-"
    if base64.b64encode(hashlib.sha256(vsc).digest()).decode().replace("/", "-") != publicado.replace("_", "-"):
        return False, "vsc não confere com o hash publicado pelo TSE"
    try:
        blocos = parse(vsc)[0][2]
        hw = blocos[1][2]                                     # assinaturaHW (urna)
        conteudo, pem = hw[3][2], hw[4][2]
        cert = _le_certificado(pem)
    except Exception:
        return False, "arquivo de assinaturas ilegível"
    ac = ACS.get(cert["emissor"])
    if not ac:
        return False, f"certificado emitido por AC desconhecida ({cert['emissor']})"
    tipo_ac, chave_ac = ac
    if not _assina_ok(tipo_ac, chave_ac, cert["tbs"], hashlib.sha512(cert["tbs"]).digest(), cert["assinatura"]):
        return False, "certificado da urna não foi assinado pela AC do TSE"
    tipo_urna = "ed521" if cert["oid"] == OID_ED521 else "ecdsa" if cert["oid"] == OID_ECDSA else None
    if tipo_urna is None:
        return False, "tipo de chave da urna desconhecido"
    try:
        manifesto = parse(conteudo)[0][2][0][2]
    except Exception:
        return False, "manifesto ilegível"
    for _, _, item in manifesto:
        if item[0][2].decode("latin-1") != nome_bu:
            continue
        h, sig = item[1][2][1][2], item[1][2][2][2]
        if hashlib.sha512(bu).digest() != h:
            return False, "bu.dat não confere com o hash assinado pela urna"
        d = hashlib.sha512(h).digest()
        if not _assina_ok(tipo_urna, cert["chave"], d, d, sig):
            return False, "assinatura da urna inválida"
        return True, cert["emissor"]
    return False, "bu.dat ausente do manifesto assinado"
