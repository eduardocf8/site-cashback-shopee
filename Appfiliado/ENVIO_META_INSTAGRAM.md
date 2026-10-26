# Análise do App da Meta: plano do envio do Instagram do Appfiliado

Objetivo: conseguir o **Acesso Avançado** das permissões do Instagram num envio só, com um vídeo que
mostra cada caso de uso funcionando de verdade, do começo ao fim. Com o Acesso Avançado, qualquer
afiliado Shopee conecta o Instagram dele no Appfiliado. Hoje só conectam as contas com função no app
(testadores).

Por que agora deve passar: a última rejeição foi "Screencast não alinhado com os detalhes do caso de
uso". O app não estava publicado, os avisos de comentário não chegavam e a resposta teve de ser
disparada à mão. Com o app publicado, o vídeo mostra tudo real: o post é publicado pelo Appfiliado,
alguém comenta, e a resposta e a DM saem sozinhas e aparecem no Instagram.

---

## 1. As permissões do envio

| Permissão | Para que o Appfiliado usa | Cenas do vídeo |
|---|---|---|
| `instagram_business_basic` | Conectar a conta e mostrar o perfil conectado (foto, @, nome); listar os posts e stories para escolher onde a automação vale | 3 e 5 |
| `instagram_business_content_publish` | Publicar no Instagram (feed e stories, na hora ou agendado) os posts criados no Estúdio Instagram, só quando o afiliado pede | 4 |
| `instagram_business_manage_comments` | Receber os comentários dos posts do afiliado (webhook `comments`) e responder publicamente | 5 e 6 |
| `instagram_business_manage_messages` | A DM ligada ao comentário, a DM para quem responde um story e a resposta a quem manda uma DM com a palavra (webhook `messages`) | 7, 8 e 9 |
| `instagram_business_manage_insights` | Não usamos. **Não peça.** | — |

Antes de montar o envio, confira em **Casos de uso › Personalizar › Permissões** o status de cada uma
("Acesso Avançado" ou "Acesso Padrão / Pronto para teste") e peça só as que ainda não têm o Avançado.
Peça todas as que faltam no **mesmo envio**, com o **mesmo vídeo**.

---

## 2. Checklist do app antes de gravar

No painel da Meta for Developers, no app:

**Configurações do app › Básico**
- [ ] **Nome de exibição: Appfiliado.** Aparece na tela de permissões do Instagram, no vídeo e para os clientes.
- [ ] **Ícone do app:** o símbolo do Appfiliado em 1024×1024 (`marketing/appfiliado/` tem a identidade).
- [ ] **E-mail de contato:** contato@appfiliado.com.br
- [ ] **URL da Política de Privacidade:** `https://appfiliado.com.br/privacidade/` (revise o texto antes, seção 9)
- [ ] **Exclusão de dados do usuário:** "URL de retorno de chamada para exclusão de dados" = `https://app.appfiliado.com.br/instagram/apagar-dados/`
- [ ] **Categoria:** Negócios e páginas (ou a mais próxima de "ferramenta para empresas")
- [ ] **Domínios do app:** `appfiliado.com.br`, `app.appfiliado.com.br` e `cash-b.com`

**Instagram › Configuração da API com login do Instagram**
- [ ] **Configurar login comercial do Instagram:**
  - URL de redirecionamento OAuth: `https://app.appfiliado.com.br/estudio/instagram/retorno/`
  - Cancelar autorização: `https://app.appfiliado.com.br/instagram/desautorizar/`
  - Exclusão de dados: `https://app.appfiliado.com.br/instagram/apagar-dados/`
- [ ] **Configurar webhooks:** URL `https://cash-b.com/instagram/automacao/webhook/`, campos `comments` e `messages` assinados.

**Geral**
- [x] **Modo do app: Publicado.**
- [x] **Verificação da empresa:** aprovada.
- [ ] **Verificação de acesso:** se o painel pedir, responda que o Appfiliado presta serviço a outras empresas (afiliados que conectam as próprias contas) e preencha o que ele pedir.
- [ ] **Testador do Instagram:** a conta que aparece conectada no vídeo (conta A, `@sejaappfiliado`), com o convite aceito (instagram.com › Configurações › Apps e sites › Convites de testador).

