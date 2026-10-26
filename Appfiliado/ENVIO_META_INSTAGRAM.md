# Análise do App da Meta: plano do novo envio do Instagram do Appfiliado

Objetivo: conseguir o **Acesso Avançado** das duas permissões que faltam,
`instagram_business_manage_comments` e `instagram_business_content_publish`. Com elas, qualquer
afiliado Shopee conecta o Instagram no Appfiliado, publica os posts do Estúdio e usa as automações de
comentário.

## O que a Meta respondeu (suporte, 26/10/2026)

A `manage_comments` **não** foi rejeitada pela função. O motivo foi o **vídeo**:

- começou com a conta **já conectada** ("pre-authenticated login flow");
- por isso não mostrou o app **pedindo a permissão** na tela de consentimento do Instagram (OAuth),
  com o nome `instagram_business_manage_comments` visível.

O passo a passo que a Meta pediu, e onde cada item está neste plano:

| O que a Meta pediu | Onde está aqui |
|---|---|
| 1. Sair de todas as contas de teste antes de gravar; não começar de uma sessão já conectada | Seção 3 (preparação) e cenas 1.2 e 2.2 |
| 2. Gravar o fluxo completo, de deslogado a logado: o usuário achando o botão de login do Instagram e passando pelo OAuth | Cenas 1.3, 1.4, 2.3 e 2.4 |
| 3. Pausar na tela de consentimento com `instagram_business_manage_comments` legível e mostrar o usuário aceitando | Cenas 1.4 e 2.4 (pausa de 8 segundos e legenda com o nome de cada permissão) |
| 4. Mostrar a ação de ponta a ponta: resposta pública disparada pelo app num comentário real de outra pessoa, com o resultado no Instagram, e legendas dizendo qual permissão está sendo mostrada | Cenas 1.5 e 1.6 (e 2.5 para publicar) |
| 5. Incluir o login completo no vídeo de cada permissão pedida e mostrar só os fluxos dessas permissões | Um vídeo por permissão (vídeo 1 e vídeo 2), cada um começando deslogado. As duas permissões já aprovadas só aparecem dentro do mesmo fluxo, com legenda "already approved": o perfil conectado (`basic`) e a DM da mesma automação, 5 segundos no fim da cena 1.6 (`manage_messages`) |

---

## 1. As permissões

| Permissão | Status | Neste envio? |
|---|---|---|
| `instagram_business_basic` | Aprovada (com a ferramenta da cash-b) | Não, mas aparece no vídeo 1 (perfil conectado) |
| `instagram_business_manage_messages` | Aprovada (com a ferramenta da cash-b) | Não, mas aparece no vídeo 1 (DM da automação) |
| `instagram_business_manage_comments` | Rejeitada pelo vídeo | **Sim: vídeo 1** |
| `instagram_business_content_publish` | Ainda não pedida | **Sim: vídeo 2** |
| `instagram_business_manage_insights` | Não usamos | Não |

**Por que dois vídeos:** a Meta pediu o login completo "no vídeo de cada permissão" e "só os fluxos das
permissões pedidas". Com um vídeo por permissão, cada um começa deslogado, passa pelo consentimento e
mostra só aquela permissão. No formulário, cada permissão recebe o seu vídeo.

**Se quiser mandar só a `manage_comments` agora:** grave só o vídeo 1 e peça a `content_publish`
depois, com o vídeo 2. As duas juntas também funcionam, porque cada uma tem o seu vídeo.

---

## 2. Checklist antes de gravar

