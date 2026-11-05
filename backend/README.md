# Backend — DataPulse API

Este diretorio contem a API REST, o banco SQLite, as migrations Alembic e o
worker que executa tarefas demoradas. A API e o frontend rodam como processos
separados e conversam por HTTP.

- [Voltar a visao geral e inicio rapido](../README.md)
- [Documentacao da interface](../frontend/README.md)

## Como o backend funciona

1. O FastAPI recebe e valida requisicoes.
2. Os schemas Pydantic validam os dados de entrada.
3. Rotas aplicam autenticacao/permissoes e chamam os servicos de dominio.
4. SQLAlchemy persiste dados em SQLite; Alembic controla as alteracoes do esquema.
5. O processo `worker` consulta tarefas pendentes e executa importacoes e
   agendamentos sem bloquear a API.

Nao sao criadas tabelas automaticamente no startup. Se o banco nao estiver na
ultima migration, API e worker falham explicitamente para evitar operar com um
esquema incompatível.

## Requisitos

- Python 3.14.
- PowerShell no Windows (os comandos podem ser adaptados para macOS/Linux).
- As dependencias de `requirements.txt`.

## Instalar e iniciar localmente

Execute os comandos abaixo no PowerShell a partir da raiz do repositorio:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Edite `.env` e preencha `SECRET_KEY`. Gere um valor localmente:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Copie a saida para `SECRET_KEY` no `.env`. Nao a publique, nao a envie para o
frontend e nao a reutilize em outros projetos. O `.env` e ignorado pelo Git e
excluido do contexto Docker; `.env.example` contem apenas valores de exemplo.

Ainda na pasta `backend`, execute:

```powershell
python -m alembic upgrade head
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

Em outro terminal, ative o mesmo ambiente virtual, entre em `backend` e inicie
o worker:

```powershell
python -m worker
```

O worker e necessario para importacoes em segundo plano e agendamentos. Se ficar
offline, a API continua ativa e as tarefas ficam aguardando na fila.

### Endpoints uteis

| Endereco | Finalidade |
|---|---|
| <http://127.0.0.1:8000/docs> | Swagger interativo |
| <http://127.0.0.1:8000/openapi.json> | Contrato OpenAPI |
| <http://127.0.0.1:8000/health> | Verifica se o processo responde |
| <http://127.0.0.1:8000/ready> | Verifica se o banco esta acessivel |

O frontend usa o proxy do Vite para encaminhar `/api` e `/docs` para a API local.

## Configuracao

Copie `.env.example` para `.env`. As variaveis mais usadas:

| Variavel | Obrigatoria | Descricao |
|---|---:|---|
| `DATABASE_URL` | Sim | URL SQLAlchemy. O exemplo usa `sqlite:///./database.db`; caminhos relativos sao resolvidos a partir de `backend`. |
| `SECRET_KEY` | Sim | Chave privada para assinar JWTs; minimo de 32 caracteres. |
| `ALGORITHM` | Nao | Somente `HS256` e aceito. |
| `CORS_ORIGINS` | Nao | Lista separada por virgulas das origens autorizadas. |
| `API_ALLOWED_HOSTS` | Nao | Hosts HTTPS publicos permitidos para importacao de API; vazio desabilita essa integracao. |
| `WORKER_LOCK_PATH` | Nao | Arquivo usado para impedir workers concorrentes no mesmo banco/volume. |
| `SMTP_ENABLED` | Nao | `false` por padrao; habilite somente quando SMTP estiver configurado. |
| `SMTP_HOST`, `SMTP_PORT` | Quando SMTP e habilitado | Servidor e porta do provedor de email. |
| `SMTP_SECURITY` | Quando SMTP e habilitado | `starttls` ou `ssl`; a verificacao TLS permanece ativa. |
| `SMTP_USERNAME`, `SMTP_PASSWORD` | Nao | Credenciais do provedor; configure apenas no ambiente local/servidor. |
| `SMTP_FROM` | Quando SMTP e habilitado | Endereco remetente autorizado pelo provedor. |
| `DATAPULSE_API_*` | Nao | Segredos de fontes externas HTTPS; configure no backend, nunca no Vue. |

Variaveis nao definidas no `.env` podem usar os valores padrao descritos em
`.env.example`. `DATABASE_URL` e obrigatoria e `SECRET_KEY` nao pode ficar vazia.
Nao use o mesmo segredo entre desenvolvimento e producao.

## Autenticacao e permissoes

- O primeiro usuario cadastrado e administrador. O cadastro inicial fecha depois.
- Administradores criam novos membros; eles comecam como leitores.
- Leitores consultam; editores tambem criam e processam dados; administradores
  gerenciam papeis e auditoria.
- As permissoes sao verificadas na API, nao apenas na interface.
- JWTs expiram em 60 minutos. Alterar senha, alterar permissoes ou encerrar sessoes
  revoga os tokens existentes; a senha e armazenada usando Argon2.
- Login e cadastro inicial tem limite local de tentativas por IP.

O endpoint `POST /api/v1/auth/password` exige a senha atual e devolve um token
novo para a sessao atual. `POST /api/v1/auth/logout` encerra todas as sessoes da
conta. Nao ha recuperacao automatizada de senha, refresh token ou MFA.

Todos os usuarios no mesmo banco compartilham um unico workspace. O projeto nao
implementa isolamento multiempresa e nao deve receber dados confidenciais sem
avaliacao e controles adicionais.

## Endpoints da API

Todos os endpoints de negocio tem o prefixo `/api/v1`. Para modelos, tipos e
respostas completos, consulte o Swagger em `/docs`.

