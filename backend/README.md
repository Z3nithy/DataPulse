# Backend — API e operações

Este diretório contém a API FastAPI, o banco SQLite, as migrations Alembic e o
worker que processa importações e agendamentos em segundo plano. A interface web
fica em [`../frontend`](../frontend/README.md).

- [Voltar ao início rápido do projeto](../README.md)
- [Documentação da interface](../frontend/README.md)

## Como as peças trabalham juntas

1. A API recebe as chamadas HTTP da interface e valida os dados com Pydantic.
2. As rotas verificam a sessão e as permissões do usuário.
3. Os serviços executam importações, consultas e operações de domínio.
4. SQLAlchemy acessa o banco SQLite; Alembic mantém o esquema atualizado.
5. O processo worker busca tarefas pendentes e as executa fora da API.

A API, o worker e a interface são processos separados. Use o mesmo arquivo
`.env` e o mesmo banco SQLite na API e no worker. O worker não inicia
automaticamente junto com a API.

> O aplicativo não cria nem atualiza tabelas automaticamente ao iniciar. Se o
> banco não estiver na migration mais recente, a API e o worker interrompem a
> inicialização para evitar operar com um esquema incompatível.

## Requisitos

- Python 3.14.
- PowerShell no Windows (os comandos podem ser adaptados para macOS/Linux).
- Dependências listadas em [`requirements.txt`](requirements.txt).

## Instalar e iniciar

Abra um PowerShell na raiz do repositório e crie o ambiente:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Edite `backend/.env` e defina `SECRET_KEY`. Gere uma chave localmente:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Copie o valor para `SECRET_KEY`. A chave deve ter pelo menos 32 caracteres.
Mantenha-a privada e não a reutilize em outros projetos. O arquivo `.env` é
ignorado pelo Git; somente `.env.example`, sem segredos, deve ser versionado.

Ainda na pasta `backend`, aplique as migrations e inicie a API:

```powershell
python -m alembic upgrade head
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

Abra **outra** janela do PowerShell, ative o mesmo ambiente virtual e inicie o
worker:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m worker
```

Se o worker estiver offline, a API continua respondendo, mas importações
assíncronas e agendamentos aguardam na fila. O painel **Automação e
agendamentos** mostra o estado do worker, as tarefas recentes e os motivos
registrados para falhas.

### Endpoints locais úteis

| Endereço                             | O que verifica                   |
| ------------------------------------ | -------------------------------- |
| <http://127.0.0.1:8000/docs>         | Documentação interativa Swagger  |
| <http://127.0.0.1:8000/openapi.json> | Contrato OpenAPI                 |
| <http://127.0.0.1:8000/health>       | Se o processo da API responde    |
| <http://127.0.0.1:8000/ready>        | Se a API e o banco estão prontos |

No desenvolvimento, o Vite encaminha `/api`, `/docs` e `/openapi.json` para a
API local.

## Configuração (`.env`)

Copie `.env.example` para `.env` e altere apenas o que for necessário.
`DATABASE_URL` e `SECRET_KEY` são obrigatórias. Em desenvolvimento local, SMTP
e integrações externas podem ficar desabilitados.

| Variável                         | Obrigatória      | Descrição                                                                                                      |
| -------------------------------- | ---------------- | -------------------------------------------------------------------------------------------------------------- |
| `DATABASE_URL`                   | Sim              | URL SQLAlchemy. O exemplo usa `sqlite:///./pulse.db`; caminhos relativos são resolvidos a partir de `backend`. |
| `SECRET_KEY`                     | Sim              | Chave privada para assinar JWTs; mínimo de 32 caracteres.                                                      |
| `ALGORITHM`                      | Não              | Algoritmo JWT; o projeto exige `HS256`.                                                                        |
| `CORS_ORIGINS`                   | Não              | Origens autorizadas separadas por vírgula.                                                                     |
| `API_ALLOWED_HOSTS`              | Não              | Hosts HTTPS autorizados para importação de API. Vazio desabilita essa integração.                              |
| `DEMO_MODE`                      | Não              | `false` por padrão. Defina `true` para permitir que um administrador crie a conta pública de demonstração.     |
| `DEMO_USERNAME`                  | Ao ativar a demo | Usuário configurado para a conta pública; 3 a 32 caracteres entre letras, números, ponto, hífen e sublinhado.  |
| `DEMO_PASSWORD`                  | Ao ativar a demo | Senha privada da conta pública, com 10 a 128 caracteres. Não use uma senha real ou reutilizada.                |
| `DEMO_EMAIL`                     | Não              | Email de contato opcional da conta pública; usado para notificações por email, não para login.                 |
| `WORKER_LOCK_PATH`               | Não              | Arquivo de trava que impede workers concorrentes usando o mesmo banco.                                         |
| `SMTP_ENABLED`                   | Não              | `false` por padrão; habilite somente após configurar SMTP.                                                     |
| `SMTP_HOST`, `SMTP_PORT`         | Com SMTP         | Servidor e porta do provedor.                                                                                  |
| `SMTP_SECURITY`                  | Com SMTP         | `starttls` ou `ssl`; a verificação TLS permanece ativa.                                                        |
| `SMTP_USERNAME`, `SMTP_PASSWORD` | Com SMTP         | Credenciais do provedor; configure somente em ambiente privado.                                                |
| `SMTP_FROM`                      | Com SMTP         | Endereço remetente autorizado pelo provedor.                                                                   |
| `DATAPULSE_API_*`                | Não              | Credenciais de fontes externas HTTPS; configure no backend, nunca no Vue.                                      |

