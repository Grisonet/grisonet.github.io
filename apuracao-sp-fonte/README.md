# Apuração SP 2026 — Fonte do projeto

Painel ao vivo, mapas, estudo de Guaratinguetá e análise "Dinheiro × Votos" das
Eleições 2026 em São Paulo. O site publicado está em **`../apuracao-sp/`**
(GitHub Pages: https://grisonet.github.io/apuracao-sp/). Esta pasta guarda a
**fonte** (poller de WhatsApp, scripts de dados e o fonte do index), que antes
vivia só no Mac/scratchpad temporário.

---

## Páginas publicadas (em `apuracao-sp/`)
- **`index.html`** — painel principal ao vivo. Lê o feed público do TSE direto do
  navegador (CORS liberado). Presidente e Governador com **mapa ao lado da lista**;
  Senado (2 vagas); Deputados (fed/est) com **todos os candidatos**, destaques por
  visitante (★, localStorage), **filtro por partido/federação**, **selo de ELEITO**
  (oficial TSE `e='s'`, ou projeção matemática nos majoritários), **projeção de
  cadeiras por partido** e **como cada eleito pegou a vaga** (votação própria /
  quociente / média). Gerado de `web-src/sp2026.html` por `build_index.py`.
- **`mapa.html`** — mapa do estado **Cabo Samuel × Dani Dias** por cidade
  (azul/rosa, pin com foto) + **estudo completo de Guaratinguetá** (panorama,
  confronto, resultado por cargo — nível município).
- **`dinheiro.html`** — **Dinheiro × Votos**: cruza resultado × prestação de contas
  do TSE (gasto, origem do recurso, impulsionamento na Meta) + **seguidores no
  Instagram** + seção de **Destaques**.

### Dados servidos junto (em `apuracao-sp/`)
- `estado.json`, `gov-sp.json`, `presidente.json` — agregados dos mapas (gerados
  pelo poller a cada 3 min; ⚠️ congelam se o poller parar).
- `financeiro-sp.json` — base da página Dinheiro × Votos (gerado por
  `dados-coleta/proc_financeiro.py`, estático).
- `sp-mun.geojson` (645 municípios SP), `br-uf.geojson` (27 UFs), `fotos/`.

---

## Poller de WhatsApp (`poller/poller.py`)
Lê o TSE e manda alertas no WhatsApp (via Evolution API do GRChat) **por cargo,
em tempo real**, e um **comparativo Cabo Samuel × Dani Dias** (Guaratinguetá +
17 cidades do Vale Histórico). Também roda a thread que gera `estado/gov/
presidente.json` e dá `git push` a cada 3 min.

- Config no `.env` (ver `.env.example`) — **NÃO versionar o `.env` real**
  (contém a chave da Evolution). Instância remetente, destinos e intervalos ali.
- Rodar: `cd ~/eleicao2026 && caffeinate -i python3 -u poller.py >> poller.log 2>&1 & disown`
- Parar: `pkill -f poller.py`
- Destinos: cargos → 5511993990357; comparativo → +5511993990357 e +5512981855887.

### Endpoints do TSE (feed público, sem auth, CORS reflete qualquer origem)
- Base: `https://resultados.tse.jus.br/oficial/ele2026/`
- Padrão: `/{pleito}/dados/{uf}/{uf}-c{cargo}-e00{pleito}-u.json`
- Pleitos: 6257 Presidente (1ºT), 6259 estadual (Gov/Sen/DepFed/DepEst).
  ⚠️ Dep. Federal fica sob o pleito **estadual** (6259).
- Cargos: 0001 Presidente · 0003 Governador · 0005 Senador · 0006 Dep. Federal · 0007 Dep. Estadual
- Município: `/6259/dados/sp/sp{cd}-c{cargo}-e006259-u.json` (cd TSE no nome).
- Campos: `s.pst` % apurado; por candidato `vap`, `pvap`, `e`(=s eleito), `sqcand`;
  `carg.qe` quociente; `agr.vag` cadeiras do partido/federação (tp=f federação).

---

## Dados financeiros e de seguidores (`dados-coleta/`)
- **`proc_financeiro.py`** — baixa a prestação de contas 2026 (dados abertos),
  cruza com os resultados e gera `financeiro-sp.json`. Fonte:
  `https://cdn.tse.jus.br/estatistica/sead/odsele/prestacao_contas/prestacao_de_contas_eleitorais_candidatos_2026.zip`
  (CSVs por UF; usar `despesas_contratadas_*_SP.csv` e `receitas_*_SP.csv`,
  encoding latin-1, sep `;`). **CSVs não versionados** (166 MB) — baixar ao rodar.
  - Impulsionamento Meta = despesas categoria "Impulsionamento de Conteúdos"
    com fornecedor Facebook/DLocal/EBANX.
  - Origem do recurso: `DS_FONTE_RECEITA` (FUNDO ESPECIAL=FEFC, FUNDO PARTIDARIO,
    OUTROS RECURSOS→próprio/pessoa física/coletivo). "Dinheiro público" = FEFC + Fundo Partidário.
  - Join por `SQ_CANDIDATO` (= `sqcand` dos resultados).
- **`proc_perfil.py`** — acrescenta ao `financeiro-sp.json` o **perfil** de cada candidato (sexo, idade, cor/raça,
  escolaridade, estado civil, ocupação, naturalidade, patrimônio, identidade de gênero, orientação sexual,
  experiência eleitoral). Fontes e uso no cabeçalho do script; alimenta a seção "Quem ganha — cruzamentos de perfil × dinheiro × voto"
  do `dinheiro.html` (14 cruzamentos, cada um com frase de insight calculada dos dados em `DIMS`/`drawCruz`;
  os insights de cada seção e os "Principais achados" saem de `drawInsights`). Sem painel de filtros — o
  usuário quer cruzamento com leitura pronta, não filtro.
  ⚠️ Rodar DEPOIS do `proc_financeiro.py` (que regrava o JSON) e recolocar `seg`.
- **`eleitos_handles.tsv`** / **`neleitos_handles.tsv`** — sq, nome, cargo, votos, @instagram
  (links de rede social do TSE: `rede_social_candidato_2026.zip`; o TSE guarda só o LINK,
  não o nº de seguidores).
- **`seguidores_eleitos.tsv`** — seguidores IG dos 164 eleitos (116 via WebSearch em 05/10 + 48 lidos do perfil em 08/10).
- **`seguidores_lote_2026-10-08.tsv`** — lote de 08/10: 48 eleitos + 28 não-eleitos (27 dep. federal), com handle
  oficial conferido, confiança, fonte e obs. Lido via WebFetch de `instagram.com/<handle>/` (funciona sem login;
  `curl` na API não). Handles errados do TSE foram corrigidos nos `*_handles.tsv`. Faltou só Jorge do Carmo (PT, DE).
- **`top50_naoeleitos_depest_sp_FINAL.{csv,json}`** — seguidores de 49 não-eleitos
  (dep. estadual mais votados), coletados em outra sessão.

---

## Achados da tese "voto segue o dinheiro / a fama?"
Correlação log-log com votos (dep SP): **gasto total r=0,73**, **fundo eleitoral
r=0,71**, **impulsionamento Meta r=0,65**, **seguidores r=0,45** (240 candidatos). Ou seja,
**dinheiro explica o voto melhor que fama**. Impulsionamento Meta total ≈ R$ 78,8 mi;
16 dos 28 que puseram ≥R$500k na Meta **não** se elegeram; casos como Felipe Franco
(3,9 mi seguidores → 59k votos) e Marco Feliciano (4 mi → 122k) reforçam.

---

## Pendências
1. ~~Seguidores dos eleitos que faltavam~~ — feito em 08/10 (164/164).
2. Seguidores de não-eleitos: 76 coletados (49 DE + 27 DF); ampliar a amostra se quiser mais base.
3. Prestação de contas é **parcial** (versão 04/10); prazo legal final **03/11/2026** — valores mudam.
4. Mapas congelam se o poller parar (dependem do push dos JSONs).