**No Appfiliado**
- [ ] **Conta para o revisor:** crie no admin (Contas do Appfiliado) uma conta com e-mail próprio, por exemplo `revisor.meta@appfiliado.com.br`, com:
  - cortesia: `carrosseis_premium, instagram_premium` (Estúdio Instagram Premium e Automações do Instagram Premium);
  - "testa o Estúdio Instagram" marcado.

  A senha vai só no formulário da Meta, nunca em arquivo.
- [ ] **Selos "Em teste":** se quiser, eu tiro os selos antes de gravar. Não atrapalham, mas deixam o vídeo com cara de teste.

---

## 3. Preparação da gravação

- **Duas contas do Instagram:**
  - **Conta A (`@sejaappfiliado`):** a do afiliado. É ela que conecta no Appfiliado. Antes de gravar, **desconecte** a conta no Appfiliado (botão Desconectar no cartão do Instagram), para o vídeo mostrar a conexão do zero.
  - **Conta B:** a do "seguidor" (o `@usecashb` ou o seu perfil pessoal). De preferência, uma conta que **não segue** a conta A, para mostrar a DM chegando em "Solicitações de mensagem" (o caso mais comum dos clientes).
- **Conteúdo na conta A:** um story no ar (para a cena 8). O post do vídeo é publicado pelo próprio Appfiliado na cena 4.
- **No Appfiliado:** apague as automações e publicações de teste, para o painel começar limpo. Deixe pronto no Estúdio um post de produto (do link de um produto, por exemplo a garrafa térmica), já salvo, com legenda.
- **Tela:** grave em 1920×1080, navegador com zoom de 110% a 125%, barra de endereço visível (a Meta gosta de ver o domínio), notificações do sistema desligadas e gerenciador de senhas fechado. Deixe o navegador liberado para abrir janelas (pop-ups) do `app.appfiliado.com.br`.
- **Conta B no celular:** espelhe o celular na tela do computador (scrcpy no Android, QuickTime no iPhone) e deixe o painel do Appfiliado de um lado e o celular do outro. Assim o revisor vê a ação e o resultado na mesma imagem. Se preferir, use a conta B num navegador em janela anônima, ao lado.
- **Narração em inglês:** grave a fala de cada cena e coloque **legendas em inglês** também. A interface do Appfiliado é em português, e a narração explica cada botão. A Meta aceita isso no lugar de traduzir a interface.
- **Duração:** de 10 a 13 minutos, um vídeo só cobrindo todas as permissões. Na dúvida, mostre mais.
- **Sem cortes nos momentos de prova:** da publicação até o post aparecer, e do comentário até a resposta aparecer, deixe a gravação correr, mesmo que demore alguns segundos.

---

## 4. Roteiro do vídeo, cena por cena

> Em cada cena: **o que fazer** (português) e **o que falar** (inglês). Leia devagar. O que está entre
> colchetes na fala é ação, não precisa ser lido.

### Cena 1. Apresentação (0:00 a 0:40)

**O que fazer**
1. Abra `https://appfiliado.com.br`. Role devagar pela página inicial (2 ou 3 segundos em cada parte).
2. Clique em "Privacidade" no rodapé e mostre a seção **"3. Dados do Instagram"** por uns 5 segundos.
3. Volte para a página inicial.

**O que falar**
> "Hi, this is Appfiliado. Appfiliado is a web platform for Shopee affiliates in Brazil: people who
> recommend products and earn a commission through their affiliate links. Among other tools, Appfiliado
> lets affiliates create Instagram posts and publish them to their own account, and automatically reply
> to people who comment on their posts, reply to their stories or send them a direct message, delivering
> the affiliate link they asked for. The interface is in Portuguese, so I will explain every screen and
> button in English as we go.
> [Privacy page] This is our privacy policy, at appfiliado.com.br/privacidade. Section 3 explains
> exactly which Instagram data we access, why, and how users can delete it."

### Cena 2. Entrar no Appfiliado (0:40 a 1:00)

**O que fazer**
1. Abra `https://app.appfiliado.com.br/entrar/`.
2. Entre com a conta do afiliado.
3. Mostre o painel por 2 segundos e o menu da esquerda, com **Estúdio Instagram** e **Automações**.
4. Clique em **Estúdio Instagram**.

**O que falar**
> "I'm logging in to the Appfiliado dashboard as an affiliate. In the menu there are two Instagram
> tools: 'Estúdio Instagram', Instagram Studio, to create and publish posts, and 'Automações',
> Automations, to reply automatically. I open the Instagram Studio."

