# Planejador - Vikunja para Associacao de Adquirentes

Gestor de projetos self-hosted para acompanhar a constituicao da Associacao
de Adquirentes do Empreendimento Mondrian BFabbriani (Itapema/SC).

## Stack

- **Vikunja** (vikunja/vikunja:latest) — gestor de projetos open-source
- **PostgreSQL 16** — banco de dados
- **Railway** — hosting

## Deploy no Railway

### Passo 1 — Criar o banco de dados

1. Abrir [railway.app](https://railway.app) e criar novo projeto
2. Clicar **+ New** → **Database** → **PostgreSQL**
3. Anotar as variaveis de conexao (host, user, password, database)

### Passo 2 — Criar o servico Vikunja

1. No mesmo projeto, clicar **+ New** → **Docker Image**
2. Digitar: `vikunja/vikunja:latest`
3. Em **Settings** → **Networking**, gerar dominio publico (porta **3456**)
4. Em **Variables**, adicionar:

```
VIKUNJA_DATABASE_TYPE=postgres
VIKUNJA_DATABASE_HOST=${{Postgres.PGHOST}}
VIKUNJA_DATABASE_DATABASE=${{Postgres.PGDATABASE}}
VIKUNJA_DATABASE_USER=${{Postgres.PGUSER}}
VIKUNJA_DATABASE_PASSWORD=${{Postgres.PGPASSWORD}}
VIKUNJA_DATABASE_SSLMODE=require
VIKUNJA_SERVICE_PUBLICURL=https://SEU-DOMINIO.up.railway.app
VIKUNJA_SERVICE_TIMEZONE=America/Sao_Paulo
VIKUNJA_SERVICE_ENABLEREGISTRATION=true
VIKUNJA_SERVICE_ENABLELINKSHARING=true
PORT=3456
```

5. Deploy automatico. Aguardar ~1-2 min.

### Passo 3 — Criar conta admin

1. Aceder ao dominio publico gerado pelo Railway
2. Registar primeiro utilizador (sera o admin)
3. Desativar registro aberto se quiser (mudar variavel para false)

### Passo 4 — Importar tarefas do Excel

```bash
pip install openpyxl requests

py scripts/import_vikunja.py \
  --url https://SEU-DOMINIO.up.railway.app \
  --user SEU_USER \
  --password SUA_SENHA
```

Isto cria automaticamente:
- 1 projeto principal + 6 sub-projetos
- 143 tarefas com prioridade, status e labels
- Labels por responsavel (Caina, Jair, Advogado, etc.)

### Teste local (opcional)

```bash
docker-compose up -d
# Aceder em http://localhost:3456
```

## Estrutura do projeto no Vikunja

```
Associacao Adquirentes — Mondrian BFabbriani
  ├── Tarefas Operacionais       (24 tarefas — C-01..C-09, J-01..J-05, A-01..A-05, etc.)
  ├── Cronograma Geral           (15 atividades sequenciais em 4 semanas)
  ├── Checklist Cartorio         (51 itens de conformidade documental)
  ├── Processo CNPJ-REDESIM      (33 passos para abertura do CNPJ)
  ├── Pendencias e Bloqueios     (10 itens bloqueantes)
  └── Riscos e Controles         (10 riscos com mitigacao)
```

## Controlo de acesso

- **Jair / Caina**: contas com acesso de escrita
- **Adquirentes**: acesso read-only via link partilhado
- **Advogado/Contador**: contas com acesso limitado a projetos relevantes

## Ficheiros

- `docker-compose.yml` — deploy local com Docker
- `scripts/import_vikunja.py` — importador de tarefas do Excel
- `Manual_Operacional_Associacao_v1.xlsx` — planilha fonte
