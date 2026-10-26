# Análise do App da Meta: plano do envio do Instagram do Appfiliado

Objetivo: conseguir o **Acesso Avançado** das permissões do Instagram num envio só, com um vídeo que
mostra cada caso de uso funcionando de verdade, do começo ao fim. Com o Acesso Avançado, qualquer
afiliado Shopee conecta o Instagram dele no Appfiliado. Hoje só conectam as contas com função no app.

Por que agora deve passar: a última rejeição foi "Screencast não alinhado com os detalhes do caso de
uso". O app não estava publicado, os avisos de comentário não chegavam e a resposta teve de ser
disparada à mão. Com o app publicado, o vídeo mostra a automação real: alguém comenta, a resposta
e a DM saem sozinhas e aparecem no Instagram.

---

## 1. As permissões do envio

| Permissão | Para que o Appfiliado usa | Entra no envio? |
|---|---|---|
| `instagram_business_basic` | Conectar a conta e mostrar o perfil conectado (foto, @, nome); listar os posts e stories para escolher onde a automação vale | **Sim**, se não estiver com Acesso Avançado. Para servir contas de clientes, a Meta exige o Avançado também nesta. |
| `instagram_business_manage_comments` | Receber os comentários dos posts do afiliado (webhook `comments`) e responder publicamente | **Sim** (é a que falta) |
| `instagram_business_manage_messages` | A DM ligada ao comentário, a DM para quem responde um story e a resposta a quem manda uma DM com a palavra (webhook `messages`) | **Sim**, se não estiver com Acesso Avançado |
| `instagram_business_content_publish` | Publicar no Instagram os posts criados no Estúdio Instagram | **Só depois que a função "Publicar no Instagram" existir** (ver seção 9) |
| `instagram_business_manage_insights` | Não usamos | **Não** |

Antes de montar o envio, confira em **Casos de uso › Personalizar › Permissões** qual é o status de
cada uma ("Acesso Avançado" ou "Acesso Padrão / Pronto para teste") e peça só as que ainda não têm o
Avançado. Peça todas as que faltam no **mesmo envio**, com o **mesmo vídeo**.

---

## 2. Checklist do app antes de gravar

No painel da Meta for Developers, no app:

**Configurações do app › Básico**
- [ ] **Nome de exibição: Appfiliado.** É o nome que aparece na tela de permissões do Instagram, no vídeo e para os clientes. Se ainda estiver como cash-b, troque.
- [ ] **Ícone do app:** o símbolo do Appfiliado em 1024×1024 (`marketing/appfiliado/` tem a identidade).
- [ ] **E-mail de contato:** contato@appfiliado.com.br
- [ ] **URL da Política de Privacidade:** `https://appfiliado.com.br/privacidade/` (página nova; revise o texto antes, seção 10)
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
- [ ] **Modo do app: Publicado** (feito).
- [ ] **Verificação da empresa:** aprovada (feito).
- [ ] **Verificação de acesso:** se o painel pedir, responda que o Appfiliado presta serviço a outras empresas (afiliados que conectam as próprias contas) e preencha o que ele pedir.
- [ ] **Testadores do Instagram:** a conta que aparece conectada no vídeo (conta A, `@usecashb`) e a conta que vai comentar e mandar DMs (conta B). As duas com o convite aceito no Instagram (Configurações › Apps e sites › Convites de testador).

**No Appfiliado**
- [ ] **Conta para o revisor:** crie uma conta no admin (Contas do Appfiliado) com e-mail próprio, por exemplo `revisor.meta@appfiliado.com.br`, cortesia do plano Premium do Estúdio (`carrosseis_premium`) e "testa o Estúdio Instagram" marcado. A senha vai só no formulário da Meta, nunca em arquivo.
- [ ] **Selos "Em teste":** combine comigo se tiramos os selos antes de gravar. Eles não atrapalham, mas deixam o vídeo com cara de teste.
- [ ] **Decisão sobre separar a automação em outro módulo** (seção 9): os nomes do menu aparecem no vídeo.

---

## 3. Preparação da gravação

