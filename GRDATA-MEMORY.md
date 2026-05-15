# GR Data — Memória do Projeto

> Sistema de inteligência eleitoral brasileira. Versão **v25.4** — Maio 2026.

**URL pública:** https://grisonet.github.io

> Para referência de deploy/manutenção operacional, ver `README.md` (mesmo diretório).

---

## VISÃO ATUAL (v25.4)

### Infraestrutura

- **Supabase Project:** `lrtacwxvsrqbcmgbvyrl` (org "Griso News", plano Pro, região sa-east-1)
- **URL Supabase:** `https://lrtacwxvsrqbcmgbvyrl.supabase.co`
- **GitHub Pages:** `Grisonet/grisonet.github.io` (deploy via SSH)
- **BigQuery:** projeto `grdata-491620`, service account `grdata-bigquery@grdata-491620.iam.gserviceaccount.com`
- **Dataset principal:** `basedosdados.br_tse_eleicoes`

⚠️ **Não há tabelas próprias no Postgres do BigQuery — todas as queries vão direto pro `basedosdados`.** No Postgres do Supabase só existe a tabela `user_saved_items` (auth-protected).

### Páginas (8 + 2)

1. **Dashboard** — KPIs por município/UF/cargo com delta vs eleição anterior
2. **Mapa Estadual** — feature core: 1 candidato × N municípios do estado, mapa Leaflet + ranking
3. **Meu Mapa** — mapas salvos pelo usuário no servidor (requer auth)
4. **Planejamento** — meta de votos + priorização automática de municípios-alvo (consolidar + expandir)
5. **Emendas** — ⏸️ pausada aguardando chave Portal Transparência
6. **Resultados** — estilo UOL: top 2 + mapa Leaflet + drill-down por zona/local/seção
7. **Consulta** — cascade eleição→UF→município→cargo→candidato, depois detail com 5 abas (bens, dados pessoais, evolução, receitas, despesas)
8. **Comparativo** — até 3 candidatos lado a lado, persistência localStorage
9. **Estatísticas** — gráfico por partido
10. **API** — documentação

### Auth

- Supabase Auth (email/senha)
- `mailer_autoconfirm: true` (signup imediato)
- `disable_signup: false`
- `site_url: https://grisonet.github.io`
- Tabela `user_saved_items` com RLS — user só vê próprios items
- Persistência local: `cmp` (comparativo) e `grdata.planos` em localStorage (mapas vão pro servidor)

---

## FONTES DE DADOS

### 1. Edge Functions Supabase (todas com `verify_jwt: false`)

| Endpoint | Tabelas BQ |
|---|---|
| `tse-proxy` | proxy DivulgaCandContas |
| `tse-resultados` | proxy Resultados TSE |
| `tse-dashboard` | `detalhes_votacao_municipio_zona`, `resultados_candidato_municipio_zona`, `candidatos` |
| `tse-bigquery` | `resultados_candidato_secao`, `perfil_eleitorado_local_votacao` |
| `tse-votos-secao` | mesmas + `detalhes_votacao_secao` |
| `tse-financeiro` | `bens_candidato`, `receitas_candidato`, `despesas_candidato` |
| `tse-mapa-estadual` | `resultados_candidato_municipio_zona`, `candidatos`, `perfil_eleitorado_local_votacao`, `br_bd_diretorios_brasil.municipio` |
| `tse-planejamento` | `detalhes_votacao_municipio_zona`, `resultados_candidato_municipio_zona`, `perfil_eleitorado_local_votacao`, `br_bd_diretorios_brasil.municipio` |
| `tse-emendas` | proxy Portal Transparência (Emendas) |

### 2. APIs externas (via proxy)

- **DivulgaCandContas TSE:** `https://divulgacandcontas.tse.jus.br/divulga/rest/v1`
- **Resultados TSE:** `https://resultados.tse.jus.br/oficial` (URLs 2024 retornaram 404 ao longo do projeto — TSE arquivou)
- **Portal Transparência:** `https://api.portaldatransparencia.gov.br/api-de-dados/emendas` (requer chave)

### 3. BigQuery: 23 tabelas em `basedosdados.br_tse_eleicoes`