**No painel da Meta for Developers (app)**
- [x] **Nome de exibição: Appfiliado** e **ícone do Appfiliado** (aparecem na tela de consentimento).
- [x] **Nome do app do Instagram: "Appfiliado - IG".** A tela de consentimento usa esse nome, que é separado do nome de exibição: em Casos de uso › Configuração da API com login do Instagram, clique em **Sincronizar nome do app** depois de trocar o nome de exibição.
- [x] **URL da Política de Privacidade:** `https://appfiliado.com.br/privacidade/`
- [x] **URL dos Termos de Serviço:** `https://appfiliado.com.br/termos-de-uso/`
- [x] **URL do site:** `https://app.appfiliado.com.br/entrar/`, com as instruções da seção 7 em "Fornecer instruções de teste".
- [x] **Exclusão de dados:** `https://app.appfiliado.com.br/instagram/apagar-dados/`, no tipo **URL de retorno de chamada** (não "URL de instruções": o endereço não é uma página, a Meta recusa).
- [ ] **Login comercial do Instagram:** redirecionamento `https://app.appfiliado.com.br/estudio/instagram/retorno/`, cancelar autorização `https://app.appfiliado.com.br/instagram/desautorizar/`.
- [ ] **Webhooks:** `https://cash-b.com/instagram/automacao/webhook/`, campos `comments` e `messages` assinados.
- [x] **Modo do app: Publicado.**
- [x] **Verificação da empresa:** aprovada.
- [ ] **Testador do Instagram:** a conta A (`@sejaappfiliado`), com o convite aceito (instagram.com › Configurações › Apps e sites › Convites de testador).

**No Appfiliado**
- [x] **Conta para o revisor:** criada (`revisor.meta@appfiliado.com.br`), com a cortesia `carrosseis_premium, instagram_premium` e "testa o Estúdio Instagram" marcado. A senha vai só no formulário da Meta, nunca em arquivo.
- [x] **Selos "Em teste":** já saíram.
- [ ] **Conta A desconectada** no Appfiliado (botão Desconectar no cartão do Instagram), antes de cada vídeo.
- [ ] **Automações e publicações de teste apagadas**, para o painel começar limpo.
- [ ] **Um post de produto pronto no Estúdio** (do link de um produto, com legenda), para o vídeo 2.

---

## 3. Preparação da gravação

- **Contas do Instagram:**
  - **Conta A (`@sejaappfiliado`):** a do afiliado. É ela que conecta no Appfiliado. Tenha a senha à mão: no vídeo você vai **digitar** o usuário e a senha na janela do Instagram (a senha aparece como pontinhos).
  - **Conta B:** a de **outra pessoa**, que vai comentar (a Meta pediu "um comentário real de terceiro"). Use uma conta **sem função no app da Meta** e que não seja da empresa: o perfil pessoal de alguém da família ou de um amigo, no celular dele ou no seu. Evite o `@usecashb`, que é da empresa.
- **Começar deslogado (o ponto da rejeição):**
  1. Desconecte a conta A no Appfiliado (cartão do Instagram › Desconectar).
  2. No Instagram da conta A, vá em **Configurações › Apps e sites** e **remova o Appfiliado** se ele aparecer. Assim a tela de consentimento aparece completa, como para um usuário novo.
  3. Grave numa **janela anônima** nova (InPrivate no Edge). Ela abre sem nenhum login: nem no Instagram, nem no Appfiliado.
  4. Se o Instagram pedir código de verificação (dois fatores) durante o login, tudo bem: deixe aparecer no vídeo, faz parte do login.
- **Tela:** 1920×1080, zoom do navegador entre 110% e 125%, barra de endereço visível, notificações do sistema desligadas, gerenciador de senhas fechado (para ele não preencher a senha sozinho). Libere as janelas (pop-ups) do `app.appfiliado.com.br` na janela anônima antes de começar.
- **Conta B no celular:** espelhe o celular na tela do computador (Phone Link/Vincular ao Celular no Windows, scrcpy no Android ou QuickTime no iPhone) e deixe o painel do Appfiliado de um lado e o celular do outro.
- **Legendas (obrigatórias):** depois de gravar, edite no Clipchamp (vem no Windows) ou no CapCut e coloque dois tipos de texto:
  - **Faixa da permissão:** um texto fixo no canto de cima, enquanto a cena mostra aquela permissão. O texto exato está em cada cena ("Faixa na tela").
  - **Legendas da narração:** o texto em inglês que você fala ("O que falar"), em legenda embaixo.