- **Duas contas do Instagram:**
  - **Conta A (`@usecashb`):** a do afiliado. É ela que conecta no Appfiliado. Antes de gravar, **desconecte** a conta no Appfiliado (Automações › Desconectar), para o vídeo mostrar a conexão do zero.
  - **Conta B:** a do "seguidor". De preferência, uma conta que **não segue** a conta A, para mostrar a DM chegando em "Solicitações de mensagem" (é o caso mais comum dos clientes).
- **Conteúdo na conta A:** pelo menos um post publicado (o do vídeo) e um story no ar. Se a função de publicar já existir, o post é publicado pelo próprio Appfiliado durante o vídeo.
- **Apague** automações e históricos de teste antigos, para o painel começar limpo.
- **Tela:** grave em 1920×1080, navegador com zoom de 110% a 125%, barra de endereço visível (a Meta gosta de ver o domínio), notificações do sistema desligadas e gerenciador de senhas fechado.
- **Conta B no celular:** espelhe o celular na tela do computador (scrcpy no Android, QuickTime no iPhone) e deixe o painel do Appfiliado de um lado e o celular do outro. Assim o revisor vê a ação e o resultado na mesma imagem. Se preferir, use a conta B num navegador em janela anônima, ao lado.
- **Narração em inglês:** grave a narração (seção 5) e coloque **legendas em inglês** também. A interface do Appfiliado é em português, e a narração explica cada botão. A Meta aceita isso no lugar de traduzir a interface.
- **Duração:** de 8 a 12 minutos, um vídeo só cobrindo todas as permissões. Na dúvida, mostre mais.
- **Sem cortes nos momentos de prova:** do comentário até a resposta aparecer, deixe a gravação correr, mesmo que demore alguns segundos.

---

## 4. Roteiro detalhado em português (o que fazer em cada cena)

> A coluna da narração em inglês de cada cena está na seção 5, com o mesmo número.

### Cena 1. Apresentação (0:00 a 0:40)
1. Abra `https://appfiliado.com.br`. Role devagar pela página inicial (2 ou 3 segundos em cada parte).
2. Clique em "Privacidade" no rodapé e mostre a seção **"3. Dados do Instagram"** por uns 5 segundos.
3. Volte para a página inicial.

### Cena 2. Entrar no Appfiliado (0:40 a 1:00)
1. Abra `https://app.appfiliado.com.br/entrar/`.
2. Entre com a conta do afiliado (a mesma que você vai informar ao revisor).
3. Mostre o painel por 2 segundos e clique em **Estúdio Instagram** no menu.

### Cena 3. Conectar o Instagram: `instagram_business_basic` (1:00 a 2:30)
1. Clique em **Automações**. Mostre o cartão "Conecte o seu Instagram" e o texto que explica o que o Appfiliado pode fazer.
2. Clique em **Conectar Instagram**. Uma janela menor do Instagram abre ao lado.
3. Na janela, entre com a **conta A** (`@usecashb`).
4. **Pare na tela de permissões** por 5 segundos, mostrando o nome **Appfiliado** e a lista do que ele pede. Passe o mouse sobre cada item.
5. Clique em **Permitir**. A janela fecha sozinha e o painel atualiza.
6. Mostre o cartão da conta conectada: **foto, @usecashb, nome** e "Conectado e recebendo os comentários e as DMs". Passe o mouse sobre cada um.

### Cena 4. Publicar um post: `instagram_business_content_publish` (2:30 a 4:00)
*Só se a função de publicar já existir. Senão, pule esta cena e não peça essa permissão.*
1. Volte para **Estúdio Instagram** e crie um post ("De um modelo" › "Achado do dia").
2. Mostre o editor: troque o título, passe pelos slides.
3. Clique em **Publicar no Instagram**, escolha publicar agora e confirme.
4. Mostre a confirmação no Appfiliado.
5. No celular (ou na janela da conta A), abra o perfil `@usecashb` e mostre o post publicado.

