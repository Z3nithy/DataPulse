# DataPulse

O **DataPulse** é um projeto de portfólio para importar dados, explorar indicadores e
acompanhar tendências. Ele roda localmente com uma API FastAPI, uma interface Vue,
um banco SQLite e um worker para tarefas em segundo plano.

> **Importante:** este projeto é demonstrativo. Todas as contas do mesmo banco
> compartilham um único workspace. Não use dados confidenciais nem considere o
> projeto pronto para uso empresarial sem uma avaliação de segurança.

## O que você pode fazer

- Importar arquivos CSV, JSON, XLSX e XLS e consultar o histórico de validação.
- Criar análises com filtros, agrupamentos, KPIs e tendências.
- Salvar consultas como favoritos e relatórios e exportar relatórios em CSV.
- Configurar alertas, agendamentos e processamento em segundo plano.
- Gerenciar usuários, permissões, notificações e auditoria.
- Explorar o workspace com o tour interativo e o guia de primeiros passos.
- Criar uma conta pública de demonstração com dados sintéticos e restaurar esses
  dados sem apagar os outros datasets do workspace.

Os resultados são calculados a partir dos dados importados ou de dados sintéticos.
O DataPulse não usa IA e não inventa previsões.

## Tecnologias

| Parte          | Tecnologias                                          |
| -------------- | ---------------------------------------------------- |
| Interface      | Vue 3, Vite, Vue Router, Pinia, Axios e Tailwind CSS |
| API            | Python 3.14, FastAPI, Pydantic e SQLAlchemy          |
| Banco de dados | SQLite, com esquema controlado pelo Alembic          |
| Tarefas        | Worker persistente; envio de email opcional via SMTP |
| Testes         | `unittest`, Node.js test runner e Playwright         |

## Início rápido no Windows

### Requisitos

- Python 3.14.
- Node.js 22.18 ou mais recente na linha 22, ou 24.12 ou mais recente.
- PowerShell.

Você iniciará três processos em **três janelas de PowerShell**: API, worker e
interface. Deixe as três janelas abertas enquanto usa o projeto.

### 1. Configure o backend

Na primeira janela, a partir da pasta raiz do repositório:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Abra `backend/.env` e preencha `SECRET_KEY`. Gere uma chave localmente:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Copie o valor gerado para `SECRET_KEY` em `backend/.env`. Não compartilhe nem
publique essa chave.

Ainda na pasta `backend`, prepare o banco e inicie a API:

```powershell
python -m alembic upgrade head
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

### 2. Inicie o worker

Na segunda janela, use a mesma pasta e o mesmo ambiente virtual:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m worker
```

O worker processa importações em segundo plano e agendamentos. Sem ele, a API
continua funcionando, mas as tarefas permanecem na fila.

### 3. Inicie a interface

Na terceira janela, a partir da raiz do repositório:

```powershell
cd frontend
npm.cmd ci
npm.cmd run dev -- --host 127.0.0.1
```

Abra <http://127.0.0.1:5173>. O Vite encaminha as chamadas da interface para a API
local.

### 4. Entre no workspace

Na primeira execução, escolha **Primeiro acesso? Configurar administrador** e
crie a conta de administrador. Esse cadastro inicial fecha depois que a primeira
conta é criada. Em seguida, use o tour opcional para conhecer as páginas.

