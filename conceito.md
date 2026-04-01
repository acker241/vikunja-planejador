# Planejador - Leantime para Associacao de Adquirentes

Gestor de projetos self-hosted para acompanhar a constituicao da Associacao
de Adquirentes do Empreendimento Mondrian BFabbriani (Itapema/SC).

## Stack

- **Leantime** (leantime/leantime:latest) — gestor de projetos open-source (Kanban + Gantt + Timeline)
- **MySQL** — banco de dados (Leantime nao suporta PostgreSQL)
- **Railway** — hosting

## Deploy no Railway

### Passo 1 — Criar o banco de dados MySQL

1. Abrir [railway.app](https://railway.app) e criar novo projeto
2. Clicar **+ New** → **Database** → **MySQL**
3. Anotar as variaveis de conexao

### Passo 2 — Criar o servico Leantime

1. No mesmo projeto, clicar **+ New** → **GitHub Repo** → `acker241/vikunja-planejador`
2. Railway detecta o Dockerfile e faz build
3. Em **Settings** → **Networking**, gerar dominio publico (porta **8080**)
4. Em **Variables**, adicionar:

```
LEAN_DB_HOST=${{MySQL.MYSQLHOST}}
LEAN_DB_USER=${{MySQL.MYSQLUSER}}
LEAN_DB_PASSWORD=${{MySQL.MYSQLPASSWORD}}
LEAN_DB_DATABASE=${{MySQL.MYSQLDATABASE}}
LEAN_DB_PORT=${{MySQL.MYSQLPORT}}
LEAN_SESSION_PASSWORD=uma_senha_longa_aleatoria_aqui
LEAN_APP_URL=https://SEU-DOMINIO.up.railway.app
LEAN_SITENAME=Associacao Mondrian
PORT=8080
```

5. Deploy automatico. Aguardar ~2-3 min.

### Passo 3 — Setup inicial

1. Aceder ao dominio — Leantime mostra pagina de instalacao
2. Criar conta admin
3. Ir a **Company Settings > API** e criar uma API key

### Passo 4 — Importar tarefas do Excel

```bash
pip install openpyxl requests

py scripts/import_leantime.py \
  --url https://SEU-DOMINIO.up.railway.app \
  --api-key SUA_API_KEY
```

## Estrutura dos projetos no Leantime

```
Tarefas Operacionais       (24 tarefas — C-01..C-09, J-01..J-05, etc.)
Cronograma Geral           (15 milestones sequenciais em 4 semanas)
Checklist Cartorio         (51 itens de conformidade documental)
Processo CNPJ-REDESIM      (33 passos para abertura do CNPJ)
Pendencias e Bloqueios     (10 itens bloqueantes)
Riscos e Controles         (10 riscos com mitigacao)
```

## Ficheiros

- `Dockerfile` — build para Railway (Leantime)
- `docker-compose.yml` — deploy local com Docker
- `scripts/import_leantime.py` — importador de tarefas para Leantime
- `scripts/import_vikunja.py` — importador de tarefas para Vikunja (alternativa)
- `Manual_Operacional_Associacao_v1.xlsx` — planilha fonte (nao versionada — dados pessoais)