- **Narração em inglês:** grave a fala de cada cena. A interface é em português, e a narração explica cada botão.
- **Sem cortes nos momentos de prova:** do clique em "Permitir" até a conta aparecer conectada, da publicação até o post aparecer, e do comentário até a resposta aparecer, deixe a gravação correr, mesmo que demore alguns segundos.
- **Duração:** vídeo 1 com uns 5 minutos, vídeo 2 com uns 4.

---

## 4. Vídeo 1: `instagram_business_manage_comments`

> Em cada cena: **o que fazer** (português), a **faixa na tela** (texto fixo em inglês, no canto de
> cima) e **o que falar** (inglês). O que está entre colchetes na fala é ação, não precisa ser lido.

### Cena 1.1. Apresentação (0:00 a 0:20)

**O que fazer**
1. Comece com a janela anônima aberta em `https://appfiliado.com.br`. Não role a página; deixe 3 segundos.

**Faixa na tela**
> Appfiliado — Instagram permission: instagram_business_manage_comments

**O que falar**
> "Hi, this is Appfiliado, a web platform for Shopee affiliates in Brazil. In this video I'll show how
> Appfiliado uses instagram_business_manage_comments: an affiliate connects their Instagram professional
> account through Instagram Business Login, creates a comment automation, and when another person
> comments the trigger word on the affiliate's post, Appfiliado replies to that comment publicly. The
> interface is in Portuguese, so I'll explain every step in English."

### Cena 1.2. Mostrar que está tudo deslogado (0:20 a 0:45)

**O que fazer**
1. Na mesma janela anônima, abra `https://www.instagram.com`. Mostre a tela de login do Instagram (ninguém logado) por 3 segundos.
2. Abra `https://app.appfiliado.com.br/entrar/`. Mostre a tela de entrada do Appfiliado.

**Faixa na tela**
> Starting logged out: no Instagram session, no Appfiliado session

**O que falar**
> "I'm starting from a fresh private window. As you can see, I'm logged out of Instagram, and I'm also
> logged out of Appfiliado. Nothing is pre-connected."

### Cena 1.3. Entrar no Appfiliado e achar o botão do Instagram (0:45 a 1:15)

**O que fazer**
1. Entre no Appfiliado com a conta do afiliado.
2. No menu da esquerda, clique em **Estúdio Instagram**.
3. Mostre o cartão **"Conecte o seu Instagram"** no topo e passe o mouse sobre o botão **Conectar Instagram** por 2 segundos.

**Faixa na tela**
> Step 1 — Instagram Business Login: the user finds the "Conectar Instagram" (Connect Instagram) button

**O que falar**
> "I log in to Appfiliado as an affiliate and open 'Estúdio Instagram', Instagram Studio. At the top
> there is the card 'Conecte o seu Instagram', Connect your Instagram. This is the Instagram Business
> Login button: 'Conectar Instagram', Connect Instagram."

### Cena 1.4. Login do Instagram e consentimento (1:15 a 2:30)

**O que fazer**
1. Clique em **Conectar Instagram**. A janela do Instagram abre ao lado, **com a tela de login** (porque está deslogado).
2. Digite o usuário e a senha da **conta A** e entre. Se pedir código de verificação, digite.
3. Na **tela de consentimento** (o Instagram mostra "Appfiliado" e a lista do que o app pede): **pare por 8 segundos**. Passe o mouse devagar sobre cada item da lista, principalmente o de **comentários**.
4. Clique em **Permitir**. A janela fecha sozinha e a página do Appfiliado se atualiza.
5. Mostre o cartão da conta conectada: foto, `@sejaappfiliado`, nome e "Conectado e recebendo os comentários e as DMs". Pare 3 segundos nele.

**Faixa na tela** (durante a pausa na tela de consentimento, ponha também uma seta ou um destaque apontando o item de comentários)
> Step 2 — OAuth consent: Appfiliado requests instagram_business_manage_comments (manage comments)
>
> Also requested: instagram_business_basic, instagram_business_content_publish, instagram_business_manage_messages

(durante o passo 5, troque para: `Profile info (picture, username, name) uses instagram_business_basic (already approved)`)