| Area | Rotas principais |
|---|---|
| Sessao | `/auth/setup`, `/auth/register`, `/auth/login`, `/auth/me`, `/auth/password`, `/auth/logout` |
| Equipe | `/users`, `/audit` |
| Fontes e dados | `/sources`, `/datasets`, `/datasets/{id}/records` |
| Importacoes | `/ingestion/import`, `/ingestion/jobs` |
| Analytics | `/analytics/query`, `/analytics/summary`, `/analytics/trends` |
| Indicadores | `/kpis`, `/insights`, `/alerts` |
| Relatorios | `/reports`, `/reports/{id}/export` |
| Operacoes pessoais | `/notifications`, `/favorites` |
| Agendamentos/worker | `/schedules`, `/operations/status`, `/operations/metrics` |

Sucesso segue o formato `{"data": ..., "meta": ...}`. Erros incluem codigo,
mensagem, detalhes de validacao e identificador de requisicao. Colecoes usam
paginacao; o tamanho maximo de pagina e 100.

### Importacao e processamento

- Formatos: CSV, JSON, XLSX e XLS.
- Limites: 5 MB por arquivo/resposta, ate 100 colunas e 10.000 linhas por
  importacao.
- Dados sao normalizados e validados conforme o esquema; duplicados sao ignorados.
- Importacao em segundo plano retorna `202 Accepted`: isso confirma que entrou na
  fila, nao que a importacao terminou. Consulte o job pelo endpoint de historico.
- Integracoes externas usam HTTPS e exigem host autorizado em `API_ALLOWED_HOSTS`.

### Analytics

Consultas estruturadas oferecem `count`, `sum`, `avg`, `min` e `max`, filtros
tipados, agrupamentos e tendencias. Consultas SQL livres nao sao aceitas.
Insights usam uma regra estatistica de anomalia; nao sao previsoes nem IA.

## Migrations

Depois de atualizar o codigo, crie backup do banco e aplique migrations:

```powershell
python -m alembic upgrade head
```

Para criar uma migration durante o desenvolvimento:

```powershell
python -m alembic revision --autogenerate -m "descricao da alteracao"
```

Revise o arquivo gerado antes de usa-lo. Para verificar se os modelos e migrations
estao sincronizados:

```powershell
python -m alembic check
```

Evite `downgrade base`: ele remove as tabelas do DataPulse e seus dados.

## Backups e restauracao SQLite

O modulo `backup.py` cria backups online do SQLite e verifica integridade e
chaves estrangeiras. Guarde backups fora da pasta servida pela aplicacao e nao
os publique no repositorio.

```powershell
python -m backup backup C:\backups\datapulse-2026-11-05.backup
python -m backup verify C:\backups\datapulse-2026-11-05.backup
python -m backup restore C:\backups\datapulse-2026-11-05.backup --target C:\dados\restaurado.db
```

Restore exige um destino novo e nunca sobrescreve o arquivo existente. Para
simular a retencao dos sete backups validos mais recentes:

```powershell
python -m backup retain C:\backups --keep 7
```

So remove arquivos excedentes quando solicitado explicitamente:

```powershell
python -m backup retain C:\backups --keep 7 --apply
```

Agendar backups e responsabilidade do ambiente de execucao. No Windows, use o
Agendador de Tarefas; revise uma simulacao de retencao antes de habilitar a
remocao automatica e mantenha uma copia externa.

## Testes

Execute em `backend`:

```powershell
python -m unittest discover -s tests -v
python -m alembic upgrade head
python -m alembic check
```

Os testes usam um banco SQLite temporario e uma chave de teste; nao reutilizam
o banco local do projeto nem fazem chamadas a APIs privadas. A suite cobre
autenticacao, permissoes, migrations, importacoes, analytics, operacoes e
backups.

## Docker Compose

O arquivo raiz `compose.yaml` cria os servicos `migrate`, `api`, `worker` e `web`.
Antes de subir os containers, crie `backend/.env`, defina `SECRET_KEY` e, na raiz:

```powershell
$env:APP_ADDRESS = "localhost"
docker compose config --quiet
docker compose up --build
```

Compose usa um volume persistente para SQLite e migrations sao executadas antes
da API. O `backend/.dockerignore` impede que `.env`, bancos locais e backups sejam
copiados para a imagem. Em um dominio publico, configure DNS, CORS e HTTPS antes
de expor a aplicacao.

## Estrutura do codigo

```text
main.py                    cria a aplicacao FastAPI e middleware
routes/api.py              autenticacao, equipe e funcionalidades de dados
routes/operations.py       notificacoes, favoritos e agendamentos
schemas/datapulse.py       validacao dos contratos HTTP
models/entities.py         tabelas e relacoes SQLAlchemy
services/                  ingestao, analytics, eventos, relatorios e fila
database/                  engine e sessoes SQLAlchemy
migrations/                historico versionado do esquema
worker.py                  processamento de tarefas fora da API
backup.py                  backup, verificacao, restore e retencao
tests/                     testes de API, dominio e persistencia
```

## Limites e operacao

SQLite e o banco intencional para este portfolio. O worker e protegido por trava
de filesystem e a arquitetura e para uma maquina/volume compartilhado; nao
execute multiplas replicas em hosts diferentes. Rate limiting e local, nao
distribuido. Para uma aplicacao real com dados sensiveis, avalie seguranca,
privacidade, backup, recuperacao de conta e requisitos de disponibilidade antes
da publicacao.
