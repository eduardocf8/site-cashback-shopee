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
  (histórico + base dos indicadores), `AutomacaoStory`/`RespostaStoryProcessada`
  (mesmo papel, pra resposta a story - ver "Automação de resposta a
  story" abaixo).
- `instagram_api.py` — chamadas à Instagram Graph API parametrizadas por
  conta (token/ID vêm do banco, não de settings globais, diferente do
  `instagram_bot`): listar comentários, responder publicamente, enviar
  resposta privada (DM), listar mídias recentes (pra escolher o post sem
  digitar ID), listar conversas (pra checar se uma DM foi respondida),
  listar stories ativos, enviar DM avulsa (`enviar_mensagem_direta`).
- `services.py` — `processar_ciclo()`: percorre as automações ativas,
  casa palavra-chave, responde/envia DM, registra; e
  `verificar_dms_respondidas()`: confere se alguém respondeu uma DM
  enviada anteriormente.
- `webhook.py` — recebe os eventos de resposta a story em tempo real
  (diferente do polling de `services.py` - ver "Automação de resposta a
  story" abaixo).
- `management/commands/automacao_instagram_worker.py` — loop infinito
  (`while True: processar_ciclo(); sleep(intervalo)`), é o Start Command
  do Background Worker no Render.
- `views.py`/`urls.py`/`templates/` — login próprio, telas de contas
  conectadas, automações de post e de story (lista + criar/editar/pausar),
  histórico (de comentários e de stories, em telas separadas).

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
de app) - isso é suficiente pra publicar conteúdo (`instagram_bot`), mas
**não é suficiente pra ler comentários de terceiros** (ver "Análise do
app" abaixo) mesmo com a conta tendo função de Testador nesse mesmo App -
achado real, documentado depois de investigar o worker rodando sem erro
nenhum mas sem nunca achar comentário nenhum (ver histórico de commits/
conversa que motivou essa seção). Pra conectar uma conta que não seja a
original (`usecashb`):

1. No painel Meta for Developers do App, ir em **Funções** e adicionar a
   nova conta do Instagram como pessoa/conta de teste - a pessoa dona da
   conta precisa **aceitar o convite** dentro do próprio app do Instagram
   (Configurações > Aplicativos e sites), não basta só adicionar pelo
   painel da Meta.
2. Gerar o access token de longa duração pra essa conta (mesmo processo
   do `instagram_bot` - ver `marketing/instagram/README.md`, "Fase 1").
3. Em `/automacao/contas/`, adicionar a conta com o ID da conta comercial
   + o token gerado.

Sem o passo 1, qualquer chamada à API com o token dessa conta nova falha
com erro de permissão.

## Análise do app (App Review) - necessária pra funcionar de verdade

**Descoberto em 2026-08-06, depois de o worker rodar sem erro nenhum mas
nunca encontrar os comentários de teste**: a permissão
`instagram_business_manage_comments` fica com o selo **"Pronto para
teste"** no painel do App enquanto ele não passa pela Análise do App -
nesse estado, `GET /{media-id}/comments` sempre retorna `"data": []`,
mesmo com token válido, escopo concedido, ID do post certo e a conta que
comentou sendo Testadora confirmada do App. O campo `comments_count` do
próprio post bate certo (prova que a Meta sabe que o comentário existe);
só a listagem em si fica vazia - sinal de que é Standard Access mesmo,
não erro de configuração daqui. Confirmado via Depurador de Token de
Acesso e testes diretos no Graph API Explorer antes de chegar nessa
conclusão.

**Alternativa gratuita considerada e descartada**: o recurso nativo do
Meta Business Suite/Instagram ("Comment to message", em Automations) faz
a mesma coisa sem precisar de revisão nenhuma, mas só permite automação
pra **conta inteira**, não pra um post específico - não serve pro caso de
uso daqui (várias automações em paralelo, uma por post/campanha, ver
"Contexto de por que foi feito assim" no topo deste arquivo).

**Testado também com autocomentário** (a própria `usecashb` comentando no
próprio post, não só terceiros) - mesmo resultado, `"data": []`. Ou seja,
**enquanto a Análise do App não é feita, a listagem de comentários não
funciona pra ninguém**, nem pro próprio dono da conta - não é uma questão
de quem comentou, é o recurso inteiro bloqueado nesse estado. Isso também
significa que não dá pra gravar o vídeo de demonstração mostrando o
fluxo completo funcionando de ponta a ponta (a etapa de detectar o
comentário automaticamente não tem como acontecer antes da aprovação) -
ver "Vídeo de demonstração" e "Texto de explicação" abaixo, ajustados pra
essa realidade.

**Status (2026-08-07)**: Verificação de Empresa **aprovada** (App
vinculado ao portfólio empresarial "Decorações Personalizadas" -
portfólio já existente, reaproveitado, não precisou criar um novo; nome
da verificação ficou "EDUARDO CARREAO FREIRE", não "cash-b", já que é a
pessoa física por trás do MEI - tudo bem, não precisa bater com o nome
fantasia). Aprovada no mesmo dia da submissão.

**Análise do App enviada** no mesmo dia, pras três permissões
(`instagram_business_basic`, `instagram_business_manage_comments`,
`instagram_business_manage_messages`) - as outras da lista padrão
(`instagram_business_content_publish`, `instagram_business_manage_insights`
e os nomes antigos tipo `instagram_manage_comments`/`instagram_basic`/
`public_profile`) foram removidas da submissão por não serem usadas de
verdade por esse app. Vídeo único (conectar conta + criar automação +
lista/histórico) reaproveitado nas três. Criado um usuário só pro
revisor da Meta testar (`revisormeta`, `is_staff=True`, senha **não**
guardada aqui de propósito - nunca commitar credencial, mesmo
descartável). Agora é esperar o resultado (a Meta pode aprovar, pedir
ajuste ou rejeitar com motivo - qualquer resultado, ver essa seção pra
retomar o contexto).

Passos pra pedir Acesso Avançado dessa permissão:

1. **Verificação de Empresa** no Meta Business Manager (documentos do
   CNPJ do cash-b).
2. Política de Privacidade publicada, cobrindo especificamente o que é
   coletado/usado nessa automação - já feito, ver
   `paginas/templates/paginas/privacidade.html`, seção "Automação de
   comentários e DM no Instagram".
3. Vídeo de tela (roteiro abaixo) + o texto de explicação (abaixo) colado
   no campo de contexto de uso da permissão.
4. Enviar pelo botão "Ir para a análise do app" (aparece ao lado da
   permissão, em Casos de uso > Permissões).

A mesma limitação provavelmente vale pra `instagram_business_manage_messages`
(enviar DM) - só foi confirmada a `manage_comments` até agora, mas vale
testar a DM também antes de assumir que só falta revisar uma permissão.

### Vídeo de demonstração (roteiro)

Só mostra o que já funciona hoje, sem depender da permissão em revisão:

1. Login em `/automacao/entrar/`.
2. Criar uma automação nova: escolher um post real, cadastrar as
   palavras-chave e os textos de resposta pública/DM.
3. Mostrar a automação criada na lista (`/automacao/`) e o histórico
   vazio (`/automacao/historico/`), deixando claro que a estrutura está
   pronta e só falta a permissão pra detectar comentários novos.

Não mostra (não tem como, é justamente o que está bloqueado): um
comentário sendo detectado e a resposta/DM chegando de verdade.

### Texto de explicação (colar no campo de contexto de uso da permissão)

> The comment-detection step currently returns empty results
> (`GET /{media-id}/comments` returns `"data": []`) for any commenter,
> including our own connected account, because this permission is still
> in Standard Access / pending review - `comments_count` on the same
> media confirms the comment exists, only the listing itself is empty.
> This is expected, and is exactly why we're requesting Advanced Access:
> once granted, this same call will return real comments from any user,
> triggering the automated public reply / private reply flow configured
> in the automation shown in the video.

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

## Automação de resposta a story (2026-09-02)

Igual à automação de comentário (post: escolhe da lista, configura,
salva), mas pra **resposta/reação a story** - já que story não tem
comentário público na API (só existe como DM), o mecanismo por baixo é
diferente (webhook, não polling - ver abaixo), mas o fluxo de tela é o
mesmo de propósito, pra não exigir aprender uma interface nova.

**Fluxo de criação** (`views.automacao_nova`, mesma URL de sempre): 1ª
etapa nova, escolher o **tipo** (Comentário em post / Resposta a story) -
cada um puxa só o que faz sentido pra ele (posts pra um, stories ativos
agora - até 24h - pro outro, via `instagram_api.listar_stories_recentes`).
Depois, mesmo padrão de sempre: escolher a conta, escolher o item da
lista, configurar e salvar (`AutomacaoStory`).

**Diferenças de post pra story:**
- Sem palavra-chave: story não tem texto de comentário pra casar contra
  - **qualquer** resposta ou reação a esse story específico dispara.
- Duas opções do que mandar por DM (`modo_resposta`):
  - **Link do produto** (`MODO_LINK_PRODUTO`): só aparece disponível pra
    stories publicados pelo `instagram_bot` como oferta (tem
    `RegistroPublicacao.link_produto_original` gravado - ver
    `marketing/instagram/README.md`) - a tela marca "✅ link do produto
    detectado" nesses, e tanto o form de criar quanto o de editar
    recusam salvar nesse modo se o story escolhido não tiver o link
    (`views._automacao_nova_story`/`automacao_story_editar`).
  - **Mensagem personalizada** (`MODO_PERSONALIZADA`): texto livre,
    igual ao `texto_dm` da automação de comentário - único jeito
    disponível pra stories fora do bot de ofertas (dica, lembrete,
    institucional, ou qualquer story de outra conta conectada, ex: a da
    esposa).
- No máximo 1 DM por pessoa por automação (`webhook._ja_respondido`) -
  sem isso, cada resposta nova ao mesmo story (uma reação, um
  "obrigada") mandaria a DM de novo.

**Por que webhook em vez de polling** (diferente do resto desse app, que
faz polling - ver "Contexto" acima): saber *qual* story foi respondido
depende do campo `reply_to.story.id` que a Meta manda no payload do
evento de mensagem - não há confirmação de que esse dado também venha
numa consulta GET posterior em `/conversations` (só a entrega em tempo
real documenta isso claramente). Como o site já é público em HTTPS
(Render), registrar um webhook não tem o custo de infra que fez o resto
desse app escolher polling.

`webhook.py` recebe os eventos (`/instagram/automacao/webhook/`, ver
`views.webhook_instagram`) - GET faz o handshake de verificação
(`hub.challenge`), POST processa cada evento, assinado com
`X-Hub-Signature-256` (calculado com `INSTAGRAM_APP_SECRET`, o mesmo App
do `instagram_bot` - conferido em `webhook.verificar_assinatura`, sem
isso qualquer um que descobrisse a URL forjava "resposta a story" e
ganhava DM de graça). Casa `story.id` com `AutomacaoStory.instagram_story_media_id`
ativa - sem automação configurada pra aquele story, ignora silenciosamente
(igual comentário sem palavra-chave). Cada tentativa (achou automação ou
não) que bateu como resposta a story fica registrada em
`RespostaStoryProcessada` (histórico na tela + admin) - **atenção**: o
formato exato do payload (`reply_to.story.id`) não foi testado contra
tráfego real ainda, mesma cautela já registrada aqui pra
`verificar_dms_respondidas`.

**Configuração manual necessária (não dá pra fazer por aqui):**

- Variável de ambiente `INSTAGRAM_WEBHOOK_VERIFY_TOKEN` no Render
  (qualquer string secreta, só usada no handshake de verificação).
- No painel do App na Meta for Developers: Products > Webhooks > assinar
  o objeto do Instagram no campo `messages`, apontando pra
  `https://cash-b.com/instagram/automacao/webhook/` (ou o domínio do
  Render) com o mesmo verify token da variável acima. Uma assinatura só
  no App cobre todas as contas conectadas (`ContaInstagramConectada`)
  que tiverem função nesse App - a Meta identifica a conta de destino
  pelo `entry[].id` de cada evento.
- Precisa da permissão `instagram_manage_messages` no token - deve já
  estar coberta pelo Standard Access existente, já que
  `enviar_resposta_privada` usa a mesma API.

## Limitações conhecidas / não implementado

- **Não funciona com comentários de terceiros até a Análise do App ser
  aprovada** (ver seção "Análise do app" acima) - hoje só reage a
  comentários de contas que sejam Testadoras do App e ao mesmo tempo o
  dono dele, o que na prática não cobre clientes de verdade.
- Resposta privada (DM) só funciona até 7 dias após o comentário, e uma
  vez só por comentário (regra da própria API, não dá pra contornar).
- Sem tela de cadastro público pra usuários - só via Django Admin
  (proposital, são só 2 pessoas usando).
- Sem encriptação do access token no banco (fica em texto plano na
  tabela `ContaInstagramConectada`, protegido só pelo login/acesso ao
  Admin) - mesmo nível de risco que o `INSTAGRAM_ACCESS_TOKEN` do
  `instagram_bot` já tinha em variável de ambiente.