O login usa **nome de usuário**; email é opcional. Para habilitar a conta pública
de demonstração, siga a seção de [conta pública e demonstração](backend/README.md#contas-permissoes-e-demonstracao).

## Endereços locais

| Serviço                       | Endereço                       |
| ----------------------------- | ------------------------------ |
| Aplicação web                 | <http://127.0.0.1:5173>        |
| API                           | <http://127.0.0.1:8000>        |
| Swagger / documentação da API | <http://127.0.0.1:8000/docs>   |
| Estado da API                 | <http://127.0.0.1:8000/health> |
| Estado da API e do banco      | <http://127.0.0.1:8000/ready>  |

## Problemas comuns

| Sintoma                             | O que verificar                                                                                                                               |
| ----------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| `Application startup failed`        | Confira `backend/.env`, confirme que `SECRET_KEY` tem pelo menos 32 caracteres e execute `python -m alembic upgrade head` na pasta `backend`. |
| A interface não carrega dados       | Confirme que a API está ativa em `127.0.0.1:8000` e consulte `/ready`.                                                                        |
| Worker offline ou tarefas paradas   | Mantenha uma segunda janela aberta com `python -m worker`, usando o mesmo banco e ambiente virtual da API.                                    |
| `npm.ps1` bloqueado pelo PowerShell | Use `npm.cmd`, como nos comandos deste README; não é necessário mudar a política de execução do Windows.                                      |
| Porta já está em uso                | Feche o processo local que está usando a porta `5173`, `8000`, `18770` ou `18771` e tente novamente.                                          |

Se o problema continuar, consulte os logs do terminal correspondente e as
instruções específicas do [backend](backend/README.md) ou da
[interface](frontend/README.md).

## Testes

Execute os comandos na pasta indicada.

**Backend** — na pasta `backend`:

```powershell
python -m unittest discover -s tests -v
python -m alembic upgrade head
python -m alembic check
```

**Interface** — na pasta `frontend`:

```powershell
npm.cmd ci
npm.cmd test
npx.cmd oxlint .
npx.cmd eslint .
npm.cmd run build
```

**Testes no navegador (E2E)** — instale o Chromium uma vez e configure o Python
que tem as dependências do backend:

```powershell
npm.cmd exec playwright -- install chromium
$env:DATAPULSE_PYTHON = (Get-Command python).Source
npm.cmd run test:e2e
```

Os testes usam bancos temporários. O E2E inicia uma API, um worker e um Vite em
portas próprias (`18770` e `18771`); deixe essas portas livres. Não use dados
reais nos testes.

O GitHub Actions executa testes, verificações de migrations, lint, build e E2E
em pushes e pull requests: [workflow de CI](.github/workflows/ci.yml).

## Documentação por área

- [Backend: configuração, API, worker, backups e migrations](backend/README.md)
- [Frontend: navegação, testes e build](frontend/README.md)
- [Workflow de integração contínua](.github/workflows/ci.yml)

## Publicar o código ou hospedar a aplicação?

Enviar o código ao GitHub **não publica a aplicação para acesso online**. O
GitHub Pages hospeda arquivos estáticos e não executa esta API FastAPI nem o
worker. Para uma demonstração online, seria necessário hospedar a interface e o
backend em serviços que suportem a API, o banco e processos persistentes. Este
repositório não configura essa hospedagem.

Antes de enviar alterações ao GitHub:

1. Verifique que arquivos `.env`, bancos, backups e dados importados não estão
   no commit.
2. Nunca inclua chaves, senhas privadas ou tokens no código. Configure esses
   valores no ambiente local ou no gerenciador de segredos da hospedagem.
3. Use apenas dados sintéticos em capturas de tela e demonstrações.
4. Revise avisos de dependências e segurança.
5. Escolha uma licença antes de permitir que outras pessoas reutilizem o código.

## Limites e segurança

- Um único workspace compartilhado por todas as contas do mesmo banco; não há
  isolamento multiempresa.
- SQLite e a trava local do worker são destinados a uma única máquina/volume,
  não a múltiplas réplicas em hosts distintos.
- O limite de tentativas de login é local ao processo.
- Não há recuperação de senha por email, refresh token ou MFA.
- SMTP e integrações HTTPS são opcionais e exigem configuração explícita.
- Variáveis `VITE_*` são incluídas nos arquivos públicos da interface: nunca
  coloque segredos nelas.

Para uso público, empresarial ou com informações sensíveis, faça uma avaliação
de segurança, privacidade, disponibilidade e recuperação de dados antes de
hospedar o sistema.
