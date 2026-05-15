# GR Data — Sistema de Inteligência Eleitoral

> SPA React (single page app) hospedada em GitHub Pages, backend serverless Supabase Edge Functions sobre BigQuery (Base dos Dados).

URL pública: **https://grisonet.github.io**

---

## Arquitetura

```
┌──────────────────────────────────────────────────────────┐
│  Browser (Cliente)                                       │
│  React 18 + esbuild (bundle IIFE ~470KB)                 │
│  Leaflet.js (carregamento dinâmico)                      │
│  Hash routing: /#/<página>                               │
│  Auth client: @supabase/supabase-js                      │
└─────────────┬────────────────────────────────────────────┘
              │ HTTPS
              ▼
┌──────────────────────────────────────────────────────────┐
│  GitHub Pages — Grisonet/grisonet.github.io              │
│  Serve: index.html + app.js                              │
└──────────────────────────────────────────────────────────┘
              │ XHR/fetch
              ▼
┌──────────────────────────────────────────────────────────┐
│  Supabase project: lrtacwxvsrqbcmgbvyrl                  │
│  - Edge Functions (Deno): proxies + BQ queries           │
│  - Postgres: tabela user_saved_items (auth/RLS)          │
│  - Auth: email+senha (mailer_autoconfirm:true)           │
└─────────────┬────────────────────────────────────────────┘
              │
       ┌──────┴──────┐
       ▼             ▼
┌──────────────┐  ┌────────────────────────────┐
│ TSE APIs     │  │ BigQuery (basedosdados)    │
│ DivulgaCand  │  │ br_tse_eleicoes.*          │
│ Resultados   │  │ br_bd_diretorios_brasil.*  │
└──────────────┘  └────────────────────────────┘
```

---

## Páginas

| URL | Componente | O que faz |
|---|---|---|
| `/#/dashboard` | `DashboardPage` | KPIs por município/UF/ano/cargo. Margem, abstenção, comparecimento, votos válidos, ranking, top zonas |
| `/#/mapa-estadual` | `MapaEstadualPage` | Mapa Leaflet do estado com pins coloridos por votos de um candidato. Ranking lateral, botão "Salvar em Meu Mapa" |
| `/#/meu-mapa` | `MeuMapaPage` | Lista de mapas salvos pelo usuário logado (requer auth). Click carrega no Mapa Estadual |
| `/#/planejamento` | `PlanejamentoPage` | Meta de votos + priorização automática de municípios-alvo. Salva planos no localStorage |
| `/#/emendas` | `EmendasPage` | ⏸️ Pausada — aguardando chave Portal da Transparência |
| `/#/resultados` | `ResultadosPage` | Resultados oficiais estilo UOL: cards top 2 candidatos, mapa Leaflet, filtro de turno |
| `/#/consulta` | App inline | Cascade de candidatos com detalhe completo: bens, dados, evolução, receitas, despesas |
| `/#/comparativo` | `ComparativoPage` | Comparativo até 3 candidatos lado a lado. Persistência em localStorage |
| `/#/estatisticas` | App inline | Gráfico de candidatos por partido |
| `/#/api` | App inline | Documentação dos endpoints |

---

## Edge Functions deployadas (Supabase)

Todas em `https://lrtacwxvsrqbcmgbvyrl.supabase.co/functions/v1/<nome>`:

| Função | Descrição | Tabelas BQ usadas |
|---|---|---|
| `tse-proxy` | Proxy CORS p/ DivulgaCandContas TSE | — (proxy) |
| `tse-resultados` | Proxy CORS p/ Resultados TSE | — (proxy) |
| `tse-dashboard` | KPIs por município/zona vs eleição anterior | `detalhes_votacao_municipio_zona`, `resultados_candidato_municipio_zona`, `candidatos` |
| `tse-bigquery` | Hierarquia zona→local→seção (mapa drill-down) | `resultados_candidato_secao`, `perfil_eleitorado_local_votacao` |
| `tse-votos-secao` | Drill-down por seção com perfil | mesmas + `detalhes_votacao_secao` |
| `tse-financeiro` | Bens + receitas + despesas de campanha | `bens_candidato`, `receitas_candidato`, `despesas_candidato` |
| `tse-mapa-estadual` | Ranking candidatos + municípios com votos | `resultados_candidato_municipio_zona`, `candidatos`, `perfil_eleitorado_local_votacao`, `br_bd_diretorios_brasil.municipio` |
| `tse-planejamento` | Eleitorado por município + votos do candidato | `detalhes_votacao_municipio_zona`, `resultados_candidato_municipio_zona` |
| `tse-emendas` | Proxy Portal Transparência (Emendas) | — (proxy externo) |

Todas com `verify_jwt: false` (chave anon não exigida).

---

## Database

### Tabela `user_saved_items` (Postgres Supabase)

| Coluna | Tipo | Notas |
|---|---|---|
| `id` | uuid (PK) | gen_random_uuid() |
| `user_id` | uuid (FK auth.users) | ON DELETE CASCADE |
| `tipo` | text | 'mapa', 'plano', 'compare' |
| `nome` | text | nome user-friendly |
| `config` | jsonb | snapshot do estado da página |
| `created_at`, `updated_at` | timestamptz | trigger atualiza updated_at |

**RLS:** habilitada. Políticas SELECT/INSERT/UPDATE/DELETE checam `auth.uid() = user_id`. User só vê os próprios items.

---

## Segredos / Credenciais