### Cena 3. Conectar o Instagram: `instagram_business_basic` (1:00 a 2:20)

**O que fazer**
1. No topo do Estúdio Instagram, mostre o cartão **"Conecte o seu Instagram"** e o texto que explica o que o Appfiliado pode fazer.
2. Clique em **Conectar Instagram**. Uma janela menor do Instagram abre ao lado.
3. Na janela, entre com a **conta A** (`@sejaappfiliado`).
4. **Pare na tela de permissões** por 5 segundos, mostrando o nome **Appfiliado** e a lista do que ele pede. Passe o mouse sobre cada item.
5. Clique em **Permitir**. A janela **fecha sozinha** e a página do Appfiliado se atualiza.
6. Mostre o cartão da conta conectada: **foto, @sejaappfiliado, nome** e "Conectado e recebendo os comentários e as DMs". Passe o mouse sobre cada um.

**O que falar**
> "First, the affiliate connects their Instagram professional account. I click 'Conectar Instagram',
> which means 'Connect Instagram'. A smaller window opens with the official Instagram Business Login,
> and I log in with the account sejaappfiliado.
> Here Instagram shows that the app Appfiliado is requesting permission to access the profile, publish
> content, manage comments and manage messages. I click 'Allow'.
> The window closes by itself and Appfiliado refreshes. We use instagram_business_basic to show the
> connected account: the profile picture, the username sejaappfiliado and the account name, so the
> affiliate can confirm which account is connected. The status below says it is connected and
> receiving comments and direct messages."

### Cena 4. Publicar um post: `instagram_business_content_publish` (2:20 a 4:00)

**O que fazer**
1. Em **Seus posts**, abra o post de produto que você deixou pronto.
2. Mostre o editor por alguns segundos: passe pelos slides e mostre a legenda embaixo.
3. Clique em **Publicar no Instagram**. Mostre a janela: a conta `@sejaappfiliado`, "Vai como carrossel de N imagens no feed, com a legenda do editor" e as opções **Publicar agora** e **Agendar**.
4. Clique em **Agendar** só para mostrar o campo de dia e hora, e volte para **Publicar agora**.
5. Clique em **Publicar**. Espere a mensagem "Enviado! O post sai no seu Instagram em instantes." e a linha "Publicada", com o link **Ver no Instagram** (leva até uns 30 segundos; **não corte**).
6. Clique em **Ver no Instagram** (ou abra o perfil `@sejaappfiliado` no celular) e mostre o carrossel publicado, passando pelas imagens e pela legenda.
7. Volte ao Estúdio e clique em **Publicações**: mostre a publicação na lista "Já foram".

**O que falar**
> "This is a post the affiliate created in the Instagram Studio, with the product photo, the price and
> a caption. When it's ready, they click 'Publicar no Instagram', which means 'Publish to Instagram'.
> The dialog shows which account it goes to and how it will be published: a carousel in the feed, with
> the caption. The affiliate can publish now, 'Publicar agora', or schedule it for a date and time,
> 'Agendar'. I'll publish it now.
> We use instagram_business_content_publish to publish the post the affiliate created to their own
> connected account, and only when they ask for it. [wait] It's published. [Instagram] And here is the
> carousel on the sejaappfiliado profile, with the caption. The 'Publicações' page, Publications,
> lists everything that was published or scheduled."

### Cena 5. Criar a automação de comentário: `basic` e `manage_comments` (4:00 a 5:15)

**O que fazer**
1. No menu, clique em **Automações**. Mostre que o cartão do Instagram conectado também está aqui.
2. Clique em **Nova automação**. Nome: "Garrafa térmica (QUERO)".
3. Em "Quando responder", deixe **Comentou no post**.
4. Em "Em qual post", clique em **Um post específico**. Mostre a lista dos posts que veio do Instagram (`basic`) e clique no post publicado na cena 4. Ele aparece em destaque.
5. Palavras: `QUERO`. Mostre a dica de que maiúsculas e acentos não importam.
6. **Responder o comentário** marcado, com as três respostas prontas.
7. **Mandar DM** marcado. Texto: "Oi! Aqui está o link que você pediu:" e o link do produto.
8. Deixe **Mandar o link num botão** marcado, com o texto "Ver produto". Deixe o Sub ID como está.
9. Clique em **Salvar**. O painel volta para a lista. Mostre a automação ligada, com o `@sejaappfiliado`.

