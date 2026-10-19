"""Decodifica o boletim de urna (.bu.dat, ASN.1/DER) e extrai o resultado de Presidente."""
from der import parse, as_int

BRANCO, NULO = 2, 3


def presidente(raw, eleicao):
    """-> dict(v22, v13, outros, brancos, nulos, comparecimento, aptos) ou None."""
    env = parse(raw)[0][2]
    conteudo = next(v for c, n, v in env if c == 0 and n == 4 and isinstance(v, bytes) and len(v) > 200)
    bu = parse(conteudo)[0][2]
    for c, n, v in bu:
        if not (isinstance(v, list) and v and all(isinstance(x, list) and len(x) >= 5 for _, _, x in v)):
            continue
        for _, _, porEleicao in v:                      # ResultadoVotacaoPorEleicao
            if as_int(porEleicao[0][2]) != eleicao:
                continue
            aptos = as_int(porEleicao[1][2])
            resultados = next(x for _, _, x in porEleicao if isinstance(x, list))
            for _, _, rv in resultados:                 # ResultadoVotacao (por tipo de cargo)
                comp = as_int(rv[1][2])
                for _, _, tvc in rv[2][2]:              # TotalVotosCargo
                    if as_int(tvc[0][2]) != 1:          # 1 = Presidente
                        continue
                    r = {"v22": 0, "v13": 0, "outros": 0, "brancos": 0, "nulos": 0,
                         "comparecimento": comp, "aptos": aptos}
                    for _, _, vv in tvc[2][2]:          # TotalVotosVotavel
                        campos = {(cl, nm): val for cl, nm, val in vv}
                        tipo = as_int(campos[(2, 1)]); q = as_int(campos[(2, 2)])
                        if tipo == BRANCO:
                            r["brancos"] += q
                        elif tipo == NULO:
                            r["nulos"] += q
                        else:
                            cod = as_int(campos[(2, 3)][1][2]) if (2, 3) in campos else 0
                            r["v22" if cod == 22 else "v13" if cod == 13 else "outros"] += q
                    return r
    return None