Cada um tem **lugar de guarda** e **procedimento de rotação**:

| Segredo | Onde está | Como rotacionar |
|---|---|---|
| **Supabase anon key** | `SUPABASE_ANON` hardcoded em `App.jsx` linha 9 | Dashboard Supabase → Settings → API → Reset legacy anon key. Atualizar source + rebuild |
| **GCP Service Account** (BigQuery) | Supabase secret `GCP_SA_PRIVATE_KEY` + `GCP_SA_EMAIL` + `GCP_PROJECT_ID` | Google Cloud Console → IAM → grdata-bigquery@grdata-491620 → Keys → Add new + delete old. Atualizar secret via `supabase secrets set` |
| **Portal Transparência** | Supabase secret `PORTAL_TRANSPARENCIA_KEY` (pendente) | Cadastrar email em portaldatransparencia.gov.br/api-de-dados/cadastrar-email. Chave por email. Sem expiração mas pode revogar manualmente |
| **GitHub deploy** | SSH key local em `~/.ssh/id_ed25519` (autenticada como Grisonet) | Adicionar nova SSH key em github.com/settings/keys e remover antiga |
| **Supabase access token** (CLI) | Localmente em comandos `SUPABASE_ACCESS_TOKEN=...` | Dashboard → Account → Access Tokens → Revoke + create new |

⚠️ **NÃO commit nenhum segredo no git.** O `GRDATA-MEMORY.md` original tinha tokens em texto plano — foi limpo.

---

## Build & Deploy

### Frontend (esbuild → GitHub Pages)

```bash
cd /Users/griso/Downloads/grdata-project/frontend
npm install
npm run build   # gera dist/app.js (~470KB)
# Copia pro repo do GH Pages:
cp dist/app.js "/Users/griso/GR Data/app.js"
cd "/Users/griso/GR Data"
git add app.js && git commit -m "deploy" && git push
# GH Pages atualiza em ~1-3 min (CDN cache)
```

### Edge Functions (Supabase CLI)

Pré-requisitos: `SUPABASE_ACCESS_TOKEN` no env (gerar em supabase.com/dashboard/account/tokens).

```bash
export SUPABASE_ACCESS_TOKEN="sbp_..."
cd /Users/griso/Downloads/grdata-project
# Deploy uma função:
npx supabase@latest functions deploy <nome-funcao> \
  --project-ref lrtacwxvsrqbcmgbvyrl --no-verify-jwt
# Set secret:
npx supabase@latest secrets set --project-ref lrtacwxvsrqbcmgbvyrl --env-file <arquivo>
```

### Migrations Postgres

Via Management API (sem CLI separado):

```bash
curl -X POST "https://api.supabase.com/v1/projects/lrtacwxvsrqbcmgbvyrl/database/query" \
  -H "Authorization: Bearer $SUPABASE_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  --data-binary @<(jq -Rs '{query: .}' migration.sql)
```

---

## Stack

- **Frontend:** React 18, esbuild, Supabase JS, Leaflet (CDN), hash routing
- **Backend:** Deno (Supabase Edge), BigQuery REST API com JWT auth (RS256), Postgres com RLS
- **CI/CD:** manual via `git push` (GitHub Pages) + `supabase functions deploy`
- **Hospedagem:** GitHub Pages (frontend, gratuito) + Supabase free tier ou Pro
- **Custo recorrente:** $0 (free tier Supabase) ou $25/mês (Pro). BigQuery cobra por TB queried (basedosdados é hospedado por terceiro, queries pagas pela conta `grdata-491620`)

---

## Estrutura de pastas

```
/Users/griso/
├── GR Data/                          # repo do GH Pages
│   ├── app.js                        # bundle deployado
│   ├── index.html                    # com error overlay debug
│   ├── README.md                     # este arquivo
│   ├── GRDATA-MEMORY.md              # memória técnica do projeto
│   └── *.csv                         # exports/relatórios
└── Downloads/grdata-project/         # source code
    ├── frontend/
    │   ├── src/App.jsx               # tudo num arquivo (~2500 linhas)
    │   ├── src/index.jsx             # entrypoint React
    │   ├── package.json
    │   └── dist/app.js               # build output
    └── supabase/functions/
        ├── _shared/bq.ts             # auth BQ + helpers
        ├── tse-proxy/index.ts
        ├── tse-resultados/index.ts
        ├── tse-dashboard/index.ts
        ├── tse-bigquery/index.ts
        ├── tse-votos-secao/index.ts
        ├── tse-financeiro/index.ts
        ├── tse-mapa-estadual/index.ts
        ├── tse-planejamento/index.ts
        └── tse-emendas/index.ts
```

---

## Troubleshooting

**Página em branco após deploy:** o `index.html` tem um error overlay inline que captura JS errors e mostra em caixa vermelha no topo. Hard refresh (Cmd+Shift+R) e veja o erro.

**Tabelas BQ vazias / 0 rows:** confirmar nome do cargo. BigQuery usa nome textual em pt-BR (`'deputado federal'`, `'prefeito'`), não código TSE.

**Auth não funciona:** verificar `site_url` e `uri_allow_list` em `https://api.supabase.com/v1/projects/lrtacwxvsrqbcmgbvyrl/config/auth`.

**CORS error:** edge functions sempre incluem `Access-Control-Allow-Origin: *`. Se quebrar, conferir se a função está com `verify_jwt: false`.

**Build falha:** `npm install` precisa de Node 18+. `esbuild` é o único dep dev.