**O que falar**
> "Now the Automations page, 'Automações'. I create an automation: 'Nova automação', new automation.
> Under 'Quando responder', which means 'When to reply', I keep 'Comentou no post', 'Commented on the
> post'. Under 'Em qual post', 'Which post', I choose 'Um post específico', 'A specific post'. This list
> of the account's own posts comes from the Instagram API, using instagram_business_basic. I select the
> post we just published.
> The trigger word is 'QUERO', which means 'I want'. Uppercase and accents don't matter.
> 'Responder o comentário' means 'Reply to the comment': these are public replies, and one of them is
> picked at random so the replies don't look repetitive.
> 'Mandar DM' means 'Send a DM': this text and the affiliate link are sent privately to the person who
> commented, with a button that opens the link. I click 'Salvar', save, and the automation is on for
> the account sejaappfiliado."

### Cena 6. O comentário ao vivo: `manage_comments` (5:15 a 6:30)

**O que fazer**
1. Passe para a **conta B** (celular ou janela ao lado). Abra o post publicado na cena 4.
2. Comente **"QUERO"**. **Não corte.**
3. Em poucos segundos, atualize os comentários na conta B: a **resposta pública** da conta A aparece embaixo do comentário. Aproxime o zoom ou pare 3 segundos nela.
4. Comente também **"que lindo"**, sem a palavra. Mostre que **não** sai resposta.

**O que falar**
> "On the right side, I'm using a different Instagram account, a follower. I open the post and comment
> 'QUERO'. Appfiliado receives this comment through the comments webhook, using
> instagram_business_manage_comments. [wait] And here, a few seconds later, the account sejaappfiliado
> replied publicly to the comment, automatically, using the same permission. No manual action was
> taken.
> Now I comment 'que lindo', which means 'how nice', without the trigger word. As expected, there is no
> reply: the automation only responds to the words the affiliate configured."

### Cena 7. A DM do comentário: `manage_messages` (6:30 a 7:20)

**O que fazer**
1. Ainda na conta B, abra a **DM**. Se a conta B não segue a A, abra **Solicitações**.
2. Mostre a DM da conta A com o texto e o botão **"Ver produto"**.
3. Toque no botão e mostre que abre o produto na Shopee.

**O que falar**
> "Now let's check the follower's direct messages. [Requests] Since this account doesn't follow
> sejaappfiliado, the message is in message requests. Here is the private reply sent automatically to
> the person who commented, with the text and a 'Ver produto' button, 'See product'. [tap] The button
> opens the product. We use instagram_business_manage_messages to send this private reply, once per
> comment, as the Instagram rules require."

### Cena 8. Resposta a story: `manage_messages` (7:20 a 8:40)

**O que fazer**
1. No Appfiliado, **Nova automação**. Nome: "Story do achado". Em "Quando responder", escolha **Respondeu o story**.
2. Em "Em qual story", clique em **Um story específico (no ar)**, mostre o story que veio do Instagram e escolha.
3. Texto da DM: "Oi! O link do achado do story é este:" e o link. **Salvar**.
4. Na conta B, abra o story da conta A e responda **"🔥"** (ou qualquer texto).
5. Abra a DM da conta B e mostre a mensagem que chegou, com o botão.

**O que falar**
> "The second type of automation is a story reply. I create a new automation and choose 'Respondeu o
> story', 'Replied to the story'. I choose a specific story that is live right now, again listed through
> instagram_business_basic, and write the message. Save.
> [follower account] Now the follower replies to the story. [wait] And here is the direct message with
> the link, sent automatically through instagram_business_manage_messages, in response to the
> follower's reply."

### Cena 9. DM com palavra: `manage_messages` (8:40 a 9:40)

**O que fazer**
1. No Appfiliado, **Nova automação**. Nome: "Cupom". Em "Quando responder", escolha **Mandou DM**.
2. Palavra: `CUPOM`. Texto da DM: "O cupom de hoje é ACHADO10 😉". **Salvar**.
3. Na conta B, mande uma DM para a conta A: **"tem cupom?"**.
4. Mostre a resposta chegando na conta B.