**O que falar**
> "I click 'Conectar Instagram'. The official Instagram Business Login opens in a new window. Since I'm
> logged out, Instagram asks me to log in, so I type the username and password of the professional
> account sejaappfiliado.
> [consent screen] This is the consent screen. Instagram shows that the app Appfiliado is requesting
> permission to manage the comments on my account. This is instagram_business_manage_comments. The
> same screen also lists access to the profile, publishing content and messages. I grant access by
> clicking 'Allow'.
> [back to Appfiliado] The window closes and Appfiliado now shows the connected account: profile
> picture, username sejaappfiliado and name. This profile information comes from
> instagram_business_basic, which is already approved."

### Cena 1.5. Criar a automação de comentário (2:30 a 3:30)

**O que fazer**
1. No menu, clique em **Automações Instagram** e em **Nova automação**.
2. Nome: "Garrafa térmica (QUERO)". Em "Quando responder", deixe **Comentou no post**.
3. Em "Em qual post", clique em **Um post específico** e escolha um post da conta A na lista.
4. Palavras: `QUERO`.
5. **Responder o comentário** marcado, com as três respostas prontas. Passe o mouse sobre elas.
6. Deixe **Mandar DM** como está (texto e link do produto).
7. Clique em **Salvar**. Mostre a automação ligada na lista, com o `@sejaappfiliado`.

**Faixa na tela**
> Demonstrating instagram_business_manage_comments — setting up the public reply to comments

**O que falar**
> "Now I create a comment automation: 'Automações Instagram', then 'Nova automação', new automation.
> 'Comentou no post' means 'Commented on the post'. I choose a specific post, 'Um post específico'.
> The trigger word is 'QUERO', which means 'I want'.
> 'Responder o comentário' means 'Reply to the comment'. These are the public replies Appfiliado will
> post under the comment, using instagram_business_manage_comments. One of them is picked at random.
> I click 'Salvar', save. The automation is on."

### Cena 1.6. O comentário real e a resposta pública (3:30 a 4:40)

**O que fazer**
1. Mostre a **conta B** (o celular espelhado). Abra o post escolhido na cena 1.5.
2. Comente **"QUERO"**. **Não corte.**
3. Em poucos segundos, atualize os comentários: a **resposta pública** da conta A aparece embaixo do comentário da conta B. Pare 3 segundos nela (aproxime o zoom, se der).
4. Comente também **"que lindo"**, sem a palavra. Espere uns 10 segundos e mostre que **não** sai resposta.
5. **Obrigatório, em 5 segundos:** na conta B, abra as mensagens e mostre a DM que chegou da conta A, com o texto e o link. É da `manage_messages`, já aprovada, e sai da mesma automação.

**Faixa na tela**
> Demonstrating instagram_business_manage_comments — a real comment from another person triggers the public reply

(durante o passo 5, troque para: `Private reply uses instagram_business_manage_messages (already approved)`)

**O que falar**
> "This is a different person's Instagram account, on a phone. I open the affiliate's post and comment
> 'QUERO'. Appfiliado receives this comment through the comments webhook, using
> instagram_business_manage_comments. [wait] And here, a few seconds later, the account sejaappfiliado
> replied publicly to the comment, automatically. This public reply was posted by Appfiliado with
> instagram_business_manage_comments, and it's visible on Instagram.
> Now I comment 'que lindo', which means 'how nice', without the trigger word. As expected, there is no
> reply: the automation only responds to the words the affiliate configured.
> [DM] The same automation also sent this private reply to the person who commented, here in their
> Instagram messages. That uses instagram_business_manage_messages, which is already approved."

### Cena 1.7. Histórico dos comentários (4:40 a 5:10)

**O que fazer**
1. Volte ao Appfiliado. Em **Automações Instagram**, clique em **Histórico**.
2. Mostre a linha da conta B: o nome de usuário, o que ela comentou e o ✓ da resposta no comentário.

**Faixa na tela**
> instagram_business_manage_comments — comment data shown only to the account owner

**O que falar**
> "In 'Histórico', History, the affiliate sees who commented, what they wrote, and whether the public
> reply was delivered. Comment data is shown only to the account owner. That's how Appfiliado uses
> instagram_business_manage_comments. Thank you."

