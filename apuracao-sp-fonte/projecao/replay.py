#!/usr/bin/env python3
"""Refaz a noite de um 2º turno de Presidente com as urnas na ordem em que chegaram ao TSE,
usando exatamente o mesmo modelo do painel ao vivo.

  python3 replay.py [ANO]              -> só imprime o erro da projeção em vários pontos
  python3 replay.py ANO --gera DIR     -> grava DIR/indice.json + DIR/pontos/NNNN.json (um a cada 0,5%)

2022 usa a hora real de chegada (DT_BU_RECEBIDO). 2018 e 2014 usam a ordem simulada de
build_ordem_simulada.py (o TSE não publicou a hora de chegada nesses anos).
"""
import json, os, sys, time
from modelo import ModeloTransferencia, K_PADRAO

here = os.path.dirname(os.path.abspath(__file__))
AZUL, VERMELHO = "#0B57D0", "#C5221F"
ANOS = {
    "2022": {"data": "2022-10-30", "ordem": "real", "candidatos": {
        "a": {"nome": "Bolsonaro", "completo": "Bolsonaro (PL)", "numero": 22, "cor": AZUL},
        "b": {"nome": "Lula", "completo": "Lula (PT)", "numero": 13, "cor": VERMELHO}}},
    "2018": {"data": "2018-10-28", "ordem": "simulada", "candidatos": {
        "a": {"nome": "Bolsonaro", "completo": "Bolsonaro (PSL)", "numero": 17, "cor": AZUL},
        "b": {"nome": "Haddad", "completo": "Haddad (PT)", "numero": 13, "cor": VERMELHO}}},
    "2014": {"data": "2014-10-26", "ordem": "simulada", "candidatos": {
        "a": {"nome": "Aécio", "completo": "Aécio (PSDB)", "numero": 45, "cor": AZUL},
        "b": {"nome": "Dilma", "completo": "Dilma (PT)", "numero": 13, "cor": VERMELHO}}},
}


def carrega(ano):
    t1 = json.load(open(os.path.join(here, "base", f"{ano}_t1.json")))
    t2 = json.load(open(os.path.join(here, "base", f"{ano}_t2.json")))
    ordem = json.load(open(os.path.join(here, "base", f"{ano}_t2_ordem.json")))
    aptos = json.load(open(os.path.join(here, "base", f"{ano}_t2_aptos.json")))
    # a ordem simulada vem com o relógio de 2022: troca só a data
    data = ANOS[ano]["data"]
    inicio = f"{data}T17:00:00"
    hora = {}
    for k in t2:
        t = ordem[k]
        if ano != "2022":
            dia = "2022-10-31" if t.startswith("2022-10-31") else "2022-10-30"
            t = (data if dia == "2022-10-30" else _dia_seguinte(data)) + t[10:]
        # o TSE só começa a divulgar às 17h: o que chegou antes sai junto às 17h
        hora[k] = max(t, inicio)
    seq = sorted(t2, key=lambda k: hora[k])
    return t1, t2, hora, seq, aptos, inicio


def _dia_seguinte(data):
    from datetime import date, timedelta
    return (date.fromisoformat(data) + timedelta(days=1)).isoformat()