**Em uso ativo:**
- `resultados_candidato_secao` (505M rows, 71GB) — votos por candidato/seção
- `resultados_candidato_municipio_zona` (40M rows, 6GB) — pré-agregado por município/zona
- `detalhes_votacao_secao` (24M rows, 4.7GB) — aptos/comparecimento/abstenção
- `detalhes_votacao_municipio_zona` (376k rows) — pré-agregado
- `perfil_eleitorado_local_votacao` (6M rows) — NOME, ENDEREÇO, lat/lng dos locais
- `candidatos` (3.3M rows) — info de candidato (nome, partido, ocupação, idade, instrução)
- `bens_candidato` (5M rows, 0.7GB)
- `receitas_candidato` (15M rows, 5.5GB)
- `despesas_candidato` (32M rows, 14GB)
- `br_bd_diretorios_brasil.municipio` — id_municipio_tse ↔ id_municipio (IBGE) ↔ nome

**Disponíveis mas não usadas ainda:**
- `local_secao` — geo-only, sem nomes (foi substituída por perfil_eleitorado_local_votacao)
- `perfil_eleitorado_municipio_zona` (40M rows) — perfil demográfico por zona
- `perfil_eleitorado_secao` (588M rows, 39GB) — perfil demográfico por seção (granularidade máxima)
- `resultados_partido_*` — votos de legenda
- `vagas`, `partidos`, `dicionario`

---

## QUIRKS / DECISÕES NÃO-ÓBVIAS

### Cargo: nome textual, não código

Frontend manda `cargo=6` (TSE code). Backend traduz pra `'deputado federal'` via `cargoCodeToName(code)` em `_shared/bq.ts`. Map:
- 1 → presidente
- 3 → governador
- 5 → senador
- 6 → deputado federal (com espaço)
- 7 → deputado estadual
- 11 → prefeito
- 13 → vereador

### Scope para candidatos (frontend → URL)

- **Presidente (cargo=1):** `scope=BR` (nacional)
- **Outros federais:** `scope=UF` (sigla)
- **Municipais (prefeito/vereador):** `scope=munCod` (TSE, sem zeros)

### URLs corretas DivulgaCandContas

Pattern correto (extraído do bundle v22 que funcionava):
- **Cargos:** `/eleicao/listar/municipios/{eleId}/{munOuUf}/cargos`
- **Candidatos:** `/candidatura/listar/{ano}/{munOuUf}/{eleId}/{cargo}/candidatos`
- **Detail:** `/candidatura/buscar/{ano}/{munOuUf}/{eleId}/candidato/{candId}`

Patterns incorretos comuns: `/eleicao/buscar/...` (retorna 404).

### Municípios: `mun=SP` para federal (bug histórico)

Frontend v22 passa `mun=SP` pra federal mesmo quando deveria estar vazio. Backend `tse-*` detecta com regex `/^\d+$/.test(mun)` e ignora se não-numérico.

### Coordenadas

Usar `perfil_eleitorado_local_votacao.latitude` e `.longitude` (FLOAT64 direto, sem ST_X/ST_Y). Cobertura:
- 2024: ~95% nacional
- 2014-2022: ~79% nacional
- Outliers persistentes sem coords: Salvador (~50%), BH 2014-2022 (~0%)

### Discrepância `*_secao` vs `*_municipio_zona`

Para Cabo Samuel SP 2022 Dep Federal:
- Soma de `resultados_candidato_secao` filtrado por turno=1 e r.votos>0: 2.008 votos
- `resultados_candidato_municipio_zona`: 7.262 votos (bate com TSE oficial)

Ainda não sei se a `_secao` está incompleta ou se há filtro silencioso. Usar `_municipio_zona` para totais "oficiais".

### Coerção de tipos em SELECT React

`cargos.find(c => c.codigo === e.target.value)` falha porque `c.codigo` é NUMBER e `e.target.value` é STRING. Sempre `String(c.codigo) === e.target.value`. Mesmo issue com `selCargo.codigo.replace(...)` (NUMBER não tem `.replace`).

---

## EVOLUÇÃO HISTÓRICA

### v22 (Março 2026) — versão original

- Sistema em produção no Supabase `tdssncfrteftokgrpclq`
- Projeto Supabase original DELETADO (NXDOMAIN) → recuperação iniciada em Maio 2026
- Bundle v22 minificado preservado, com ResultadosPage completo

### v23 (Maio 2026) — recuperação