---

## 5. Vídeo 2: `instagram_business_content_publish`

> Antes de gravar: **desconecte** a conta A no Appfiliado, **remova** o Appfiliado em Configurações ›
> Apps e sites do Instagram, **feche** a janela anônima do vídeo 1 e abra **outra** janela anônima.

### Cena 2.1. Apresentação (0:00 a 0:20)

**O que fazer**
1. Janela anônima nova aberta em `https://appfiliado.com.br`. Deixe 3 segundos.

**Faixa na tela**
> Appfiliado — Instagram permission: instagram_business_content_publish

**O que falar**
> "Hi, this is Appfiliado, a web platform for Shopee affiliates in Brazil. In this video I'll show how
> Appfiliado uses instagram_business_content_publish: an affiliate creates a post in Appfiliado's
> Instagram Studio and publishes it to their own Instagram professional account, only when they ask
> for it. The interface is in Portuguese, so I'll explain every step in English."

### Cena 2.2. Mostrar que está tudo deslogado (0:20 a 0:45)

**O que fazer**
1. Abra `https://www.instagram.com` e mostre a tela de login (ninguém logado).
2. Abra `https://app.appfiliado.com.br/entrar/` e mostre a tela de entrada.

**Faixa na tela**
> Starting logged out: no Instagram session, no Appfiliado session

**O que falar**
> "I'm starting from a fresh private window, logged out of Instagram and logged out of Appfiliado.
> Nothing is pre-connected."

### Cena 2.3. Entrar no Appfiliado e achar o botão do Instagram (0:45 a 1:10)

**O que fazer**
1. Entre no Appfiliado com a conta do afiliado.
2. Clique em **Estúdio Instagram** e passe o mouse sobre **Conectar Instagram**.

**Faixa na tela**
> Step 1 — Instagram Business Login: the user finds the "Conectar Instagram" (Connect Instagram) button

**O que falar**
> "I log in to Appfiliado and open 'Estúdio Instagram', Instagram Studio, where affiliates create their
> posts. This is the Instagram Business Login button: 'Conectar Instagram', Connect Instagram."

### Cena 2.4. Login do Instagram e consentimento (1:10 a 2:20)

**O que fazer**
1. Clique em **Conectar Instagram**. A janela do Instagram abre com a tela de login.
2. Digite o usuário e a senha da **conta A** e entre (e o código, se pedir).
3. Na **tela de consentimento**, **pare por 8 segundos** e passe o mouse sobre cada item, principalmente o de **publicar conteúdo**.
4. Clique em **Permitir**. A janela fecha e a conta aparece conectada no topo do Estúdio.

**Faixa na tela** (com uma seta ou destaque no item de publicar conteúdo)
> Step 2 — OAuth consent: Appfiliado requests instagram_business_content_publish (publish content)
>
> Also requested: instagram_business_basic, instagram_business_manage_comments, instagram_business_manage_messages

**O que falar**
> "I click 'Conectar Instagram'. The Instagram Business Login opens and, since I'm logged out, I type
> the username and password of the professional account sejaappfiliado.
> [consent screen] On the consent screen, Instagram shows that Appfiliado is requesting permission to
> publish content on my account. This is instagram_business_content_publish. I grant access by clicking
> 'Allow'. [back] The window closes and the connected account sejaappfiliado is shown."

### Cena 2.5. Publicar o post e ver no Instagram (2:20 a 3:50)

**O que fazer**
1. Em **Seus posts**, abra o post de produto que você deixou pronto. Passe pelos slides e mostre a legenda.
2. Clique em **Publicar no Instagram**. Mostre a janela: a conta `@sejaappfiliado` e "Vai como carrossel de N imagens no feed, com a legenda do editor".
3. Clique em **Agendar** só para mostrar o campo de dia e hora. Volte para **Publicar agora**.
4. Clique em **Publicar**. Espere "Enviado! O post sai no seu Instagram em instantes." e a linha virar **Publicada**, com **Ver no Instagram** (até uns 30 segundos; **não corte**).
5. Clique em **Ver no Instagram** (ou abra o perfil no celular) e mostre o carrossel publicado, com as imagens e a legenda.