def roda(ano="2022", K=K_PADRAO, passo=0.5, saida=None):
    t1, t2, hora, seq, aptos, INICIO = carrega(ano)
    cfg = ANOS[ano]
    fa = sum(v[0] for v in t2.values()); fb = sum(v[1] for v in t2.values())
    final = 100 * fa / (fa + fb)
    m = ModeloTransferencia(t1, K=K)
    n = len(seq)
    pontos, validacao = [], []
    alvos_val = [5, 10, 20, 50]
    prox = passo
    lote = {"secoes": 0, "va": 0, "vb": 0}
    if saida:
        os.makedirs(os.path.join(saida, "pontos"), exist_ok=True)
        meta0 = {"modo": "replay", "ano": int(ano), "gerado_tse": INICIO + "-03:00", "candidatos": cfg["candidatos"]}
        snap = m.snapshot(meta0, guarda_historico=False)
        snap.pop("historico")
        json.dump(snap, open(os.path.join(saida, "pontos", "inicio.json"), "w"), separators=(",", ":"))
        pontos.append({"pct": 0, "arquivo": "pontos/inicio.json", "t": INICIO, "proj": None, "faixa": None,
                       "placara": None, "dif": snap["diferenca"]["primeiro_turno"], "status": "indefinido"})
    for i, k in enumerate(seq, 1):
        v = t2[k]
        m.adiciona(k, v[0], v[1], v[3] + v[4], aptos=aptos.get(k, 0))
        lote["secoes"] += 1; lote["va"] += v[0]; lote["vb"] += v[1]
        pct = 100 * i / n
        # o TSE divulga em lotes: só fecha o ponto quando muda o horário de chegada
        if pct >= prox and (i == n or hora[seq[i]] != hora[k]) or i == n:
            meta = {"modo": "replay", "ano": int(ano), "gerado_tse": hora[k] + "-03:00", "candidatos": cfg["candidatos"]}
            ul = {"secoes": lote["secoes"], "validos": lote["va"] + lote["vb"],
                  "pcta": round(100 * lote["va"] / max(lote["va"] + lote["vb"], 1), 2)}
            snap = m.snapshot(meta, ultimo_lote=ul)
            lote = {"secoes": 0, "va": 0, "vb": 0}
            pr = snap.get("projecao", {})
            erro = pr.get("pcta", final) - final
            while alvos_val and pct >= alvos_val[0]:
                validacao.append({"alvo": alvos_val.pop(0), "pct": round(pct, 2), "t": hora[k],
                                  "proja": pr.get("pcta"), "faixa": pr.get("faixa"), "erro": round(erro, 3)})
            if saida:
                nome = f"pontos/{int(round(pct * 10)):04d}.json"
                h = snap.pop("historico")[-1]
                json.dump(snap, open(os.path.join(saida, nome), "w"), separators=(",", ":"))
                pontos.append({"pct": round(pct, 2), "arquivo": nome, "t": hora[k], "proj": pr.get("pcta"),
                               "faixa": pr.get("faixa"), "placara": h["placara"], "dif": h["dif"],
                               "status": pr.get("status")})
            else:
                print(f"  {pct:6.2f}% {hora[k][11:16]}  placar {snap['placar']['pcta']:6.2f}  "
                      f"proj {pr.get('pcta', 0):7.3f}  faixa {pr.get('faixa')}  erro {erro:+.3f}  {pr.get('status')}")
            while prox <= pct:
                prox += passo
    # primeiro ponto em que a projeção cravou o vencedor e nunca mais mudou
    venc = "a" if final > 50 else "b"
    selo = None
    for p in pontos if saida else []:
        if p["status"] == venc and selo is None:
            selo = p
        elif p["status"] != venc and p["pct"] > 0:
            selo = None
    indice = {"ano": int(ano), "candidatos": cfg["candidatos"], "ordem": cfg["ordem"], "secoes": n,
              "inicio": INICIO, "fim": hora[seq[-1]],
              "final": {"va": fa, "vb": fb, "pcta": round(final, 3), "vencedor": venc},
              "selo": {"pct": selo["pct"], "t": selo["t"]} if selo else None,
              "validacao": validacao, "pontos": pontos}
    if saida:
        json.dump(indice, open(os.path.join(saida, "indice.json"), "w"), separators=(",", ":"))
    print(ano, json.dumps({"final": round(final, 3), "selo": indice["selo"], "validacao": validacao}))


if __name__ == "__main__":
    t = time.time()
    ano = next((a for a in sys.argv[1:] if a in ANOS), "2022")
    if "--gera" in sys.argv:
        roda(ano, saida=sys.argv[sys.argv.index("--gera") + 1])
    else:
        roda(ano, passo=5)
    print(f"({time.time() - t:.0f}s)")