O arquivo `.env.example` deixa a conta demo desativada e a senha vazia para não
publicar credenciais. Para ativar uma demonstração local:

1. Gere uma senha aleatória. Por exemplo:

   ```powershell
   python -c "import secrets; print(secrets.token_urlsafe(18))"
   ```

2. Defina `DEMO_MODE=true` e coloque a senha gerada em `DEMO_PASSWORD` no
   arquivo local `backend/.env`.
3. Reinicie a API e entre com a conta de administrador.
4. Abra **Configurações** e selecione **Criar conta pública**.
5. Depois da criação, o botão **GUIA** na tela de login mostra as credenciais
   configuradas.

Não publique o arquivo `.env` nem copie sua senha para capturas de tela,
documentação pública ou código-fonte.

## Contas, permissões e demonstração

- O primeiro usuário cadastrado torna-se administrador e fecha o cadastro inicial.
- O login usa nome de usuário; o email de contato é opcional.
- Administradores criam membros, que começam como leitores, e definem seus papéis.
- Leitores consultam dados; editores também criam e processam dados; administradores
  gerenciam a equipe e as operações.
- As permissões são verificadas na API, não apenas na interface.
- O GUIA da tela de login só disponibiliza a conta demo depois de sua criação
  explícita por um administrador.

### Restaurar dados sintéticos da conta demo

Em **Configurações**, um administrador pode restaurar os dados de demonstração.
A confirmação informa que serão substituídos apenas os registros do dataset
sintético `Vendas de demonstração`. Fontes, datasets, relatórios e registros de
outros datasets permanecem intactos. Se houver uma importação em andamento
nesse dataset, a operação é bloqueada até ela terminar.

A mesma operação está disponível em `POST /api/v1/users/demo/restore-data` e
retorna o número de registros recriados.

### Perfil e senhas

- `PATCH /api/v1/auth/profile`: cada usuário atualiza o próprio nome de usuário
  e email opcional.
- `POST /api/v1/auth/password`: troca de senha exige a senha atual e devolve um
  novo token para a sessão atual.
- `POST /api/v1/users/{id}/password-reset`: administrador gera uma senha
  provisória para outro membro. A senha aparece uma única vez na interface;
  sessões antigas são revogadas. Compartilhe a senha por um canal seguro e
  oriente o membro a alterá-la ao entrar.
- `POST /api/v1/auth/logout`: encerra todas as sessões da conta.

JWTs expiram em 60 minutos e as senhas são armazenadas com Argon2. O limite de
tentativas de login é local ao processo. Não há recuperação por email, refresh
token ou MFA.

## API

Todos os endpoints de negócio usam o prefixo `/api/v1`. O Swagger em
`/docs` mostra os modelos, parâmetros e exemplos completos.

| Área           | Rotas principais                                                                                                            |
| -------------- | --------------------------------------------------------------------------------------------------------------------------- |
| Sessão         | `/auth/setup`, `/auth/demo`, `/auth/register`, `/auth/login`, `/auth/me`, `/auth/profile`, `/auth/password`, `/auth/logout` |
| Equipe         | `/users`, `/users/{id}/password-reset`, `/users/demo/restore-data`, `/audit`                                                |
| Fontes e dados | `/sources`, `/datasets`, `/datasets/{id}/records`                                                                           |
| Importações    | `/ingestion/import`, `/ingestion/jobs`                                                                                      |
| Análises       | `/analytics/query`, `/analytics/summary`, `/analytics/trends`                                                               |
| Indicadores    | `/kpis`, `/insights`, `/alerts`                                                                                             |
| Relatórios     | `/reports`, `/reports/{id}/export`                                                                                          |
| Operações      | `/notifications`, `/favorites`, `/schedules`, `/operations/status`, `/operations/metrics`                                   |