### Cena 5. Criar a automação de comentário: `basic` e `manage_comments` (4:00 a 5:00)
1. Em **Automações**, clique em **Nova automação**.
2. Nome: "Garrafa térmica (QUERO)".
3. Em "Quando responder", deixe **Comentou no post**.
4. Clique em **Escolher no Instagram**. Mostre que a lista dos posts veio da conta (`basic`) e clique no post da cena 4 (ou num post já publicado).
5. Palavras: `QUERO`. Mostre a dica de que maiúsculas e acentos não importam.
6. **Responder o comentário** marcado, com as três respostas prontas.
7. **Mandar DM** marcado. Texto: "Oi! Aqui está o link que você pediu:" e um link de produto da Shopee.
8. Clique em **Salvar**. O painel volta para a lista. Mostre a automação ligada.

### Cena 6. O comentário ao vivo: `manage_comments` (5:00 a 6:30)
1. Passe para a **conta B** (celular ou janela ao lado). Abra o post escolhido.
2. Comente **"QUERO"**. **Não corte.**
3. Em poucos segundos, atualize os comentários na conta B: a **resposta pública** da conta A aparece embaixo do comentário. Aproxime o zoom ou pare 3 segundos nela.
4. Comente também **"que lindo"**, sem a palavra. Mostre que **não** sai resposta (a automação só reage à palavra configurada).

### Cena 7. A DM do comentário: `manage_messages` (6:30 a 7:15)
1. Ainda na conta B, abra o **Direct**. Se a conta B não segue a A, abra **Solicitações**.
2. Mostre a DM da conta A com o texto e o link. Toque no link e mostre que abre o produto.

### Cena 8. Resposta a story: `manage_messages` (7:15 a 8:30)
1. No Appfiliado, **Nova automação**. Nome: "Story do achado". Em "Quando responder", escolha **Respondeu o story**.
2. Clique em **Escolher no Instagram**, mostre o story no ar e escolha. Texto da DM: "Oi! O link do achado do story é este:" e o link. **Salvar**.
3. Na conta B, abra o story da conta A e responda **"🔥"** (ou qualquer texto).
4. Abra o Direct da conta B e mostre a DM que chegou.

### Cena 9. DM com palavra: `manage_messages` (8:30 a 9:30)
1. No Appfiliado, **Nova automação**. Nome: "Cupom". Em "Quando responder", escolha **Mandou DM**.
2. Palavra: `CUPOM`. Texto da DM: "O cupom de hoje é ACHADO10 😉". **Salvar**.
3. Na conta B, mande uma DM para a conta A: **"tem cupom?"**.
4. Mostre a resposta chegando na conta B.

### Cena 10. Histórico (9:30 a 10:15)
1. Em **Automações**, clique em **Histórico**.
2. Mostre as linhas: a pessoa (`@contaB`), o que ela escreveu, se a resposta e a DM saíram, a hora.
3. Filtre por uma automação (o seletor "Automação").

### Cena 11. Controle e exclusão (10:15 a 11:15)
1. Na lista de automações, clique em **Pausar** numa delas e mostre que fica pausada.
2. Clique em **Excluir** em outra e confirme.
3. Clique em **Desconectar** no cartão da conta e confirme. Mostre que a conta sai e as automações param.
4. Opcional: no Instagram da conta A, mostre Configurações › Apps e sites, onde o afiliado também pode tirar o Appfiliado.

### Cena 12. Encerramento (11:15 a 11:40)
1. Volte para a tela de automações e encerre a gravação.

---

## 5. Narração em inglês (o que falar)

> Leia devagar. Os textos entre colchetes são ações, não precisam ser lidos.

**Scene 1. Introduction**
"Hi, this is Appfiliado. Appfiliado is a web platform for Shopee affiliates in Brazil: people who
recommend products and earn a commission through their affiliate links. Among other tools, Appfiliado
lets affiliates create Instagram posts and automatically reply to people who comment on their posts,
reply to their stories or send them a direct message, delivering the affiliate link they asked for.
The interface is in Portuguese, so I will explain every screen and button in English as we go.
[Privacy page] This is our privacy policy, at appfiliado.com.br/privacidade. Section 3 explains
exactly which Instagram data we access, why, and how users can delete it."

**Scene 2. Login**
"I'm logging in to the Appfiliado dashboard as an affiliate. In the menu, I open 'Estúdio Instagram',
which means Instagram Studio."

