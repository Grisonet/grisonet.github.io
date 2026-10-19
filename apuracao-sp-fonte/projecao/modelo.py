"""Projeção do 2º turno de Presidente comparando cada seção com ela mesma no 1º turno.

Numa seção votam as mesmas pessoas nos dois turnos. Em cada grupo de seções
(município → UF×capital/interior → UF → Brasil) estimamos, com as seções já
apuradas, uma "matriz de transferência":

    v22_2t = a1·v22_1t + a2·v13_1t + a3·outros_1t + a4·brancos/nulos_1t
    v13_2t = b1·v22_1t + b2·v13_1t + b3·outros_1t + b4·brancos/nulos_1t

ou seja, quanto de cada bloco do 1º turno foi para cada lado (o que falta para
1 virou abstenção, branco ou nulo). Grupo com poucas seções apuradas é puxado
para o grupo de cima (K seções fictícias com a composição do próprio grupo e o
comportamento do pai). As seções que faltam recebem o 1º turno delas passado
pela matriz do seu município e somam-se ao placar real.

Tudo sai de somas acumuladas: recalcular a cada lote leva ~1 s, só com a stdlib.
Validado com a apuração real do 2º turno de 2022 (ver replay.py).
"""
import math

CAPITAIS = {
    "AC|1392", "AL|27855", "AM|2550", "AP|6050", "BA|38490", "CE|13897", "DF|97012",
    "ES|57053", "GO|93734", "MA|9210", "MG|41238", "MS|90514", "MT|90670", "PA|4278",
    "PB|20516", "PE|25313", "PI|12190", "PR|75353", "RJ|60011", "RN|17612", "RO|35",
    "RR|3018", "RS|88013", "SC|81051", "SE|31054", "SP|71072", "TO|73440",
}
REGIAO = {
    "AC": "Norte", "AM": "Norte", "AP": "Norte", "PA": "Norte", "RO": "Norte", "RR": "Norte", "TO": "Norte",
    "AL": "Nordeste", "BA": "Nordeste", "CE": "Nordeste", "MA": "Nordeste", "PB": "Nordeste",
    "PE": "Nordeste", "PI": "Nordeste", "RN": "Nordeste", "SE": "Nordeste",
    "DF": "Centro-Oeste", "GO": "Centro-Oeste", "MS": "Centro-Oeste", "MT": "Centro-Oeste",
    "ES": "Sudeste", "MG": "Sudeste", "RJ": "Sudeste", "SP": "Sudeste",
    "PR": "Sul", "RS": "Sul", "SC": "Sul", "ZZ": "Exterior",
}
REGIOES = ["Norte", "Nordeste", "Centro-Oeste", "Sudeste", "Sul", "Exterior"]
NF = 4
K_PADRAO = 10.0


def grupos(chave):
    """Cadeia de grupos da seção, do mais fino ao mais grosso."""
    uf, mun = chave.split("|")[:2]
    um = f"{uf}|{mun}"
    return (f"m:{um}", f"e:{uf}|{'cap' if um in CAPITAIS else 'int'}", f"u:{uf}", "br")


def _x(v):
    return (float(v[0]), float(v[1]), float(v[2]), float(v[3] + v[4]))


def _solve(A, b):
    """Resolve A·x = b (4×4) por eliminação de Gauss com pivoteamento."""
    n = len(b)
    M = [list(A[i]) + [b[i]] for i in range(n)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(M[r][c]))
        M[c], M[p] = M[p], M[c]
        if abs(M[c][c]) < 1e-9:
            return None
        for r in range(n):
            if r != c and M[r][c]:
                f = M[r][c] / M[c][c]
                for k in range(c, n + 1):
                    M[r][k] -= f * M[c][k]
    return [M[i][n] / M[i][i] for i in range(n)]


class Grupo:
    __slots__ = ("n", "xx", "sx", "xyF", "xyL", "xyM", "yyM")

    def __init__(self):
        self.n = 0
        self.xx = [[0.0] * NF for _ in range(NF)]
        self.sx = [0.0] * NF
        self.xyF = [0.0] * NF; self.xyL = [0.0] * NF; self.xyM = [0.0] * NF
        self.yyM = 0.0

    def soma_x(self, x):
        self.n += 1
        for i in range(NF):
            xi = x[i]
            self.sx[i] += xi
            row = self.xx[i]
            for j in range(NF):
                row[j] += xi * x[j]


class Painel:
    """Placar e métricas descritivas de uma área (Brasil, região ou UF)."""
    __slots__ = ("total", "ap", "v22", "v13", "bn", "comp1", "comp2", "aptos", "saldo",
                 "a22", "a13", "vir22", "vir13", "m1", "casadas", "proj22", "proj13")

    def __init__(self):
        self.total = self.ap = self.v22 = self.v13 = self.bn = 0
        self.comp1 = self.comp2 = self.aptos = self.saldo = 0
        self.a22 = self.a13 = self.vir22 = self.vir13 = self.m1 = self.casadas = 0
        self.proj22 = self.proj13 = 0.0