**O que falar**
> "The third type is a direct message with a keyword: 'Mandou DM', 'Sent a DM'. The keyword is
> 'CUPOM', which means 'coupon', and the reply has the coupon code. A keyword is required here, so the
> automation never replies to every message. [follower account] The follower sends 'tem cupom?', 'is
> there a coupon?'. [wait] And the reply arrives, within the standard 24-hour messaging window started
> by the follower."

### Cena 10. Histórico (9:40 a 10:20)

**O que fazer**
1. Em **Automações**, clique em **Histórico**.
2. Mostre as linhas: a pessoa (a conta B), o que ela escreveu, se a resposta e a DM saíram, a hora.
3. Filtre por uma automação (o seletor "Automação").

**O que falar**
> "'Histórico' is the history page. The affiliate sees every person the automations replied to: who it
> was, what they wrote, and whether the public reply and the direct message were delivered. Each person
> is answered only once per automation, and each affiliate only sees their own data."

### Cena 11. Controle e exclusão (10:20 a 11:20)

**O que fazer**
1. Na lista de automações, clique em **Pausar** numa delas e mostre que fica pausada.
2. Clique em **Excluir** em outra e confirme.
3. Clique em **Desconectar** no cartão do Instagram e confirme. Mostre que a conta sai e o cartão volta a "Conecte o seu Instagram".
4. Opcional: no Instagram da conta A, mostre Configurações › Apps e sites, onde o afiliado também pode tirar o Appfiliado.

**O que falar**
> "The affiliate is always in control: 'Pausar' pauses an automation, and 'Excluir' deletes it with its
> history. 'Desconectar' disconnects the Instagram account: Appfiliado deletes the access token, stops
> the automations and the scheduled posts. Users can also remove Appfiliado in Instagram settings,
> under Apps and websites, and our deauthorization and data deletion callbacks delete the connection
> automatically."

### Cena 12. Encerramento (11:20 a 11:45)

**O que fazer**
1. Volte para a tela de Automações e encerre a gravação.

**O que falar**
> "That's the complete flow: connecting the account, publishing a post, replying to comments, sending
> private replies, and replying to story replies and keyword messages, all automatically and only for
> the content of the account the affiliate connected. Thank you."

---

## 5. Textos do formulário de cada permissão (em inglês)

> Cole em "Descreva como o seu app usa esta permissão". Em "Instruções passo a passo", use o texto da
> seção 6. Anexe o mesmo vídeo em todas e indique os minutos de cada cena.

**`instagram_business_basic`**
> Appfiliado is a web platform for Shopee affiliates (people who earn commissions by recommending
> products). Affiliates connect their own Instagram professional account through Instagram Business
> Login. We use instagram_business_basic to (1) identify and display the connected account (profile
> picture, username and name) so the affiliate can confirm which account is connected, and (2) list the
> account's own posts and live stories (media ID, thumbnail, caption, permalink) so the affiliate can
> choose which post or story an automation applies to. We don't use this data for any other purpose.
> Video: scene 3 (connection and profile) and scenes 5 and 8 (lists of posts and stories).

**`instagram_business_content_publish`**
> Affiliates design posts and stories in Appfiliado's Instagram Studio (images and caption). We use
> instagram_business_content_publish to publish what the affiliate created to their own connected
> account: a single image or a carousel in the feed, with the caption, or a sequence of stories. We
> publish only when the affiliate clicks "Publicar no Instagram" (Publish to Instagram), either right
> away or at the date and time the affiliate scheduled. We never publish anything without the
> affiliate's action, and the affiliate can cancel a scheduled post at any time. Video: scene 4.

**`instagram_business_manage_comments`**
> Affiliates create automations such as "comment the word QUERO on this post and receive the link". We
> subscribe to the comments webhook for the affiliate's own account and use
> instagram_business_manage_comments to read new comments on the affiliate's own posts (comment text,
> commenter's Instagram-scoped ID and username) and check whether they contain the trigger words the
> affiliate configured. When there is a match, we post a public reply to that comment, with a text the
> affiliate wrote. Comments without the trigger words are ignored, each person is replied to only once
> per automation, and the affiliate can pause or delete automations at any time. Comment data is shown
> only to the account owner in their history page and is never used for advertising or shared.
> Video: scenes 5 and 6.