**Scene 3. Connect Instagram (instagram_business_basic)**
"This is the Automations page, 'Automações'. The affiliate first needs to connect their Instagram
professional account. I click 'Conectar Instagram', which means 'Connect Instagram'.
A smaller window opens with the official Instagram Business Login. I log in with the Instagram
professional account usecashb.
Here Instagram shows that the app Appfiliado is requesting permission to access the profile,
manage comments, manage messages and publish content. I click 'Allow'.
The window closes and we are back in Appfiliado. We use instagram_business_basic to show the
connected account: the profile picture, the username usecashb and the account name. This confirms to
the affiliate which account is connected. Below, the status says the account is connected and
receiving comments and direct messages."

**Scene 4. Publish a post (instagram_business_content_publish)**
"Now the Instagram Studio. The affiliate creates a post from a template, 'De um modelo', and edits the
texts in the editor. When it's ready, they click 'Publicar no Instagram', which means 'Publish to
Instagram'. We use instagram_business_content_publish to publish the post the affiliate created, only
when they ask for it. [Instagram app] And here is the post, published on the usecashb profile."

**Scene 5. Create a comment automation (instagram_business_basic, instagram_business_manage_comments)**
"Now I create an automation: 'Nova automação', new automation. I name it, and under 'Quando
responder', which means 'When to reply', I keep 'Comentou no post', 'Commented on the post'.
I click 'Escolher no Instagram', 'Choose on Instagram'. This list of the account's own posts comes from
the Instagram API, using instagram_business_basic. I select the post.
The trigger word is 'QUERO', which means 'I want'. Uppercase and accents don't matter.
'Responder o comentário' means 'Reply to the comment': these are public replies, and one of them is
picked at random so the replies don't look repetitive.
'Mandar DM' means 'Send a DM': this text and the affiliate link are sent privately to the person who
commented. I click 'Salvar', save, and the automation is on."

**Scene 6. Live comment (instagram_business_manage_comments)**
"On the right side, I'm using a different Instagram account, a follower. I open the post and comment
'QUERO'. Appfiliado receives this comment through the comments webhook, using
instagram_business_manage_comments. [wait] And here, a few seconds later, the account usecashb replied
publicly to the comment, automatically, using the same permission. No manual action was taken.
Now I comment 'que lindo', which means 'how nice', without the trigger word. As expected, there is no
reply: the automation only responds to the words the affiliate configured."

**Scene 7. Private reply (instagram_business_manage_messages)**
"Now let's check the follower's direct messages. [Requests] Since this account doesn't follow
usecashb, the message is in message requests. Here is the private reply sent automatically to the
person who commented, with the text and the affiliate link. We use instagram_business_manage_messages
to send this private reply, once per comment, as the Instagram rules require."

**Scene 8. Story reply (instagram_business_manage_messages)**
"The second type of automation is a story reply. I create a new automation and choose 'Respondeu o
story', 'Replied to the story'. I choose the story that is live right now and write the message.
Save. [follower account] Now the follower replies to the story. [wait] And here is the direct message
with the link, sent automatically through instagram_business_manage_messages."

**Scene 9. Keyword DM (instagram_business_manage_messages)**
"The third type is a direct message with a keyword: 'Mandou DM', 'Sent a DM'. The keyword is 'CUPOM',
which means 'coupon', and the reply has the coupon code. A keyword is required here, so the automation
never replies to every message. [follower account] The follower sends 'tem cupom?', 'is there a
coupon?'. [wait] And the reply arrives within the standard 24-hour messaging window, started by the
follower."

**Scene 10. History**
"'Histórico' is the history page. The affiliate sees every person the automations replied to: who it
was, what they wrote, and whether the public reply and the direct message were delivered. Each person
is answered only once per automation, and each affiliate only sees their own data."

**Scene 11. Control and data deletion**
"The affiliate is always in control: 'Pausar' pauses an automation, 'Excluir' deletes it with its
history. 'Desconectar' disconnects the Instagram account: Appfiliado deletes the access token and stops
all automations. Users can also remove Appfiliado in Instagram settings, under Apps and websites, and
our deauthorization and data deletion callbacks delete the connection automatically."

**Scene 12. Closing**
"That's the complete flow: connecting the account, publishing, replying to comments, sending private
replies, replying to story replies and keyword messages, all automatically and only for the content of
the account the affiliate connected. Thank you."

