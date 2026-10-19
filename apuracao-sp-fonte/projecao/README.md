# Projeção do 2º turno 2026 — Presidente e governadores (GR Data)

Painel público: **https://grisonet.github.io/apuracao-sp/projecao.html**
(fonte da página: `GR Data/apuracao-sp/projecao.html`; replay estático em `apuracao-sp/projecao/replay2022/`).

Cada seção do 2º turno é
comparada com ela mesma no 1º turno, e uma matriz de transferência por município
(encolhida para capital/interior → UF → Brasil) projeta as seções que faltam.

## Peças

| Arquivo | O que faz |
|---|---|
| `build_base.py` | `votacao_secao_{ano}_{BR\|UF}.zip` (dados abertos TSE) → `base/<nome>.json` = `{"UF\|MUN\|ZONA\|SECAO": [va, vb, outros, brancos, nulos]}`; `--numeros A,B --cargo --uf` |
| `build_ordem.py` | `raw/bweb22/bweb_2t_*.zip` → hora real de chegada (`DT_BU_RECEBIDO`) e aptos de cada seção em 2022 |
| `build_ordem_simulada.py` | 2018/2014 (o TSE não publicou a hora de chegada): cada seção recebe o horário de uma seção do mesmo município em 2022, no mesmo quantil; + aptos do bweb |
| `der.py` / `bu.py` | leitor ASN.1/DER; `resultados()` extrai todos os cargos/eleições do boletim, `confronto()` reduz a (va, vb, outros, br, nu, comp, aptos) |
| `ed521.py` | verificação EdDSA Ed521 (curva E-521, SHAKE256-132, prefixo "SigEd521") em Python puro, ~14 ms |
| `integridade.py` | cadeia: hash do aux (= base64 do SHA-256 do .vsc, com "/"→"-") → certificado da urna emitido por AC URNA (ECDSA P-521) / AC UE2020 / AC UE2022 (Ed521) → SHA-512 do bu.dat no manifesto → assinatura da urna sobre SHA-512(hash). 300/300 seções reais OK, adulterações rejeitadas |
| `modelo.py` | `ModeloTransferencia`: somas acumuladas, estrato UF×(capital\|interior ≥150 seções\|interior pequeno), faixa calibrada em 2014/2018/2022, painéis por região/UF e (estaduais) por município/zona, `snapshot()` |
| `disputas.py` | Presidente + governadores com 2º turno (AC, AM, DF, ES, RN, TO): eleição, cargo, base, candidatos "a" (1º no 1º turno) e "b", cores |
| `replay.py` | refaz 2022 (ordem real), 2018 e 2014 (ordem simulada); `python3 replay.py ANO --gera out/replayANO` |
| `coletor.py` | ao vivo: config → aux + .vsc + bu.dat (threads) → integridade + decodificação (pool de processos) → modelo de cada disputa → `snapshot.json` + `dados.csv` (e `governador/<uf>/...`); modo `RELAY=1` só serve |
| `noite.sh` | roda o coletor no Mac na noite (caffeinate, reinício automático, envio ao relay) |
| `deploy/` | pasta enviada ao Railway (relay) |

## Endpoints do TSE (sem auth, CORS liberado)

- Lista de seções por UF (com `da`/`ha` quando a seção chegou):
  `https://resultados.tse.jus.br/oficial/ele2026/arquivo-urna/{pleito}/config/{uf}/{uf}-p00{pleito}-cs.json`
- Arquivos de uma seção: `.../arquivo-urna/{pleito}/dados/{uf}/{mun5}/{zona4}/{secao4}/p00{pleito}-{uf}-m{mun5}-z{zona4}-s{secao4}-aux.json`
  → `.../{hash}/{nome}-bu.dat`
- Pleitos: **3220** = 1º turno (04/10), **3221** = 2º turno (25/10). Eleições: 6257/6258 federal (Presidente), 6259/6260 estadual.
- Boletim: `EntidadeEnvelopeGenerico` → conteúdo → `resultadosVotacaoPorEleicao` → cargo 1 → votáveis
  (`tipoVoto` 1 nominal, 2 branco, 3 nulo, 4 legenda; identificação = (partido, código)).

## Validação (erro da projeção, em pontos)

| Seções | 2022 (ordem real) | 2018 (simulada) | 2014 (simulada) |
|---|---|---|---|
| 5% | 0,03 | 0,09 | 0,46 |
| 10% | 0,05 | 0,02 | 0,20 |
| 20% | 0,05 | 0,05 | 0,06 |
| 50% | 0,01 | 0,04 | 0,00 |

Em 200 pontos por eleição o resultado final ficou sempre dentro da faixa e o vencedor nunca foi apontado errado.
Faixa = √((2·sd)² + (0,10·√(1−f))² + (0,9·e^(−pct/8))²); nunca indica vencedor antes de 1%.

## Rodar

```bash
python3 replay.py                       # erro em vários pontos
python3 replay.py --gera out/replay2022 # arquivos do site (copiar p/ GR Data/apuracao-sp/projecao/)
python3 coletor.py                      # ao vivo, serve :8787
ENSAIO=1 UFS=ac,rr python3 coletor.py   # ensaio com o 1º turno
```

Variáveis: `PLEITO`, `SAIDA`, `PORT`, `INTERVALO` (30), `THREADS`, `LOTE` (publica a cada N seções),
`REQ_POR_SEG` (limitador global; o TSE devolve 429 acima do limite), `UFS`, `VERIFICAR` (1 = confere assinatura),
`PROCESSOS`, `RELAY`, `ENVIA_PARA`, `RELAY_TOKEN` (coletor) / `RELAY_TOKEN_SHA256` (relay: só o hash).

## Hospedagem

O TSE devolve 429 para IP de datacenter, então a coleta roda no Mac (`noite.sh`) e o Railway (projeto `griso-site`,
serviço `grdata-apuracao`, volume `/data`, `RELAY=1`) só serve o que recebe:
https://grdata-apuracao-production.up.railway.app/snapshot.json e `/governador/<uf>/snapshot.json`.
Token em `~/.config/grdata/relay.env`; no Railway fica só o SHA-256 dele. A página lê daí (`?fonte=` sobrescreve).
Carga testada no Mac: 35 mil seções em 16 min a 90 req/s sem 429; com a conferência de assinatura são 3 requisições
por seção (~36 seções/s a 120 req/s).
