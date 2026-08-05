# Automação de comentários e DM do Instagram — histórico e decisões

Este arquivo documenta o que já foi decidido e feito nesse app, pra
qualquer conversa futura conseguir continuar sem precisar reconstruir
esse contexto do zero. Ver também `marketing/instagram/README.md` pro
histórico do bot de **publicação** (`instagram_bot/`) - é um app
diferente, independente deste.

## O que esse app faz

Responde comentários que batem com uma palavra-chave num post específico
do Instagram: pode responder o comentário publicamente e/ou mandar uma
DM/resposta privada (mesmo mecanismo que ferramentas como ManyChat usam
pra "comenta X e recebe no direto"). Dá pra ter várias automações rodando
em paralelo (uma por post), e mais de uma conta do Instagram conectada.

## Contexto de por que foi feito assim

- **Múltiplas contas, logins separados**: o dono do site (cash-b) e a
  esposa dele (influencer, usa o Instagram dela) usam o mesmo app, cada
  um só vendo e gerenciando as próprias contas/automações. Por isso um
  login próprio (`/automacao/entrar/`), separado do login de clientes do
  site (mesmo model de usuário Django, `accounts.User`, mas gate por
  `is_staff=True` em vez de cadastro público - ver "Login" abaixo).
- **Polling em vez de webhook**: tempo real de verdade exigiria um
  webhook (URL pública, HTTPS, cadastrada no painel da Meta) - polling é
  bem mais simples de configurar (sem precisar de servidor público
  dedicado nem revisão de app) e um atraso de segundos é imperceptível
  pra esse tipo de automação.
- **Background Worker no Render, não GitHub Actions**: como o site já
  está no plano pago do Render (não no gratuito), dá pra ter um processo
  vivo 24h fazendo o polling a cada poucos segundos, em vez de depender
  do GitHub Actions (que tem intervalo mínimo de minutos e não roda um
  processo contínuo).
- **Múltiplas palavras-chave por automação**: pra cobrir variações
  ("quero", "manda", "envia" todas disparando a mesma resposta).
- **Checkboxes independentes** (responder comentário / enviar DM): o
  usuário pode querer só uma das duas ações, não sempre as duas juntas.

## Onde cada coisa mora no código

- `models.py` — `ContaInstagramConectada` (conta do Instagram + token,
  vinculada a um usuário), `AutomacaoComentario` (regra: post, palavras-
  chave, checkboxes + textos, ativa/pausada), `ComentarioProcessado`
  (histórico + base dos indicadores).
- `instagram_api.py` — chamadas à Instagram Graph API parametrizadas por
  conta (token/ID vêm do banco, não de settings globais, diferente do
  `instagram_bot`): listar comentários, responder publicamente, enviar
  resposta privada (DM), listar mídias recentes (pra escolher o post sem
  digitar ID), listar conversas (pra checar se uma DM foi respondida).
- `services.py` — `processar_ciclo()`: percorre as automações ativas,
  casa palavra-chave, responde/envia DM, registra; e
  `verificar_dms_respondidas()`: confere se alguém respondeu uma DM
  enviada anteriormente.
- `management/commands/automacao_instagram_worker.py` — loop infinito
  (`while True: processar_ciclo(); sleep(intervalo)`), é o Start Command
  do Background Worker no Render.
- `views.py`/`urls.py`/`templates/` — login próprio, telas de contas
  conectadas, automações (lista + criar/editar/pausar), histórico.

## Login e permissões

Reaproveita `accounts.User` (o mesmo model de usuário do site, já que
Django só permite um `AUTH_USER_MODEL` por projeto) mas gate por
`is_staff=True`, **não** por cadastro público - os usuários (você e sua
esposa) são criados manualmente pelo Django Admin
(`/admin/accounts/user/add/`). **Atenção**: a tela de criação do Admin
exige preencher CPF (campo obrigatório e único no model `User`) - sem
isso, criar um segundo usuário quebra com erro 500 (bug já corrigido, ver
`accounts/admin.py`).

Cada usuário só vê e gerencia as próprias `ContaInstagramConectada` (e,
por tabela, as automações e histórico vinculados a elas) - filtro por
`usuario=request.user` em todas as views, não é baseado em permissão do
Django Admin.

## Conectando uma conta do Instagram

O App da Meta usado (o mesmo do `instagram_bot`, caso de uso "Gerenciar
mensagens e conteúdo no Instagram") usa **Standard Access** (sem revisão
de app) - isso só funciona enquanto quem usa a API tiver função nesse
mesmo App. Pra conectar uma conta que não seja a original (`usecashb`):

1. No painel Meta for Developers do App, ir em **Funções** e adicionar a
   nova conta do Instagram como pessoa/conta de teste.
2. Gerar o access token de longa duração pra essa conta (mesmo processo
   do `instagram_bot` - ver `marketing/instagram/README.md`, "Fase 1").
3. Em `/automacao/contas/`, adicionar a conta com o ID da conta comercial
   + o token gerado.

Sem o passo 1, qualquer chamada à API com o token dessa conta nova falha
com erro de permissão.

## Rodando o worker no Render (Background Worker)

1. No dashboard do Render, criar um serviço novo do tipo **Background
   Worker**, apontando pro mesmo repositório/branch do site.
2. Start Command: `python manage.py automacao_instagram_worker`
3. Compartilhar as variáveis de ambiente de banco de dados
   (`DATABASE_URL`) e `DJANGO_SECRET_KEY` com o serviço web - o worker
   usa o mesmo banco.
4. Opcional: `AUTOMACAO_INSTAGRAM_INTERVALO_SEGUNDOS` (padrão 30) pra
   mudar o intervalo do polling.

É um serviço com custo próprio no Render, separado do plano do site (ver
preço atual no dashboard antes de criar).

## Indicadores

Por automação: comentários correspondidos, respostas públicas enviadas,
DMs enviadas, DMs respondidas. **Nenhum desses vem pronto da API** - são
calculados aqui a partir do `ComentarioProcessado`, contando o que o
próprio worker registrou em cada ciclo.

A parte de "DM respondida" é a mais delicada: depois de enviar uma DM, o
worker também confere as conversas recentes da conta pra ver se a pessoa
respondeu (`verificar_dms_respondidas`). Essa parte ainda não foi testada
contra tráfego real de conversas - o formato exato da resposta da API de
conversas pode precisar de ajuste fino quando isso acontecer de verdade
pela primeira vez.

## Limitações conhecidas / não implementado

- Resposta privada (DM) só funciona até 7 dias após o comentário, e uma
  vez só por comentário (regra da própria API, não dá pra contornar).
- Sem tela de cadastro público pra usuários - só via Django Admin
  (proposital, são só 2 pessoas usando).
- Sem encriptação do access token no banco (fica em texto plano na
  tabela `ContaInstagramConectada`, protegido só pelo login/acesso ao
  Admin) - mesmo nível de risco que o `INSTAGRAM_ACCESS_TOKEN` do
  `instagram_bot` já tinha em variável de ambiente.
