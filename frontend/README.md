# Frontend — DataPulse Workspace

Este diretório contém a interface web do DataPulse, construída com Vue 3 e Vite.
Ela conversa com a API descrita no [README do backend](../backend/README.md).

O projeto está sob a [licença MIT](../LICENSE); consulte o arquivo para ver os
termos de uso e redistribuição.

- [Voltar ao início rápido do projeto](../README.md)
- [Documentação do backend e da API](../backend/README.md)

## Requisitos

- Node.js 22.18 ou mais recente na linha 22, ou 24.12 ou mais recente.
- npm, incluído com o Node.js.
- API DataPulse em execução para fazer login e acessar os dados.

## Instalar e iniciar no Windows

Abra um PowerShell na raiz do repositório:

```powershell
cd frontend
npm.cmd ci
npm.cmd run dev -- --host 127.0.0.1
```

Abra <http://127.0.0.1:5173>. Durante o desenvolvimento, o Vite encaminha
`/api`, `/docs` e `/openapi.json` para `http://127.0.0.1:8000`. Inicie a API
antes de usar a interface; veja o
[passo a passo do backend](../backend/README.md#instalar-e-iniciar).

Usamos `npm.cmd` porque algumas instalações do PowerShell bloqueiam scripts
`.ps1`, como `npm.ps1`. Não é necessário alterar a política de execução do
Windows.

## Primeiro acesso

1. Abra a página inicial e selecione **Primeiro acesso? Configurar administrador**.
2. Crie o primeiro usuário. Ele será administrador e o cadastro inicial fechará.
3. Faça login com o nome de usuário e a senha.
4. Escolha **Começar tour** para conhecer as principais páginas ou feche o tour
   para explorar por conta própria.
5. No dashboard, use **Primeiros passos no DataPulse** para importar dados,
   executar uma análise e salvar o resultado como relatório.

O nome de usuário é usado no login. Email é opcional e serve como contato.
O tour pode ser aberto novamente no menu do perfil em **Fazer tour do sistema**.

## Funcionalidades

| Página                     | Para que serve                                                                               |
| -------------------------- | -------------------------------------------------------------------------------------------- |
| **Visão geral**            | Resumo do workspace, indicadores, atividade recente e alertas.                               |
| **Fontes e datasets**      | Cadastrar origens, organizar datasets e inspecionar registros.                               |
| **Importações**            | Enviar arquivos, acompanhar processamento e entender linhas rejeitadas.                      |
| **Analytics e tendências** | Criar consultas com filtros, agrupamentos, gráficos e períodos.                              |
| **KPIs**                   | Salvar indicadores e acompanhar metas.                                                       |
| **Insights e alertas**     | Investigar anomalias estatísticas e monitorar limites.                                       |
| **Relatórios**             | Salvar snapshots de consultas e exportá-los como CSV.                                        |
| **Configurações**          | Editar perfil e senha; administradores também gerenciam equipe, demo, auditoria e operações. |
| **Notificações**           | Consultar eventos da conta e marcar notificações como lidas.                                 |

O sistema oferece uma interface responsiva em português, tema claro e escuro,
busca global, navegação por teclado e suporte a `prefers-reduced-motion`.
Gráficos e resultados refletem dados existentes; períodos sem dados não são
preenchidos com previsões ou valores fictícios.

## Conta pública de demonstração

A conta pública não é criada automaticamente. Para habilitá-la:

1. Configure `DEMO_MODE=true` e uma senha privada em `DEMO_PASSWORD` no
   `backend/.env`.
2. Reinicie a API.
3. Entre como administrador e selecione **Criar conta pública** em
   **Configurações**.
4. Na tela de login, selecione **GUIA** para consultar as credenciais.

As credenciais vêm da configuração privada do backend; não há senha demo real
versionada neste repositório. A conta é compartilhada com os outros usuários do
mesmo banco: não insira informações pessoais ou confidenciais.

Um administrador pode restaurar o dataset sintético **Vendas de demonstração**
em **Configurações**. A ação exige confirmação e substitui somente os registros
desse dataset. Os demais datasets, fontes e relatórios permanecem intactos.

## Perfil, equipe e senhas

- Cada usuário pode editar seu próprio nome de usuário e email opcional em
  **Configurações**.
- Usuários podem alterar a própria senha informando a senha atual.
- Um administrador pode gerar uma senha provisória para outro membro. Ela é
  exibida uma única vez; compartilhe-a por um canal seguro e oriente a pessoa a
  alterá-la ao entrar.
- A redefinição e a troca de senha revogam as sessões anteriores.
- O email não é obrigatório e não há recuperação automática de senha por email.

## Configuração da API

Por padrão, o cliente usa `/api/v1` na mesma origem. No desenvolvimento, o proxy
do Vite encaminha as chamadas para a API local.

Para usar outra API, defina `VITE_API_URL` antes de iniciar o Vite ou gerar o
build:

```powershell
$env:VITE_API_URL = "https://api.exemplo.com/api/v1"
npm.cmd run build
```

Tudo que começa com `VITE_` é incorporado aos arquivos públicos do navegador.
**Nunca coloque senhas, chaves privadas, tokens SMTP ou qualquer segredo em
variáveis `VITE_*`.** Quando a interface e a API compartilham a origem, prefira
configurar um proxy no servidor.

## Testes e verificações

Execute os comandos na pasta `frontend`:

```powershell
npm.cmd ci
npm.cmd test
npx.cmd oxlint .
npx.cmd eslint .
npm.cmd run build
```

O comando `npm.cmd run lint` executa os linters com `--fix` e pode alterar
arquivos. Para apenas verificar, use os comandos `npx.cmd` acima.

### Testes E2E com Playwright

Instale o Chromium uma vez:

```powershell
npm.cmd exec playwright -- install chromium
```

Configure o caminho do Python com as dependências do backend e execute:

```powershell
$env:DATAPULSE_PYTHON = (Get-Command python).Source
npm.cmd run test:e2e
```

O Playwright inicia uma API, um worker e um Vite isolados, com banco temporário.
Mantenha as portas `18770` e `18771` livres. Os testes não usam o banco local de
desenvolvimento. Para executar todas as verificações do projeto, consulte
[Testes no README principal](../README.md#testes).

## Build e hospedagem

Gere os arquivos estáticos na pasta `frontend`:

```powershell
npm.cmd run build
```

O resultado fica em `dist/`. O servidor que hospedar a interface precisa:

- servir arquivos estáticos;
- encaminhar rotas Vue desconhecidas para `index.html`;
- encaminhar `/api` para o backend;
- opcionalmente encaminhar `/docs` e `/openapi.json` para disponibilizar o Swagger.

O proxy de desenvolvimento do Vite não é incluído no build de produção. Em
produção, configure um proxy no servidor ou defina `VITE_API_URL` durante o
build e autorize a origem exata no CORS do backend. A hospedagem da interface,
sozinha, não executa a API nem o worker.

### Publicar o frontend no Render

O frontend pode ser hospedado como um **Static Site**. A documentação oficial do
Render para Vue usa a pasta `dist` como diretório publicado e recomenda uma
regra de rewrite para rotas do Vue Router.

1. Envie o branch `main` para o GitHub e entre no
   [Render Dashboard](https://dashboard.render.com/).
2. Selecione **New > Static Site** e conecte o repositório
   `Z3nithy/DataPulse`. Autorize o acesso ao GitHub, se solicitado.
3. Configure os campos:

   | Campo no Render | Valor |
   |---|---|
   | **Name** | `datapulse-frontend` (ou outro nome disponível) |
   | **Branch** | `main` |
   | **Root Directory** | `frontend` |
   | **Build Command** | `npm ci && npm run build` |
   | **Publish Directory** | `dist` |

4. Em **Environment**, adicione `NODE_VERSION` com o valor `22.18.0` para usar
   uma versão compatível com `frontend/package.json`.
5. Selecione **Create Static Site** e aguarde o primeiro deploy.
6. Abra o endereço `https://<nome-do-site>.onrender.com` que o Render mostrar.
   O deploy automático pode atualizar o site quando houver novos pushes para o
   branch `main`.

#### Habilitar as rotas do Vue Router

No serviço do Render, abra **Redirects/Rewrites** e adicione:

| Campo | Valor |
|---|---|
| **Source** | `/*` |
| **Destination** | `/index.html` |
| **Action** | `Rewrite` |

Essa regra serve o `index.html` quando alguém abre ou atualiza diretamente uma
rota da aplicação, por exemplo `/settings`. Sem ela, o navegador pode receber
404 nessas rotas. O Render preserva os arquivos existentes, como JavaScript e
CSS, antes de aplicar a regra.

#### Conectar à API

O frontend hospedado precisa da URL pública da API. Como o backend ainda é uma
etapa separada, o primeiro deploy do site estático pode mostrar a interface, mas
login, dados e outras chamadas à API não funcionarão até essa URL ser
configurada.

Depois que a API estiver hospedada:

1. No serviço estático do Render, abra **Environment** e adicione ou atualize
   `VITE_API_URL` com a URL base da API, incluindo o prefixo. Exemplo:
   `https://datapulse-api.onrender.com/api/v1`.
2. Salve a alteração e faça um novo deploy para que o Vite incorpore a variável
   ao build.
3. No backend, inclua a origem exata do site estático em `CORS_ORIGINS`, por
   exemplo `https://datapulse-frontend.onrender.com`, e reinicie/reimplante a API.
4. Acesse `/ready` no endereço da API para confirmar que ela está pronta antes
   de testar o login.

`VITE_API_URL` é incluída no JavaScript público e deve conter somente o endereço
da API. **Não coloque senhas, tokens ou outras credenciais nessa variável.**
O endereço real do backend, `CORS_ORIGINS` e a persistência do banco serão
definidos na etapa de hospedagem do backend.

## Estrutura do código

```text
src/App.vue                    login, sessão e estrutura geral
src/router/                    páginas e navegação
src/views/WorkspaceView.vue    telas e fluxos principais do workspace
src/components/                dashboard, tabelas, gráficos e formulários
src/components/ui/             dialogs, notificações e estados reutilizáveis
src/services/api.js            cliente HTTP, erros, downloads e paginação
src/services/dateRange.js      filtros e limites de período
src/stores/                    sessão e preferências da interface
src/composables/motion.js       animações e suporte a movimento reduzido
tests/                         testes unitários do cliente e datas
e2e/                           testes completos no navegador
```

## Limites conhecidos

- A interface depende da API DataPulse; não funciona como dashboard autônomo.
- Não há separação multiempresa: usuários no mesmo banco compartilham o workspace.
- O período global não altera KPIs salvos nem snapshots de relatórios existentes.
- Acessibilidade e responsividade devem ser revalidadas nos navegadores e
  dispositivos pretendidos após cada mudança.
