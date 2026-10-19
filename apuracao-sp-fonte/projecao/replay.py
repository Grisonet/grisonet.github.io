#!/usr/bin/env python3
"""Refaz a noite do 2º turno de 2022 com as urnas na ordem em que chegaram ao TSE,
usando exatamente o mesmo modelo do painel ao vivo.

  python3 replay.py              -> só imprime o erro da projeção em vários pontos
  python3 replay.py --gera DIR   -> grava DIR/indice.json + DIR/pontos/NNNN.json (um a cada 0,5%)
"""
import json, os, sys, time
from modelo import ModeloTransferencia, K_PADRAO

here = os.path.dirname(os.path.abspath(__file__))
INICIO = "2022-10-30T17:00:00"


def carrega():
    t1 = json.load(open(os.path.join(here, "base", "2022_t1.json")))
    t2 = json.load(open(os.path.join(here, "base", "2022_t2.json")))
    ordem = json.load(open(os.path.join(here, "base", "2022_t2_ordem.json")))
    # o TSE só começa a divulgar às 17h: o que chegou antes sai junto às 17h
    hora = {k: max(ordem[k], INICIO) for k in t2}
    seq = sorted(t2, key=lambda k: hora[k])
    aptos = json.load(open(os.path.join(here, "base", "2022_t2_aptos.json")))
    return t1, t2, hora, seq, aptos


def roda(K=K_PADRAO, passo=0.5, saida=None):
    t1, t2, hora, seq, aptos = carrega()
    f22 = sum(v[0] for v in t2.values()); f13 = sum(v[1] for v in t2.values())
    final = 100 * f22 / (f22 + f13)
    m = ModeloTransferencia(t1, K=K)
    n = len(seq)
    pontos, validacao = [], []
    alvos_val = [5, 10, 20, 50]
    prox = passo
    lote = {"secoes": 0, "v22": 0, "v13": 0}
    if saida:
        os.makedirs(os.path.join(saida, "pontos"), exist_ok=True)
        meta0 = {"modo": "replay", "ano": 2022, "gerado_tse": INICIO + "-03:00"}
        snap = m.snapshot(meta0, guarda_historico=False)
        snap.pop("historico")
        json.dump(snap, open(os.path.join(saida, "pontos", "inicio.json"), "w"), separators=(",", ":"))
        pontos.append({"pct": 0, "arquivo": "pontos/inicio.json", "t": INICIO, "proj": None, "faixa": None,
                       "placar22": None, "dif": snap["diferenca"]["primeiro_turno"], "status": "indefinido"})
    for i, k in enumerate(seq, 1):
        v = t2[k]
        m.adiciona(k, v[0], v[1], v[3] + v[4], aptos=aptos[k])
        lote["secoes"] += 1; lote["v22"] += v[0]; lote["v13"] += v[1]
        pct = 100 * i / n
        # o TSE divulga em lotes: só fecha o ponto quando muda o horário de chegada
        if pct >= prox and (i == n or hora[seq[i]] != hora[k]) or i == n:
            meta = {"modo": "replay", "ano": 2022, "gerado_tse": hora[k] + "-03:00"}
            ul = {"secoes": lote["secoes"], "validos": lote["v22"] + lote["v13"],
                  "pct22": round(100 * lote["v22"] / max(lote["v22"] + lote["v13"], 1), 2)}
            snap = m.snapshot(meta, ultimo_lote=ul)
            lote = {"secoes": 0, "v22": 0, "v13": 0}
            pr = snap.get("projecao", {})
            erro = pr.get("pct22", final) - final
            while alvos_val and pct >= alvos_val[0]:
                validacao.append({"alvo": alvos_val.pop(0), "pct": round(pct, 2), "t": hora[k],
                                  "proj22": pr.get("pct22"), "faixa": pr.get("faixa"), "erro": round(erro, 3)})
            if saida:
                nome = f"pontos/{int(round(pct * 10)):04d}.json"
                h = snap.pop("historico")[-1]
                json.dump(snap, open(os.path.join(saida, nome), "w"), separators=(",", ":"))
                pontos.append({"pct": round(pct, 2), "arquivo": nome, "t": hora[k], "proj": pr.get("pct22"),
                               "faixa": pr.get("faixa"), "placar22": h["placar22"], "dif": h["dif"],
                               "status": pr.get("status")})
            else:
                print(f"  {pct:6.2f}% {hora[k][11:16]}  placar {snap['placar']['pct22']:6.2f}  "
                      f"proj {pr.get('pct22', 0):7.3f}  faixa {pr.get('faixa')}  erro {erro:+.3f}  {pr.get('status')}")
            while prox <= pct:
                prox += passo
    # primeiro ponto em que a projeção cravou o vencedor e nunca mais mudou
    venc = "22" if final > 50 else "13"
    selo = None
    for p in pontos if saida else []:
        if p["status"] == venc and selo is None:
            selo = p
        elif p["status"] != venc and p["pct"] > 0:
            selo = None
    indice = {"ano": 2022, "nomes": {"22": "Bolsonaro", "13": "Lula"}, "secoes": n,
              "inicio": INICIO, "fim": hora[seq[-1]],
              "final": {"v22": f22, "v13": f13, "pct22": round(final, 3), "vencedor": venc},
              "selo": {"pct": selo["pct"], "t": selo["t"]} if selo else None,
              "validacao": validacao, "pontos": pontos}
    if saida:
        json.dump(indice, open(os.path.join(saida, "indice.json"), "w"), separators=(",", ":"))
    print(json.dumps({"final": round(final, 3), "selo": indice["selo"], "validacao": validacao}, indent=1))


if __name__ == "__main__":
    t = time.time()
    if "--gera" in sys.argv:
        roda(saida=sys.argv[sys.argv.index("--gera") + 1])
    else:
        roda(passo=5)
    print(f"({time.time() - t:.0f}s)")
