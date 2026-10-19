# Projeção do 2º turno — Presidente 2026 (GR Data)

Painel público: **https://grisonet.github.io/apuracao-sp/projecao.html**
(fonte da página: `GR Data/apuracao-sp/projecao.html`; replay estático em `apuracao-sp/projecao/replay2022/`).

Engenharia reversa do *Apuração Aberta* (Diogo Machado): cada seção do 2º turno é
comparada com ela mesma no 1º turno, e uma matriz de transferência por município
(encolhida para capital/interior → UF → Brasil) projeta as seções que faltam.

## Peças

| Arquivo | O que faz |
|---|---|
| `build_base.py` | `raw/votacao_secao_{ano}_BR.zip` (dados abertos TSE) → `base/{ano}_t{turno}.json` = `{"UF\|MUN\|ZONA\|SECAO": [v22, v13, outros, brancos, nulos]}` |
| `build_ordem.py` | `raw/bweb22/bweb_2t_*.zip` → hora de chegada (`DT_BU_RECEBIDO`) e aptos de cada seção em 2022 |
| `der.py` / `bu.py` | leitor ASN.1/DER e extração de Presidente do boletim de urna (`.bu.dat`) — validado 8/8 contra a base oficial |
| `modelo.py` | `ModeloTransferencia`: somas acumuladas, projeção, faixa provável, métricas por região/UF e `snapshot()` (mesmo JSON no ao vivo e no replay) |
| `replay.py` | refaz a noite de 2022 na ordem real; `--gera out/replay2022` grava os 201 pontos para o site |
| `coletor.py` | ao vivo: lê `arquivo-urna/3221/config/<uf>` → seções novas → aux + bu.dat → modelo → `snapshot.json` + `dados.csv`, servidos por HTTP com CORS |
| `deploy/` | pasta enxuta enviada ao Railway (código + `base/2026_t1.json` + Dockerfile) |

## Endpoints do TSE (sem auth, CORS liberado)

- Lista de seções por UF (com `da`/`ha` quando a seção chegou):
  `https://resultados.tse.jus.br/oficial/ele2026/arquivo-urna/{pleito}/config/{uf}/{uf}-p00{pleito}-cs.json`
- Arquivos de uma seção: `.../arquivo-urna/{pleito}/dados/{uf}/{mun5}/{zona4}/{secao4}/p00{pleito}-{uf}-m{mun5}-z{zona4}-s{secao4}-aux.json`
  → `.../{hash}/{nome}-bu.dat`
- Pleitos: **3220** = 1º turno (04/10), **3221** = 2º turno (25/10). Eleições: 6257/6258 federal (Presidente), 6259/6260 estadual.
- Boletim: `EntidadeEnvelopeGenerico` → conteúdo → `resultadosVotacaoPorEleicao` → cargo 1 → votáveis
  (`tipoVoto` 1 nominal, 2 branco, 3 nulo, 4 legenda; identificação = (partido, código)).

## Validação (2º turno de 2022, ordem real de chegada)

| Seções | Erro da projeção | Faixa |
|---|---|---|
| 5% | 0,01 pt | ±0,21 |
| 10% | 0,04 pt | ±0,16 |
| 20% | 0,06 pt | ±0,13 |
| 50% | 0,01 pt | ±0,09 |

Selo (vencedor cravado e nunca mais mudou): Lula às 17:13, com 1,0% das seções.
Faixa = √((2·sd)² + (0,10·√(1−f))² + (0,40/√pct)²); nunca indica vencedor antes de 1%.

## Rodar

```bash
python3 replay.py                       # erro em vários pontos
python3 replay.py --gera out/replay2022 # arquivos do site (copiar p/ GR Data/apuracao-sp/projecao/)
python3 coletor.py                      # ao vivo, serve :8787
ENSAIO=1 UFS=ac,rr python3 coletor.py   # ensaio com o 1º turno
```

Variáveis: `PLEITO`, `ELEICAO`, `SAIDA`, `PORT`, `INTERVALO` (30), `THREADS`, `LOTE` (publica a cada N seções),
`REQ_POR_SEG` (limitador global; o TSE devolve 429 acima do limite), `UFS`.

## Hospedagem

Railway, projeto `griso-site`, serviço `grdata-apuracao` (volume `/data`):
https://grdata-apuracao-production.up.railway.app/snapshot.json — a página lê daí (`?fonte=` sobrescreve).