**`instagram_business_manage_messages`**
> We use instagram_business_manage_messages for three automations that the affiliate configures for
> their own account: (1) a private reply to a person who commented a trigger word on the affiliate's
> post (once per comment, within 7 days); (2) a direct message to a person who replied to the
> affiliate's story; (3) a reply to a person who sent the affiliate a direct message containing a
> trigger word (a keyword is mandatory, so we never reply to every message). Messages are sent only in
> response to the person's action, within the standard messaging window, with the text and link the
> affiliate wrote (the link can be sent as a button). We receive the messages webhook only to detect
> these events, ignore messages sent by the account itself, and show the history only to the account
> owner. Video: scenes 7, 8 and 9.

---

## 6. Instruções para o revisor (em inglês)

> Cole em "Instruções passo a passo" e "Credenciais de teste". Preencha o e-mail e a senha da conta do
> revisor só no formulário.

> 1. Go to https://app.appfiliado.com.br/entrar/ and log in with the test account below.
> 2. In the left menu, open "Estúdio Instagram" (Instagram Studio). At the top, click "Conectar
>    Instagram" (Connect Instagram). A window with Instagram Business Login opens. Log in with an
>    Instagram professional account and click "Allow". The window closes and the connected profile
>    (picture, username, name) is shown.
> 3. Publishing: under "Seus posts" (Your posts), open a post, or create one in the "De um modelo" (From a
>    template) tab by clicking a template. Click "Publicar no Instagram" (Publish to Instagram), keep
>    "Publicar agora" (Publish now) and click "Publicar". The post appears on the connected account
>    within seconds. "Agendar" (Schedule) publishes at a chosen date and time.
> 4. Automations: in the left menu, open "Automações" (Automations) and click "Nova automação" (New
>    automation). Keep "Comentou no post" (Commented on the post), click "Um post específico" (A specific
>    post) and select a post. Type QUERO in the keywords field, keep the public replies and the DM text,
>    add any link and click "Salvar" (Save).
> 5. From another Instagram account, comment "QUERO" on that post. Within seconds, the connected account
>    replies publicly and sends a private reply with the link. Comments without the keyword are ignored.
> 6. Create another automation with "Respondeu o story" (Replied to the story) and reply to a live story
>    from another account: a DM is sent. Create one with "Mandou DM" (Sent a DM) and the keyword CUPOM,
>    then send "CUPOM" from another account: a reply is sent.
> 7. Click "Histórico" (History) to see every reply. "Pausar" pauses, "Excluir" deletes, and
>    "Desconectar" disconnects the account and deletes the access token.
>
> The interface is in Portuguese; the screencast has English narration and subtitles explaining each
> step. Test account: e-mail ______ / password ______.

---

## 7. Depois do envio

- A resposta costuma levar de alguns dias a algumas semanas. Acompanhe em **Análise do app › Solicitações**.
- **Se aprovar:**
  1. criar os produtos novos na Zouti e me mandar os links (`marketing/appfiliado/zouti-lancamento-instagram.md`);
  2. ligar `APPFILIADO_LANCAMENTO_INSTAGRAM=True` no Render (web e worker): o Estúdio e as Automações abrem para os clientes, o Carrosséis sai do menu e o site passa aos planos novos;
  3. eu tiro os selos "Em teste" e a gente anuncia.
- **Se rejeitar:** me mande o texto exato da rejeição. A gente ajusta o ponto pedido e reenvia ("Solicitar novamente") com uma nota curta explicando o que mudou.

---

## 8. O que já está pronto no Appfiliado

- Login do Instagram para empresas numa janela menor, que fecha sozinha e atualiza a página; token de 60 dias cifrado e renovado sozinho; inscrição nos webhooks.
- Conexão do Instagram no Estúdio Instagram (e em Publicações) e nas Automações.
- Publicar no feed (uma imagem ou carrossel, com legenda) e nos stories, na hora ou agendado; página de Publicações.
- Automações de comentário, resposta a story e DM com palavra; resposta pública sorteada; DM com o link num botão; um post específico ou todos; cada automação ligada ao Instagram em que foi criada.
- Histórico, pausar, excluir, desconectar.
- Endereços de "cancelar autorização" e "exclusão de dados" (`instagram_painel/README.md`).

---

## 9. Política de Privacidade

Está em `https://appfiliado.com.br/privacidade/`, com a seção do Instagram (o que lemos, para que serve, publicação dos posts) e como pedir a exclusão. **É um rascunho meu: revise o texto (e, se quiser, coloque a razão social e o CNPJ) antes de cadastrar na Meta.**