Respostas bem-sucedidas usam o formato `{"data": ..., "meta": ...}`. Erros
incluem mensagem e detalhes de validação. Coleções são paginadas; o tamanho
máximo de página é 100.

### Importações e análises

- Formatos aceitos: CSV, JSON, XLSX e XLS.
- Limites: 5 MB por arquivo/resposta, até 100 colunas e 10.000 linhas por
  importação.
- Dados são validados e normalizados conforme o esquema do dataset. Duplicados
  são ignorados.
- Importações em segundo plano retornam `202 Accepted`: isso significa que a
  tarefa entrou na fila, não que terminou. Consulte o histórico de importações.
- Importações de API usam HTTPS e só aceitam hosts autorizados por
  `API_ALLOWED_HOSTS`.
- Consultas oferecem `count`, `sum`, `avg`, `min` e `max`, filtros tipados,
  agrupamentos e tendências. SQL livre não é aceito.
- Insights usam uma regra estatística para identificar anomalias; não são
  previsões nem resultados de IA.

## Diagnóstico do worker e da fila

1. Abra **Configurações** como administrador e atualize o painel de operações.
2. Se o worker estiver offline, confirme que a janela do worker está aberta,
   que usa o mesmo ambiente virtual e que aponta para o mesmo banco da API.
3. Se houver tarefas na fila, aguarde o worker processá-las. Uma fila parada
   pode indicar um erro no processo; consulte o terminal do worker.
4. Abra **Últimas tarefas em segundo plano** para ver status e mensagem de erro.
   Tarefas com falha não são reenviadas automaticamente; corrija a causa e crie
   uma nova execução.
5. Se o email falhar, abra **Últimas entregas de email** e verifique SMTP,
   conectividade, TLS, credenciais e logs do servidor.

## Migrations

Depois de atualizar o código, faça backup do banco e aplique as migrations na
pasta `backend`:

```powershell
python -m alembic upgrade head
```

Para criar uma migration durante o desenvolvimento:

```powershell
python -m alembic revision --autogenerate -m "descricao-da-alteracao"
```

Revise o arquivo gerado antes de usá-lo. Verifique se os modelos e migrations
estão sincronizados:

```powershell
python -m alembic check
```

Evite `downgrade base`: ele remove as tabelas do DataPulse e seus dados.

## Backups e restauração do SQLite

O módulo `backup.py` cria backups online do SQLite e verifica a integridade e
as chaves estrangeiras. Guarde os backups fora da pasta do projeto e nunca os
publique no repositório.

```powershell
python -m backup backup C:\backups\datapulse.backup
python -m backup verify C:\backups\datapulse.backup
python -m backup restore C:\backups\datapulse.backup --target C:\dados\restaurado.db
```

A restauração exige um arquivo de destino novo e não sobrescreve um arquivo
existente. Para simular a retenção dos sete backups válidos mais recentes:

```powershell
python -m backup retain C:\backups --keep 7
```

Arquivos excedentes só são removidos com `--apply`:

```powershell
python -m backup retain C:\backups --keep 7 --apply
```

Agendar backups é responsabilidade do ambiente de execução. No Windows, use o
Agendador de Tarefas. Revise uma simulação de retenção antes de habilitar a
remoção automática e mantenha uma cópia externa.

## Testes

Execute na pasta `backend`:

```powershell
python -m unittest discover -s tests -v
python -m alembic upgrade head
python -m alembic check
```

Os testes usam um banco SQLite temporário e uma chave exclusiva de teste; não
reutilizam o banco local nem fazem chamadas a APIs privadas. A suíte cobre
autenticação, permissões, migrations, importações, análises, operações e backups.

## Estrutura do código

```text
main.py                    cria a aplicação FastAPI e middleware
routes/api.py              autenticação, equipe e funcionalidades de dados
routes/operations.py       notificações, favoritos e agendamentos
schemas/datapulse.py       validação dos contratos HTTP
models/entities.py         tabelas e relações SQLAlchemy
services/                  ingestão, análise, eventos, relatórios e fila
database/                  engine e sessões SQLAlchemy
migrations/                histórico versionado do esquema
worker.py                  processamento de tarefas fora da API
backup.py                  backup, verificação, restauração e retenção
tests/                     testes de API, domínio e persistência
```

## Limites de operação

SQLite e a trava local do worker são adequados para este portfólio em uma única
máquina/volume. Não execute várias réplicas em hosts diferentes. O limite de
tentativas de login também é local, não distribuído.

Todas as contas no mesmo banco compartilham um único workspace. Para uso
empresarial, público ou com dados sensíveis, faça uma avaliação de segurança,
privacidade, backup, recuperação de conta e disponibilidade antes de hospedar o
sistema.
