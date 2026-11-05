# DataPulse

**DataPulse** e uma plataforma de analytics/BI para importar dados, explorar
indicadores e acompanhar tendencias em um workspace. Este repositorio foi
preparado como projeto de portfolio: roda localmente, usa SQLite, nao exige uma
conta em servico externo e nao cria dados de exemplo automaticamente.

> **Atencao:** o projeto e demonstrativo, nao um servico de BI pronto para dados
> confidenciais ou uso empresarial. Todas as contas do mesmo banco compartilham
> o workspace. Leia [Seguranca e limites](#seguranca-e-limites) antes de publicar.

## O que ele faz

- Importa CSV, JSON, XLSX e XLS, valida linhas, infere colunas e evita registros
  duplicados.
- Consulta analytics com filtros, agrupamentos, KPIs e comparacao de tendencias.
- Salva favoritos e relatorios, exporta snapshots em CSV e gera insights
  estatisticos e alertas.
- Processa importacoes e agendamentos em segundo plano por meio de um worker.
- Inclui login, papeis de acesso, auditoria, notificacoes e configuracoes de equipe.
- Apresenta uma interface responsiva em portugues, com tema claro/escuro,
  busca, graficos acessiveis e estados vazios/erro.

Os resultados sao calculados a partir dos dados importados. O projeto nao usa IA,
nao inventa previsoes e nao cria dados demonstrativos por conta propria.

## Tecnologias

| Camada | Tecnologias |
|---|---|
| Interface | Vue 3, Vite, Vue Router, Pinia, Axios e Tailwind CSS |
| API | Python 3.14, FastAPI, Pydantic e SQLAlchemy |
| Banco | SQLite, com esquema versionado pelo Alembic |
| Operacoes | Worker persistente; SMTP opcional |
| Testes | unittest, Node.js test runner e Playwright |
| Publicacao | Docker Compose e Caddy opcional |

## Comecar no Windows

### 1. Requisitos

- Python 3.14.
- Node.js 22.18 ou mais recente na linha 22, ou 24.12 ou mais recente.
- PowerShell.

### 2. Configurar e iniciar a API

Abra um PowerShell na raiz deste repositorio:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Edite `backend/.env` e preencha `SECRET_KEY` com uma chave aleatoria. Gere uma
chave com:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Copie o valor para `.env`; nao o publique nem o compartilhe. As demais variaveis
podem continuar com os valores de exemplo para desenvolvimento local.

Ainda na pasta `backend`, aplique o esquema e inicie a API:

```powershell
python -m alembic upgrade head
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

Em outro PowerShell, na pasta `backend` e com o mesmo ambiente virtual ativo,
inicie o worker:

```powershell
python -m worker
```

O worker e necessario para importacoes em segundo plano e agendamentos. Se ele
nao estiver ativo, essas tarefas aguardam na fila.

### 3. Iniciar a interface

Em outro PowerShell:

```powershell
cd frontend
npm.cmd ci
npm.cmd run dev -- --host 127.0.0.1
```

Abra <http://127.0.0.1:5173>. O proxy do Vite encaminha as requisicoes para a API
em `127.0.0.1:8000`. No primeiro acesso, crie a conta de administrador; depois,
o cadastro publico e encerrado.

### Enderecos locais

| Recurso | Endereco |
|---|---|
| Aplicacao | <http://127.0.0.1:5173> |
| API | <http://127.0.0.1:8000> |
| Swagger / OpenAPI | <http://127.0.0.1:8000/docs> |
| Health / readiness | <http://127.0.0.1:8000/health> e <http://127.0.0.1:8000/ready> |

## Executar com Docker

Docker Compose inicia SQLite em volume, migrations, API, worker e frontend servido
pelo Caddy. E uma alternativa de execucao em um unico host.

1. Se ainda nao existir, crie `backend/.env` a partir de `backend/.env.example`;
   preserve o arquivo atual e defina `SECRET_KEY`.
2. Na raiz do projeto, valide a configuracao e suba os servicos:

```powershell
$env:APP_ADDRESS = "localhost"
docker compose config --quiet
docker compose up --build
```

Com o valor local `localhost`, abra <https://localhost>. O Caddy cria um
certificado local para desenvolvimento, que pode nao ser confiavel pelo
navegador; isso e diferente de um certificado publico para dominio real.

Para um dominio publico, configure DNS, defina `APP_ADDRESS` com o dominio,
libere as portas 80 e 443 e configure uma origem CORS exata em `backend/.env`.
Consulte as instrucoes detalhadas no [guia de publicacao da API](backend/README.md).

O banco do Compose fica em um volume nomeado e e separado de qualquer banco local.
Este deployment usa SQLite; mantenha um unico host e nao escale as replicas do
worker/API como se fosse uma instalacao multi-host.

## Testes e verificacoes

Backend, a partir de `backend`:

```powershell
python -m unittest discover -s tests -v
python -m alembic upgrade head
python -m alembic check
```

Frontend, a partir de `frontend`:

```powershell
npm.cmd test
npx.cmd oxlint .
npx.cmd eslint .
npm.cmd run build
npm.cmd exec playwright -- install chromium
$env:DATAPULSE_PYTHON = (Get-Command python).Source
npm.cmd run test:e2e
```

Os testes do backend e o E2E usam bancos temporarios. O fluxo Playwright inicia
sua propria API, worker e interface em portas locais dedicadas. Nao use dados
reais nos testes.

O workflow [.github/workflows/ci.yml](.github/workflows/ci.yml) executa os testes,
validacoes, lint, build e o E2E em pushes e pull requests.

## Estrutura do repositorio

```text
backend/     API FastAPI, banco SQLite, migrations, worker e testes
frontend/    Aplicacao Vue, componentes, testes e configuracao Playwright
.github/     CI do projeto
compose.yaml Execucao local ou em um unico servidor com Docker
```

- [Documentacao da API e operacao](backend/README.md)
- [Documentacao da interface](frontend/README.md)
- [Composicao Docker](compose.yaml)
- [CI](.github/workflows/ci.yml)

## Publicar este projeto no GitHub

Antes de enviar os arquivos a um repositorio publico:

1. Confira que `.env` nao sera enviado. O `.gitignore` da raiz ignora segredos,
   bancos locais, backups, dependencias e artefatos gerados.
2. Nunca inclua dados pessoais, arquivos importados, tokens, senhas, chaves ou
   backups. Os `.env.example` contem apenas exemplos sem credenciais.
3. Use dados sinteticos, criados por voce, ao gravar uma demonstracao.
4. Revise as dependencias e os avisos de seguranca antes de publicar uma versao.
5. Escolha e adicione uma licenca antes de permitir que outras pessoas reutilizem
   o codigo. Este repositorio ainda nao define uma licenca.

Publicar o codigo no GitHub nao publica automaticamente a aplicacao. O GitHub
Pages, por ser hospedagem estatica, nao executa esta API FastAPI nem o worker;
para demonstrar o sistema online, publique tambem o backend e o SQLite em um
ambiente que suporte processos persistentes, ou apresente uma gravacao local.

Os arquivos de exemplo nao geram usuarios nem dados automaticamente. Inicie o
projeto com um banco vazio e faca manualmente o cadastro inicial do administrador.

## Seguranca e limites

- O sistema e de **workspace unico**: contas no mesmo banco compartilham fontes,
  datasets, analytics e relatorios. Nao e multiempresa.
- SQLite e adequado para esta demonstracao em uma unica maquina; o worker usa uma
  trava local. Nao use varias replicas/hosts para API ou worker.
- Login e cadastro inicial usam limitacao local por IP, nao distribuida.
- Nao ha recuperacao automatizada de senha, refresh token ou MFA.
- SMTP e integracoes HTTPS sao opcionais e exigem configuracao explicita.
- Nao coloque segredos em variaveis `VITE_*`: elas vao para o bundle publico.
- A autenticacao e controles do projeto nao substituem uma avaliacao de seguranca
  para uso publico, comercial ou com informacoes sensiveis.

Para detalhes de variaveis, migrations, API, backups e operacao, consulte o
[README do backend](backend/README.md).