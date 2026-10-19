"""Decodifica o boletim de urna (.bu.dat, ASN.1/DER) e extrai os votos por cargo."""
from der import parse, as_int

NOMINAL, BRANCO, NULO, LEGENDA = 1, 2, 3, 4


def resultados(raw):
    """-> {(eleicao, cargo): {"votos": {numero: qtd}, "brancos", "nulos", "comparecimento", "aptos"}}"""
    env = parse(raw)[0][2]
    conteudo = next(v for c, n, v in env if c == 0 and n == 4 and isinstance(v, bytes) and len(v) > 200)
    bu = parse(conteudo)[0][2]
    out = {}
    for c, n, v in bu:
        if not (isinstance(v, list) and v and all(isinstance(x, list) and len(x) >= 5 for _, _, x in v)):
            continue
        for _, _, porEleicao in v:                      # ResultadoVotacaoPorEleicao
            eleicao = as_int(porEleicao[0][2])
            aptos = as_int(porEleicao[1][2])
            lista = next(x for _, _, x in porEleicao if isinstance(x, list))
            for _, _, rv in lista:                      # ResultadoVotacao (por tipo de cargo)
                comp = as_int(rv[1][2])
                for _, _, tvc in rv[2][2]:              # TotalVotosCargo
                    cargo = as_int(tvc[0][2])
                    r = {"votos": {}, "brancos": 0, "nulos": 0, "comparecimento": comp, "aptos": aptos}
                    for _, _, vv in tvc[2][2]:          # TotalVotosVotavel
                        campos = {(cl, nm): val for cl, nm, val in vv}
                        tipo = as_int(campos[(2, 1)]); q = as_int(campos[(2, 2)])
                        if tipo == BRANCO:
                            r["brancos"] += q
                        elif tipo == NULO:
                            r["nulos"] += q
                        elif tipo == NOMINAL and (2, 3) in campos:
                            cod = as_int(campos[(2, 3)][1][2])
                            r["votos"][cod] = r["votos"].get(cod, 0) + q
                        else:                           # legenda (só em cargos proporcionais)
                            r["votos"][0] = r["votos"].get(0, 0) + q
                    out[(eleicao, cargo)] = r
        break
    return out


def confronto(r, numero_a, numero_b):
    """Reduz o resultado de um cargo ao confronto: (va, vb, outros, brancos, nulos, comparecimento, aptos)."""
    v = r["votos"]
    va, vb = v.get(numero_a, 0), v.get(numero_b, 0)
    return va, vb, sum(v.values()) - va - vb, r["brancos"], r["nulos"], r["comparecimento"], r["aptos"]