- Novo projeto Supabase `lrtacwxvsrqbcmgbvyrl` criado em org "Griso News" (Pro)
- 5 edge functions reescritas do zero (tse-proxy/resultados/bigquery/votos-secao/dashboard)
- 1 nova edge function: tse-financeiro (bens + receitas + despesas)
- Bundle v22 patcheado com sed pra apontar pro novo projeto (mantém ResultadosPage)
- Source App.jsx recuperado mas com placeholders (ResultadosPage e Consulta detail eram placeholder)

### v23.4-23.7 — reconstrução

- ResultadosPage extraído do v22 bundle (~1170 linhas minificadas) → JSX
- Consulta detail reconstruído do zero (foto, header, 3 abas)
- Hash routing
- Fix URLs TSE (cascade de cargos quebrada)
- Fix scope presidente=BR

### v24 (Maio 2026) — Datapedia parity

- Tarefa #1: troca `local_secao` → `perfil_eleitorado_local_votacao` (resolve "lat=null" + nomes/endereços)
- Tarefa #2: troca `*_secao` → `*_municipio_zona` no dashboard (70× mais rápido pra federal estadual)
- Tarefa #3: dict `candidates` no API response
- Tarefa #4: endpoint tse-financeiro + 2 abas no Consulta detail (Receitas/Despesas)
- Fase 5: Mapa Estadual (replica feature core do Datapedia)
- Fase 6: Comparativo até 3 candidatos
- Fase 7: Planejamento (meta + auto-priorização)

### v25 (Maio 2026) — Auth + features+

- Fase 8: tabela `user_saved_items` + RLS + Supabase Auth + Meu Mapa
- Fase 9: Emendas (UI pronta, aguardando chave Portal Transparência)
- Round 1: mobile responsive (sidebar overlay, grids stack)

---

## BUGS HISTÓRICOS RESOLVIDOS

- "ResultadosPage cargo=0011 vs 11" — cargo zero-padded enviado pra BQ, BQ usa sem zeros
- "Mapa SP só 13 zonas" — paginação BQ trunca em ~1MB; adicionada paginação
- "Cabo Samuel não aparece no dropdown" — limit de 300 no `<select>`, rank #303 ficava fora. Convertido pra autocomplete clicável
- "ss is not defined" — `const ss=...` estava local em App, usado por componentes top-level. Movido pra module-level
- "Cargo strict ===" — TSE retorna number, e.target.value é string. Coerce com `String()`
- "Tela branca v25.0" — supabase-js + sidebar mobile não tinha causa única; era o ss undefined acima

---

## CHECKLIST PARA NOVA SESSÃO (após pausa)

1. Confirmar SSH GitHub: `ssh -T git@github.com` deve dizer "Hi Grisonet"
2. Verificar Supabase access token vigente: `npx supabase projects list` deve listar `gr-data` em Griso News
3. Confirmar tabela BQ acessível: hit `tse-dashboard?uf=SP&cargo=11&ano=2024&turno=1` retorna `current.aptos > 0`
4. Conferir `mailer_autoconfirm: true` ainda ativo (signup imediato)
5. localStorage do navegador pode estar populado com `grdata.cmp` e `grdata.planos` se a pessoa testou antes

---

## TODO / BACKLOG

### Bloqueados por credencial
- Fase 9 — Emendas (chave Portal Transparência)
- Fase 10 — IA contextualizada (chave Anthropic ou OpenAI)

### Possíveis melhorias (sem bloqueio)
- Round 3 — Evolução histórica do candidato (via BQ resultados_candidato)
- Round 4 — Mapa dual abstenção × margem
- Round 5 — Transferência 1º→2º turno
- Round 6 — Perfil socioeconômico do eleitorado
- Refresh password / esqueci minha senha (UI)
- Migrar comparativo e planos do localStorage pro servidor (tipo='compare' e 'plano' já suportados na tabela)
- Choropleth real no Mapa Estadual (polígonos coloridos, requer GeoJSON ~2MB)
- Foto do candidato (URL via TSE DivulgaCandContas)
- Cluster de pins no Leaflet (Leaflet.markercluster)
- Export PDF do Dashboard (jsPDF)
- Email confirmation no signup (mailer_autoconfirm:false + email template)
- 2FA / MFA (Supabase suporta TOTP)

### Sanity / observabilidade
- Adicionar logging estruturado nas edge functions (Supabase Logs)
- Métricas no dashboard de admin (quantos usuários, queries BQ por dia, etc.)
- Error tracking (Sentry ou similar — opcional)