**Faixa na tela**
> Demonstrating instagram_business_content_publish — the affiliate publishes their post; result visible on Instagram

**O que falar**
> "This is a post the affiliate created in the Instagram Studio, with the product photo, the price and
> a caption. The affiliate clicks 'Publicar no Instagram', Publish to Instagram. The dialog shows the
> account and how it will be published: a carousel in the feed, with this caption. They can publish
> now, 'Publicar agora', or schedule it, 'Agendar'. I'll publish it now.
> Appfiliado uses instagram_business_content_publish to publish the post the affiliate created to their
> own account, and only when they ask for it. [wait] It's published. [Instagram] And here is the
> carousel on the sejaappfiliado profile, with the caption."

### Cena 2.6. Publicações (3:50 a 4:10)

**O que fazer**
1. Volte ao Estúdio e clique em **Publicações**. Mostre o post na lista "Já foram", com "Ver no Instagram".

**Faixa na tela**
> instagram_business_content_publish — the affiliate sees everything published or scheduled

**O que falar**
> "The 'Publicações' page, Publications, lists everything the affiliate published or scheduled, and a
> scheduled post can be canceled at any time. That's how Appfiliado uses
> instagram_business_content_publish. Thank you."

---

## 6. Textos do formulário de cada permissão (em inglês)

> Em "Descreva como o seu app usa esta permissão". Anexe o **vídeo 1** na `manage_comments` e o
> **vídeo 2** na `content_publish`, e indique os minutos das cenas.

**`instagram_business_manage_comments`** (vídeo 1)
> Appfiliado is a web platform for Shopee affiliates (people who earn commissions by recommending
> products). Affiliates connect their own Instagram professional account through Instagram Business
> Login and create automations such as "comment the word QUERO on this post and get the link". We
> subscribe to the comments webhook for the affiliate's own account and use
> instagram_business_manage_comments to read new comments on the affiliate's own posts (comment text,
> commenter's Instagram-scoped ID and username) and check whether they contain the trigger words the
> affiliate configured. When there is a match, we post a public reply to that comment, with a text the
> affiliate wrote. Comments without the trigger words are ignored, each person is replied to only once
> per automation, and the affiliate can pause or delete automations at any time. Comment data is shown
> only to the account owner in their history page and is never used for advertising or shared.
> Screencast: starts logged out; full Instagram Business Login and consent screen requesting
> instagram_business_manage_comments (1:15–2:30); automation setup (2:30–3:30); a real comment from
> another person and the public reply visible on Instagram (3:30–4:40); history (4:40–5:10).

**`instagram_business_content_publish`** (vídeo 2)
> Affiliates design posts and stories in Appfiliado's Instagram Studio (images and caption). We use
> instagram_business_content_publish to publish what the affiliate created to their own connected
> account: a single image or a carousel in the feed, with the caption, or a sequence of stories. We
> publish only when the affiliate clicks "Publicar no Instagram" (Publish to Instagram), either right
> away or at the date and time the affiliate scheduled. We never publish anything without the
> affiliate's action, and the affiliate can cancel a scheduled post at any time.
> Screencast: starts logged out; full Instagram Business Login and consent screen requesting
> instagram_business_content_publish (1:10–2:20); publishing a carousel and the result on Instagram
> (2:20–3:50); publications page (3:50–4:10).

---

## 7. Instruções para o revisor (em inglês)

> Cole em "Instruções passo a passo" e "Credenciais de teste". Preencha o e-mail e a senha da conta do
> revisor só no formulário.