---

## 6. Textos do formulário de cada permissão (em inglês)

> Cole em "Descreva como o seu app usa esta permissão". Em "Instruções passo a passo", use o texto da
> seção 7. Anexe o mesmo vídeo em todas e indique os minutos de cada cena.

**`instagram_business_basic`**
> Appfiliado is a web platform for Shopee affiliates (people who earn commissions by recommending
> products). Affiliates connect their own Instagram professional account through Instagram Business
> Login. We use instagram_business_basic to (1) identify and display the connected account (profile
> picture, username and name) so the affiliate can confirm which account is connected, and (2) list the
> account's own posts and live stories (media ID, thumbnail, caption, permalink) so the affiliate can
> choose which post or story an automation applies to. We don't use this data for any other purpose.
> Video: scene 3 (connection and profile) and scene 5 (post list).

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
> affiliate wrote. We receive the messages webhook only to detect these events, ignore messages sent by
> the account itself, and show the history only to the account owner. Video: scenes 7, 8 and 9.

**`instagram_business_content_publish`** (só quando a função existir)
> Affiliates design posts in Appfiliado's Instagram Studio (images and caption). We use
> instagram_business_content_publish to publish the post the affiliate created to their own connected
> account, only when the affiliate clicks "Publish to Instagram" (or schedules it for a date the
> affiliate chose). We never publish anything without the affiliate's action. Video: scene 4.

---

## 7. Instruções para o revisor (em inglês)

> Cole em "Instruções passo a passo" e "Credenciais de teste". Preencha e-mail e senha da conta do
> revisor só no formulário.

> 1. Go to https://app.appfiliado.com.br/entrar/ and log in with the test account below.
> 2. In the left menu, open "Estúdio Instagram" (Instagram Studio), then click "Automações" (Automations).
> 3. Click "Conectar Instagram" (Connect Instagram). A window with Instagram Business Login opens. Log in
>    with an Instagram professional account and click "Allow". The window closes and the connected
>    profile (picture, username, name) is shown.
> 4. Click "Nova automação" (New automation). Keep "Comentou no post" (Commented on the post), click
>    "Escolher no Instagram" (Choose on Instagram) and select a post. Type QUERO in the keywords field,
>    keep the public replies and the DM text, add any link and click "Salvar" (Save).
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

## 8. Depois do envio

- A resposta costuma levar de alguns dias a algumas semanas. Acompanhe em **Análise do app › Solicitações**.
- **Se aprovar:** a gente tira a chave de teste, abre o Estúdio e as automações para os clientes (Premium), troca o "Em teste" pela página na landing e anuncia.
- **Se rejeitar:** me mande o texto exato da rejeição. A gente ajusta o ponto pedido e reenvia ("Solicitar novamente") com uma nota curta explicando o que mudou.

---

## 9. Decisões antes de gravar

1. **Publicar no Instagram (`content_publish`).** A função ainda não existe no Estúdio. Recomendação: **fazer a função antes de gravar** e mandar tudo junto, um envio e um vídeo, como você queria. A alternativa é mandar agora sem essa permissão e pedir depois, com outro vídeo.
2. **Separar a automação do Estúdio Instagram?** Se separarmos em módulos diferentes, os nomes do menu mudam. Grave depois dessa mudança.
3. **Nome e ícone do app na Meta.** Precisam ser Appfiliado antes de gravar, porque aparecem na tela de permissões.

---

## 10. O que já está pronto no Appfiliado

- Login do Instagram para empresas numa janela menor, token de 60 dias cifrado e renovado sozinho, inscrição nos webhooks.
- Automações de comentário, resposta a story e DM com palavra; resposta pública sorteada; DM com link.
- Histórico, pausar, excluir, desconectar.
- Endereços de "cancelar autorização" e "exclusão de dados" (`instagram_painel/README.md`).
- **Política de Privacidade** em `https://appfiliado.com.br/privacidade/`, com a seção do Instagram e como pedir a exclusão. **É um rascunho meu: revise o texto (e, se quiser, coloque a razão social e o CNPJ) antes de cadastrar na Meta.**
