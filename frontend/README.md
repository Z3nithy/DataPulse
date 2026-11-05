# Frontend — DataPulse Workspace

Este diretorio contem a interface web do DataPulse. Ela foi feita com Vue 3 e
consome a API descrita em [backend/README.md](../backend/README.md).

- [Voltar a visao geral e inicio rapido](../README.md)
- [Documentacao da API](../backend/README.md)

## Requisitos

- Node.js 22.18 ou mais recente na linha 22, ou 24.12 ou mais recente.
- npm incluido com o Node.js.
- A API DataPulse em execucao para login e acesso aos dados.

## Instalar e iniciar no Windows

Abra um PowerShell na raiz do repositorio:

```powershell
cd frontend
npm.cmd ci
npm.cmd run dev -- --host 127.0.0.1
```

Abra <http://127.0.0.1:5173>. `npm.cmd` evita a restricao de execucao de
`npm.ps1` que pode existir no PowerShell; nao e necessario alterar a politica de
scripts do Windows.

Durante o desenvolvimento, o Vite encaminha `/api`, `/docs` e `/openapi.json`
para `http://127.0.0.1:8000`. Inicie o backend antes de usar a aplicacao; os
passos estao no [guia do backend](../backend/README.md#instalar-e-iniciar-localmente).

## Configuracao da API

Por padrao, o cliente usa `/api/v1` na mesma origem. Isso funciona com o proxy
local do Vite e com o proxy de producao configurado no Caddy.

Para apontar para outra API, configure `VITE_API_URL` antes de iniciar o Vite ou
antes de criar o build:

```powershell
$env:VITE_API_URL = "https://api.exemplo.com/api/v1"
npm.cmd run build
```

`VITE_*` e embutido nos arquivos publicos do navegador. **Nunca coloque senhas,
chaves privadas, tokens SMTP ou qualquer segredo em variaveis `VITE_*`.**
Quando API e interface compartilham a origem, o proxy e preferivel porque evita
configuracao CORS adicional.

## Como usar

1. Abra a tela inicial e cadastre a conta de administrador na primeira execucao.
2. Crie fontes e datasets, ou defina um esquema manualmente.
3. Importe CSV, JSON, XLSX ou XLS. Para importacoes em segundo plano, mantenha o
   worker do backend ativo.
4. Explore analytics, tendencias, KPIs, insights e relatorios.
5. Configure alertas e, se necessario, membros da equipe.

Nao existem contas ou registros de demonstracao pre-criados. Os usuarios de um
banco compartilham um unico workspace; a interface nao e uma fronteira de
isolamento entre organizacoes.

## Paginas e funcionalidades

- **Visao geral:** contagens, KPIs, dados recentes, graficos, tendencias, insights,
  alertas e estado de importacoes.
- **Fontes e datasets:** cadastro, metadados, esquema e previa dos registros.
- **Importacoes:** upload sincronico ou em segundo plano, historico e erros de
  validacao.
- **Analytics:** consultas estruturadas, filtros, agrupamentos, graficos e
  favoritos pessoais.
- **KPIs e tendencias:** indicadores salvos, metas e comparacao dos periodos
  observados.
- **Insights e alertas:** deteccao estatistica explicavel e regras de limite.
  Insights nao sao resultados de IA nem previsoes.
- **Relatorios:** snapshots dos resultados e exportacao CSV autenticada.
- **Configuracoes:** alteracao de senha, membros e papeis; administradores tambem
  consultam auditoria, worker, fila e agendamentos.
- **Notificacoes:** eventos persistidos por usuario, leitura individual/em lote e
  atualizacao periodica sem push.
- **Busca global:** paginas, fontes, datasets e KPIs; use `Ctrl+K` ou `Cmd+K`.

O tema, o estado da sidebar e o periodo selecionado sao preferencias locais. A
interface adapta-se a telas pequenas, suporta navegacao por teclado e respeita a
preferencia `prefers-reduced-motion`.

### Sessao e seguranca

O JWT fica no `sessionStorage` da aba e expira em 60 minutos. Em Configuracoes,
o usuario pode mudar a senha; as sessoes antigas sao revogadas e a aba atual
recebe um novo token. **Sair de todas as sessoes** invalida os tokens da conta no
servidor.

## Comandos de desenvolvimento

Todos abaixo sao executados na pasta `frontend`:

```powershell
npm.cmd test
npx.cmd oxlint .
npx.cmd eslint .
npm.cmd run build
```

Os comandos `npx` acima verificam os arquivos e nao aplicam correcoes
automaticamente. `npm.cmd run lint` e um atalho legado que executa as ferramentas
com `--fix`; use-o somente se quiser que o lint altere arquivos.

### Testes E2E com Playwright

Instale o Chromium uma vez:

```powershell
npm.cmd exec playwright -- install chromium
```

Configure o caminho do Python (com dependencias do backend instaladas) e rode:

```powershell
$env:DATAPULSE_PYTHON = (Get-Command python).Source
npm.cmd run test:e2e
```

O Playwright inicia uma API, um worker e um Vite isolados, usando banco e chave
temporarios em portas locais dedicadas. Nao reutiliza o banco de desenvolvimento.
Deixe as portas `18770` e `18771` livres. Para todos os testes e validacoes,
consulte a [secao raiz](../README.md#testes-e-verificacoes).

## Build e publicacao

Crie os arquivos estaticos para servir:

```powershell
npm.cmd run build
```

O resultado fica em `dist/`. O servidor que o hospeda deve:

- servir arquivos estaticos;
- redirecionar rotas Vue desconhecidas para `index.html`;
- encaminhar `/api` para o backend;
- encaminhar `/docs` e `/openapi.json` se quiser disponibilizar o Swagger.

O proxy de desenvolvimento do Vite nao e incluido no build de producao. Configure
um proxy no servidor ou defina `VITE_API_URL` no momento do build e autorize a
origem exata no CORS do backend.

Para executar o conjunto local com Docker, incluindo Caddy e HTTPS, use o
[Compose na raiz](../README.md#executar-com-docker). O [Dockerfile](Dockerfile)
cria o build Vue e o serve com Caddy; o [.dockerignore](.dockerignore) deixa fora
dependencias instaladas, arquivos locais e resultados de testes.

## Estrutura do codigo

```text
src/App.vue                    login, sessao e estrutura geral
src/router/                    paginas e navegacao
src/views/WorkspaceView.vue    telas e fluxos principais do workspace
src/components/                dashboard, tabelas, graficos e formularios
src/components/ui/             dialogs, notificacoes e estados reutilizaveis
src/services/api.js            cliente HTTP, erros, downloads e paginacao
src/services/dateRange.js      filtros e limites de periodo
src/stores/                    estado da sessao e preferencias da interface
src/composables/motion.js      animacoes com limpeza e suporte a movimento reduzido
tests/                         testes unitarios do cliente e datas
e2e/                           fluxo completo do navegador
```

## Limites conhecidos

- A aplicacao exige uma API DataPulse; nao funciona como dashboard autonomo.
- Nao inclui autenticacao multiempresa ou separacao de dados entre equipes.
- O periodo global nao altera KPIs salvos nem snapshots de relatorios existentes.
- Graficos e resultados exibem dados existentes; nao completam periodos ausentes
  com previsoes ou valores ficticios.
- Acessibilidade e responsividade foram consideradas, mas devem ser revalidadas
  em cada mudanca e nos navegadores/dispositivos pretendidos.