> 1. Go to https://app.appfiliado.com.br/entrar/ and log in with the test account below.
> 2. In the left menu, open "Estúdio Instagram" (Instagram Studio). At the top, click "Conectar
>    Instagram" (Connect Instagram). Instagram Business Login opens in a new window. Log in with an
>    Instagram professional account and grant access on the consent screen. The window closes and the
>    connected profile (picture, username, name) is shown.
> 3. instagram_business_manage_comments: in the left menu, open "Automações Instagram" (Instagram
>    Automations) and click "Nova automação" (New automation). Keep "Comentou no post" (Commented on the
>    post), click "Um post específico" (A specific post) and select a post. Type QUERO in the keywords
>    field, keep the public replies and click "Salvar" (Save). From another Instagram account, comment
>    "QUERO" on that post: within seconds, the connected account replies publicly to the comment.
>    Comments without the keyword are ignored. "Histórico" (History) lists the comments that were
>    answered.
> 4. instagram_business_content_publish: in "Estúdio Instagram", open a post under "Seus posts" (Your
>    posts), or create one in the "De um modelo" (From a template) tab by clicking a template. Click
>    "Publicar no Instagram" (Publish to Instagram), keep "Publicar agora" (Publish now) and click
>    "Publicar". The post appears on the connected account within seconds. "Agendar" (Schedule)
>    publishes at a chosen date and time; "Publicações" (Publications) lists everything published.
>
> The interface is in Portuguese; the screencasts have English narration and on-screen captions
> naming the permission shown in each step. Test account: e-mail ______ / password ______.

---

## 8. Nota para o revisor ao reenviar (em inglês)

> Cole no campo de observações do envio (ou na resposta ao suporte).

> Following Meta Direct Support's guidance on our previous submission, the new screencasts start from
> a logged-out state (no Instagram or Appfiliado session), show the full Instagram Business Login and
> the OAuth consent screen with the requested permission clearly visible and labeled, and then show the
> end-to-end flow with on-screen captions naming the permission. There is one screencast per requested
> permission: instagram_business_manage_comments (a real comment from another person triggers a public
> reply, visible on Instagram) and instagram_business_content_publish (a post created in Appfiliado is
> published and visible on Instagram).
>
> This app was first used as an internal tool (cash-b.com/automacao), which is how
> instagram_business_basic and instagram_business_manage_messages were approved. It is now Appfiliado,
> a web platform for Shopee affiliates, and the screencasts show the current product. Video 1 also shows,
> briefly and labeled as already approved, the connected profile (instagram_business_basic) and the
> private reply sent by the same automation (instagram_business_manage_messages), so the whole use of
> the app is visible in one place.

---

## 9. Depois do envio

- A resposta costuma levar de alguns dias a algumas semanas. Acompanhe em **Análise do app › Solicitações**.
- **Se aprovar:**
  1. criar os produtos novos na Zouti e me mandar os links (`marketing/appfiliado/zouti-lancamento-instagram.md`);
  2. ligar `APPFILIADO_LANCAMENTO_INSTAGRAM=True` no Render (web e worker): o Estúdio e as Automações abrem para os clientes, o Carrosséis sai do menu e o site passa aos planos novos;
  3. a gente anuncia.
- **Se rejeitar:** me mande o texto exato da rejeição. A gente ajusta o ponto pedido e reenvia ("Solicitar novamente") com uma nota curta explicando o que mudou.

---

## 10. O que já está pronto no Appfiliado

- Login do Instagram para empresas numa janela menor, que fecha sozinha e atualiza a página; token de 60 dias cifrado e renovado sozinho; inscrição nos webhooks.
- Conexão do Instagram no Estúdio Instagram (e em Publicações) e nas Automações Instagram.
- Publicar no feed (uma imagem ou carrossel, com legenda) e nos stories, na hora ou agendado; página de Publicações.
- Automações de comentário, resposta a story e DM com palavra; resposta pública sorteada; DM com o link num botão; um post específico ou todos; cada automação ligada ao Instagram em que foi criada.
- Histórico, pausar, excluir, desconectar.
- Endereços de "cancelar autorização" e "exclusão de dados" (`instagram_painel/README.md`).

---

## 11. Política de Privacidade

Está em `https://appfiliado.com.br/privacidade/`, com a seção do Instagram (o que lemos, para que serve, publicação dos posts) e como pedir a exclusão. **É um rascunho meu: revise o texto (e, se quiser, coloque a razão social e o CNPJ) antes de cadastrar na Meta.**