class ModeloTransferencia:
    def __init__(self, base, K=K_PADRAO):
        """base: {"UF|MUN|ZONA|SECAO": [v22, v13, outros, brancos, nulos]} do 1º turno."""
        self.K = K
        self.base = base
        self.cadeia = {}
        self.tot, self.ap, self.pai = {}, {}, {}
        self.areas = {"BR": Painel(), **{r: Painel() for r in REGIOES}}
        for k, v in base.items():
            cad = self.cadeia[k] = grupos(k)
            x = _x(v)
            for i, g in enumerate(cad):
                if g not in self.tot:
                    self.tot[g] = Grupo(); self.ap[g] = Grupo()
                    self.pai[g] = cad[i + 1] if i + 1 < len(cad) else None
                self.tot[g].soma_x(x)
            for a in self._areas(k):
                a.total += 1
                a.m1 += v[0] - v[1]
        self.ordem = sorted(self.tot, key=lambda g: "bueom".index(g[0]))
        self.folhas = [g for g in self.tot if g[0] == "m"]
        self.feitas = {}
        self.extra = 0
        self.historico = []
        self.status_desde = None
        self._status_ant = None

    def _areas(self, chave):
        uf = chave[:2]
        if uf not in self.areas:
            self.areas[uf] = Painel()
        return (self.areas["BR"], self.areas[REGIAO.get(uf, "Exterior")], self.areas[uf])

    # ------------------------------------------------------------------
    def adiciona(self, chave, v22, v13, bn=0, comp=None, aptos=0):
        """Registra uma seção apurada no 2º turno. comp = comparecimento (None = v22+v13+bn)."""
        if chave in self.feitas:
            return False
        comp = v22 + v13 + bn if comp is None else comp
        self.feitas[chave] = (v22, v13, bn)
        b = self.base.get(chave)
        for a in self._areas(chave):
            a.ap += 1; a.v22 += v22; a.v13 += v13; a.bn += bn
            if b is not None:
                a.casadas += 1
                a.comp1 += sum(b); a.comp2 += comp; a.aptos += aptos or sum(b)
                m1, m2 = b[0] - b[1], v22 - v13
                a.saldo += m2 - m1
                a.a22 += m2 > m1; a.a13 += m2 < m1
                if m1 < 0 < m2:
                    a.vir22 += 1
                elif m2 < 0 < m1:
                    a.vir13 += 1
            else:
                a.total += 1         # seção nova (agregação diferente): entra só no placar
        if b is None:
            self.extra += 1
            return True
        x = _x(b)
        m = v22 - v13
        for g in self.cadeia[chave]:
            a = self.ap[g]
            a.soma_x(x)
            for i in range(NF):
                a.xyF[i] += x[i] * v22; a.xyL[i] += x[i] * v13; a.xyM[i] += x[i] * m
            a.yyM += m * m
        return True

    # ------------------------------------------------------------------
    def _coef(self):
        co = {}
        for g in self.ordem:
            a, t, p = self.ap[g], self.tot[g], self.pai[g]
            if p is None:   # Brasil: prior fraco — cada um mantém o seu voto, outros divididos
                bF, bL, s2p = (0.85, 0.05, 0.4, 0.05), (0.05, 0.85, 0.4, 0.05), 400.0
            else:
                bF, bL, s2p = co[p][0], co[p][1], co[p][2]
            alfa = self.K / max(t.n, 1)
            A = [[a.xx[i][j] + alfa * t.xx[i][j] for j in range(NF)] for i in range(NF)]
            P = [sum(alfa * t.xx[i][j] * bF[j] for j in range(NF)) for i in range(NF)]
            Q = [sum(alfa * t.xx[i][j] * bL[j] for j in range(NF)) for i in range(NF)]
            cF = _solve(A, [a.xyF[i] + P[i] for i in range(NF)]) or list(bF)
            cL = _solve(A, [a.xyL[i] + Q[i] for i in range(NF)]) or list(bL)
            if a.n > NF + 2:
                cM = [cF[i] - cL[i] for i in range(NF)]
                rss = a.yyM - 2 * sum(cM[i] * a.xyM[i] for i in range(NF)) + \
                    sum(cM[i] * a.xx[i][j] * cM[j] for i in range(NF) for j in range(NF))
                s2 = max(rss / (a.n - NF), 1.0)
            else:
                s2 = s2p
            co[g] = (cF, cL, s2)
        return co

    def projeta(self):
        """Projeção do resultado final: fatia do 22 nos votos válidos + faixa provável."""
        br = self.areas["BR"]
        if self.ap["br"].n == 0:
            return None
        co = self._coef()
        for a in self.areas.values():
            a.proj22, a.proj13 = float(a.v22), float(a.v13)
        var_ind = 0.0
        margem_estrato = {}
        for g in self.folhas:
            t, a = self.tot[g], self.ap[g]
            nR = t.n - a.n
            if nR <= 0:
                continue
            xR = [t.sx[i] - a.sx[i] for i in range(NF)]
            cF, cL, s2 = co[g]
            f = max(sum(cF[i] * xR[i] for i in range(NF)), 0.0)
            l = max(sum(cL[i] * xR[i] for i in range(NF)), 0.0)
            uf = g[2:4]
            for ar in (br, self.areas[REGIAO.get(uf, "Exterior")], self.areas[uf]):
                ar.proj22 += f; ar.proj13 += l
            var_ind += s2 * nR
            e = self.pai[g]
            margem_estrato[e] = margem_estrato.get(e, 0) + nR
        # incerteza dos coeficientes, correlacionada dentro de cada estrato
        var_par = sum(co[e][2] * nR * nR / (self.ap[e].n + self.K) for e, nR in margem_estrato.items())
        tot = br.proj22 + br.proj13
        pct = 100 * br.proj22 / tot
        sd = 100 * math.sqrt(var_ind + var_par) / (2 * tot)
        # faixa provável: erro estatístico + termo sistemático calibrado no replay de 2022
        # (a ordem de chegada das urnas não é aleatória dentro dos estratos)
        f_ap = br.casadas / max(br.total, 1)
        pct_ap = max(100 * f_ap, 0.05)
        meia = math.sqrt((2 * sd) ** 2 + (0.10 * math.sqrt(max(1 - f_ap, 0))) ** 2 + (0.40 / math.sqrt(pct_ap)) ** 2)
        if f_ap >= 0.9999:
            meia = 0.0
        faixa = [pct - meia, pct + meia]
        status = "indefinido"
        if pct_ap >= 1:          # nunca indica vencedor antes de 1% das seções
            status = "22" if faixa[0] > 50 else "13" if faixa[1] < 50 else "indefinido"
        if status != self._status_ant:
            self.status_desde = round(100 * br.ap / max(br.total, 1), 2) if status != "indefinido" else None
            self._status_ant = status
        transf = co["br"]
        return {"pct22": pct, "faixa": faixa, "status": status, "desde_pct": self.status_desde,
                "v22": br.proj22, "v13": br.proj13, "sd": sd,
                "transferencia_outros": [transf[0][2], transf[1][2]]}

    # ------------------------------------------------------------------
    def snapshot(self, meta, ultimo_lote=None, guarda_historico=True):
        """Monta o JSON publicado (mesmo formato no ao vivo e no replay)."""
        br = self.areas["BR"]
        p = self.projeta()
        pct_ap = round(100 * br.ap / max(br.total, 1), 2)

        def pct(a, b):
            return round(100 * a / (a + b), 2) if a + b else None

        def area(nome, a):
            d = {"nome": nome, "apurado_pct": round(100 * a.ap / max(a.total, 1), 1),
                 "v22": a.v22, "v13": a.v13, "pct22": pct(a.v22, a.v13),
                 "saldo": a.saldo, "a22_pct": round(100 * a.a22 / a.casadas, 1) if a.casadas else 0,
                 "a13_pct": round(100 * a.a13 / a.casadas, 1) if a.casadas else 0,
                 "comp_delta": round(100 * (a.comp2 - a.comp1) / a.aptos, 2) if a.aptos else None,
                 "m1": a.m1}
            if p:
                d["proj22"] = pct(a.proj22, a.proj13)
            return d

        snap = dict(meta)
        snap.update({
            "secoes": {"total": br.total, "apuradas": br.ap, "pct": pct_ap,
                       "casadas": br.casadas, "sem_par": self.extra},
            "placar": {"v22": br.v22, "v13": br.v13, "pct22": pct(br.v22, br.v13), "bn": br.bn},
            "diferenca": {"primeiro_turno": br.m1, "saldo": br.saldo, "atual": br.m1 + br.saldo,
                          "a22_pct": round(100 * br.a22 / br.casadas, 1) if br.casadas else 0,
                          "a13_pct": round(100 * br.a13 / br.casadas, 1) if br.casadas else 0,
                          "viraram22": br.vir22, "viraram13": br.vir13},
            "comparecimento_delta": round(100 * (br.comp2 - br.comp1) / br.aptos, 2) if br.aptos else None,
            "ultimo_lote": ultimo_lote,
            "regioes": [area(r, self.areas[r]) for r in REGIOES if self.areas[r].total],
            "estados": [area(uf, self.areas[uf]) for uf in sorted(k for k in self.areas if len(k) == 2 and k != "BR")],
        })
        if p:
            to = p["transferencia_outros"]
            snap["projecao"] = {"pct22": round(p["pct22"], 3), "faixa": [round(x, 3) for x in p["faixa"]],
                                "status": p["status"], "desde_pct": p["desde_pct"],
                                "v22": round(p["v22"]), "v13": round(p["v13"])}
            snap["transferencia"] = {"outros22": round(100 * to[0], 1), "outros13": round(100 * to[1], 1),
                                     "outros_bn": round(100 * (1 - to[0] - to[1]), 1)}
        if guarda_historico:
            ponto = {"t": meta.get("gerado_tse"), "pct": pct_ap, "placar22": snap["placar"]["pct22"],
                     "dif": br.m1 + br.saldo}
            if p:
                ponto.update({"proj": round(p["pct22"], 3), "faixa": [round(x, 3) for x in p["faixa"]]})
            if not self.historico or self.historico[-1]["pct"] != pct_ap:
                self.historico.append(ponto)
        snap["historico"] = self.historico
        return snap
