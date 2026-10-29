# App da Meta para anúncios: criação, beta e envio para análise

Objetivo: ler o **gasto das campanhas** na conta de anúncios do afiliado, só para leitura, e mostrar
no Appfiliado o lucro de cada campanha (investimento, comissão, margem e ROAS). Também mostrar quanto
custou cada pessoa que entrou no grupo pelo link de entrada.

O caminho tem três partes:

1. **Agora (você):** criar o app de anúncios na Meta e adicionar os testadores (seções 1 a 4).
2. **Em seguida (eu):** construir a conexão e a tela de campanhas, que funcionam para os testadores
   sem precisar da análise (seção 5).
3. **Depois de uns 15 dias de uso (você):** gravar o vídeo e enviar para análise (seções 6 a 10).

---

## 1. Por que um app separado do Instagram

- Dá para pôr o caso de uso de anúncios no app do Instagram, mas a Meta avisa que mexer numa permissão
  compartilhada entre casos de uso "pode trazer novas exigências e revisões". Com um app separado, a
  aprovação do Instagram fica intocada.
- Para o afiliado não muda nada: o login do Instagram e o do Facebook (anúncios) já são conexões
  diferentes.
- A empresa já verificada (a mesma do app do Instagram) serve para os dois apps.

---

## 2. Criar o app (passo a passo)

1. Entre em **developers.facebook.com › Meus apps › Criar app**.
2. **Detalhes do app**
   - Nome do app: **Appfiliado Anúncios**.
   - E-mail de contato: o mesmo do app do Instagram.
3. **Casos de uso:** marque **"Mensurar dados de desempenho do anúncio com a API de Marketing"** (em
   inglês, *Measure ad performance data with Marketing API*). É o caso de uso de leitura.
   - Ele **não aparece** na lista "Em destaque": clique no filtro **"Anúncios e monetização"** (ou
     **"Tudo"**) na esquerda.
   - **Não** marque "Criar e gerenciar anúncios" nem "Capturar e gerenciar leads": o Appfiliado não
     mexe nas campanhas.
4. **Empresa:** escolha o **mesmo portfólio empresarial** do app do Instagram (o que já está verificado).
5. Confira o resumo e clique em **Criar app**.

> A Meta coloca sozinha, nesse caso de uso, permissões como `ads_management` e `business_management`
> como "obrigatórias". Tudo bem: elas ficam só no **acesso padrão**. Na análise, a gente pede acesso
> avançado **apenas** de `ads_read` (seção 8), e o login do Appfiliado só vai pedir `ads_read`.

---

## 3. Configurar o app

**Configurações do app › Básico**
- [ ] **Nome de exibição: Appfiliado Anúncios** (é o que aparece na tela de consentimento do Facebook;
  fica diferente do app do Instagram e deixa claro para que é a conexão).
- [ ] **Ícone:** o mesmo ícone do Appfiliado (1024×1024).
- [ ] **Categoria:** Negócios e páginas.
- [ ] **URL da Política de Privacidade:** `https://appfiliado.com.br/privacidade/`
  (eu acrescento a seção de anúncios da Meta antes do envio, veja a seção 11).
- [ ] **URL dos Termos de Serviço:** `https://appfiliado.com.br/termos-de-uso/`
- [ ] **Exclusão de dados:** tipo **URL de retorno de chamada**,
  `https://app.appfiliado.com.br/anuncios/meta/apagar-dados/`
- [ ] **Domínios do app:** `appfiliado.com.br`

**Login do Facebook para Empresas › Configurações**
- [ ] **URIs de redirecionamento do OAuth válidos:** `https://app.appfiliado.com.br/anuncios/meta/retorno/`
- [ ] **URL de retorno de chamada para cancelar autorização:** `https://app.appfiliado.com.br/anuncios/meta/desautorizar/`
- [ ] **Login com o SDK do JavaScript:** desligado (o Appfiliado usa o login pelo servidor).

**Login do Facebook para Empresas › Configurações (criar uma configuração)**
- [ ] **Nome:** Appfiliado - leitura de anúncios
- [ ] **Variação de login:** Geral
- [ ] **Tipo de token:** **Token de acesso do usuário** (não o de usuário do sistema: muitos
  afiliados não têm portfólio empresarial, e o token do usuário funciona para todos).
- [ ] **Ativos:** **Contas de anúncios**
- [ ] **Permissões:** só **`ads_read`**
- [ ] Salve e **me mande o "ID da configuração"** (um número), junto com o **ID do app**.

**Segredo do app (importante)**
- O **App Secret** fica em **Configurações do app › Básico › Chave secreta do app**.
- **Não me mande o segredo pelo chat.** Coloque direto no Render, nos serviços **web e worker**:
  - `APPFILIADO_META_ADS_APP_ID` = ID do app
  - `APPFILIADO_META_ADS_APP_SECRET` = chave secreta do app
  - `APPFILIADO_META_ADS_CONFIG_ID` = ID da configuração do login

**Modo do app:** pode deixar em **Desenvolvimento** durante o beta. Antes do envio, ele passa para
**Publicado** (seção 6).

---

## 4. Adicionar os testadores (o beta sem análise)

Sem a análise, só quem tem uma **função no app** consegue conectar a conta de anúncios. É assim que a
gente testa com contas de verdade.

1. No app, vá em **Funções do app › Funções › Adicionar pessoas**.
2. Escolha **Testador** e digite o nome ou o e-mail do Facebook da pessoa.
3. A pessoa aceita o convite em **developers.facebook.com/requests** (ela precisa entrar uma vez no
   Meta for Developers com o mesmo Facebook).
4. Cada testador precisa ser **administrador ou anunciante** da conta de anúncios que vai conectar.
5. No Appfiliado, eu ligo a chave **"testa as campanhas da Meta"** na conta dela (no admin, como o beta
   do link de entrada).

**Quantos testadores:** você e mais 2 ou 3 afiliados de confiança que anunciam todo dia. Isso basta
para o próximo ponto.

**As 500 chamadas:** para liberar o acesso completo da API de Marketing, a Meta exige **500 chamadas
nos últimos 15 dias, com menos de 15% de erro**. Durante o beta, o Appfiliado vai ler as campanhas de
hora em hora (umas 2 chamadas por conta por hora). Só com a sua conta já passam de 700 chamadas em 15
dias.

---

## 5. O que eu construo (enquanto o beta roda)

- **Conectar conta de anúncios:** botão "Conectar Meta Ads" em Resultados, abrindo o login do
  Facebook numa janela menor que fecha sozinha (igual ao Instagram). Se a pessoa tiver mais de uma
  conta de anúncios, ela escolhe quais acompanhar.
- **Token cifrado e só leitura:** o token fica cifrado no banco. A Meta pede para reconectar a cada
  60 dias, e o painel avisa antes de vencer. Um botão **Desconectar** apaga o token.
- **Leitura de hora em hora (worker):** investimento, impressões, cliques no link, CPC e CTR por
  campanha e por dia (`/act_<id>/insights`, `level=campaign`, `time_increment=1`).
- **Tela de campanhas** (como o cartão do Afiliado Turbo, e mais):
  - dia a dia ou consolidado em 7, 15 ou 30 dias;
  - investimento com imposto (a pessoa informa o percentual que vem na fatura da Meta);
  - vendas, comissão estimada e validada, margem e ROAS;
  - cliques na Meta ao lado dos cliques que chegaram na Shopee;
  - campanha ligada ao **Sub ID pelo nome** (o nome da campanha igual ao Sub ID), com a opção de
    escolher na mão;
  - **para campanhas que levam ao link de entrada:** quanto custou cada pessoa que entrou no grupo
    (cliques por `utm_campaign`) e quanto essas pessoas renderam depois, pela comissão do grupo.
- **Na rotina:** o lucro das campanhas de ontem no relatório diário por e-mail e na Lia ("quanto
  lucrei com anúncios ontem?").
- **Política de privacidade:** a seção dos dados da Meta (o que lemos, para que serve, como apagar).
- **Endereços** de retorno, cancelar autorização e exclusão de dados da seção 3.

---

## 6. Checklist antes de gravar (depois do beta)

- [ ] O beta rodou e o painel mostra **"Acesso completo: requisitos cumpridos"** em **Painel do app ›
  Recurso Nível de acesso à API de Marketing** (as 500 chamadas em 15 dias).
- [ ] **Política de Privacidade** atualizada com a seção de anúncios (eu aviso quando estiver no ar).
- [ ] **Modo do app: Publicado.**
- [ ] **Verificação da empresa:** aprovada (a mesma do Instagram). Se o painel pedir **"Verificação de
  acesso"** (provedor de tecnologia), responda que o Appfiliado lê dados de anúncios **das contas dos
  próprios clientes** (os afiliados), com autorização deles, para relatório de desempenho.
- [ ] **Conta do revisor no Appfiliado:** a mesma `revisor.meta@appfiliado.com.br`, com a chave das
  campanhas da Meta ligada. A senha vai só no formulário da Meta, nunca em arquivo.
- [ ] **Uma campanha de verdade** rodando (ou que rodou nos últimos dias) numa conta de anúncios sua,
  com o nome igual a um Sub ID usado no link (ex.: `FONEBT1011`). Assim o vídeo mostra números reais.

---

## 7. Preparação da gravação

- **Começar deslogado (a lição da recusa do Instagram):**
  1. Desconecte a conta de anúncios no Appfiliado (botão **Desconectar**).
  2. No Facebook, vá em **Configurações › Integrações comerciais** e **remova o Appfiliado**, se ele
     aparecer. Assim a tela de consentimento aparece completa, como para um usuário novo.
  3. Grave numa **janela anônima** nova (InPrivate no Edge), sem login no Facebook nem no Appfiliado.
  4. Se o Facebook pedir código de verificação, deixe aparecer no vídeo: faz parte do login.
- **Duas janelas lado a lado:**
  - **Edge, janela InPrivate (à esquerda):** o Appfiliado e o login do Facebook.
  - **Chrome, janela normal (à direita):** o **Gerenciador de Anúncios** da mesma conta, na mesma
    campanha e no mesmo período. Serve para mostrar que o valor gasto no Appfiliado é o mesmo da Meta.
  - Encaixe uma janela de cada lado (Windows + seta para a esquerda e Windows + seta para a direita).
- **Tela:** 1920×1080, zoom entre 110% e 125%, barra de endereço visível, notificações desligadas,
  gerenciador de senhas fechado.
- **Legendas (obrigatórias):** no Clipchamp ou no CapCut, uma **faixa fixa** no canto de cima com o nome
  da permissão (texto em cada cena) e a **legenda da narração** embaixo.
- **Narração em inglês:** a interface é em português e a narração explica cada botão.
- **Sem cortes** do clique em "Continuar" até as campanhas aparecerem.
- **Duração:** uns 4 minutos.

---

## 8. Vídeo: `ads_read`

> Em cada cena: **o que fazer** (português), a **faixa na tela** (texto fixo em inglês, no canto de
> cima) e **o que falar** (inglês). O que está entre colchetes na fala é ação, não precisa ser lido.

### Cena 1. Apresentação (0:00 a 0:20)

**O que fazer**
1. Janela anônima aberta em `https://appfiliado.com.br`. Deixe 3 segundos.

**Faixa na tela**
> Appfiliado — Marketing API permission: ads_read (read-only)

**O que falar**
> "Hi, this is Appfiliado, a web platform for Shopee affiliates in Brazil. Many affiliates run ads on
> Facebook and Instagram to promote Shopee products. In this video I'll show how Appfiliado uses
> ads_read: the affiliate connects their ad account with Facebook Login for Business, and Appfiliado
> reads the daily spend and results of their campaigns, read-only, to show the profit of each campaign
> next to the Shopee commission. Appfiliado never creates, edits or pauses ads. The interface is in
> Portuguese, so I'll explain every step in English."

### Cena 2. Mostrar que está tudo deslogado (0:20 a 0:40)

**O que fazer**
1. Abra `https://www.facebook.com` e mostre a tela de login (ninguém logado).
2. Abra `https://app.appfiliado.com.br/entrar/` e mostre a tela de entrada.

**Faixa na tela**
> Starting logged out: no Facebook session, no Appfiliado session

**O que falar**
> "I'm starting from a fresh private window. I'm logged out of Facebook and logged out of Appfiliado.
> Nothing is pre-connected."

### Cena 3. Entrar no Appfiliado e achar o botão (0:40 a 1:05)

**O que fazer**
1. Entre no Appfiliado com a conta do afiliado.
2. Abra **Resultados › Campanhas** e passe o mouse sobre **Conectar Meta Ads** por 2 segundos.

**Faixa na tela**
> Step 1 — Facebook Login for Business: the user finds the "Conectar Meta Ads" (Connect Meta Ads) button

**O que falar**
> "I log in to Appfiliado as an affiliate and open 'Resultados', Results, then 'Campanhas', Campaigns.
> This is the Facebook Login for Business button: 'Conectar Meta Ads', Connect Meta Ads."

### Cena 4. Login do Facebook e consentimento (1:05 a 2:05)

**O que fazer**
1. Clique em **Conectar Meta Ads**. A janela do Facebook abre com a tela de login.
2. Digite o e-mail e a senha do Facebook e entre (e o código, se pedir).
3. Na tela que mostra **Appfiliado Anúncios** e o que ele pede: **pare por 8 segundos** e passe o mouse sobre o
   item dos **anúncios**.
4. Na escolha de ativos, marque a **conta de anúncios** e mostre por 3 segundos.
5. Clique em **Continuar** / **Salvar**. A janela fecha e o Appfiliado mostra a conta conectada.

**Faixa na tela** (com uma seta ou destaque no item dos anúncios)
> Step 2 — Consent: Appfiliado requests ads_read (read access to ads and ad performance)

**O que falar**
> "I click 'Conectar Meta Ads'. Facebook Login for Business opens in a new window. Since I'm logged
> out, I log in with my Facebook account.
> [consent screen] This is the consent screen. Facebook shows that Appfiliado Anúncios, our app for ads, is requesting access to
> my ads and their performance. This is ads_read, read-only. Appfiliado does not request permission to
> manage ads. [assets] I choose which ad account Appfiliado can read, and I continue.
> [back] The window closes and Appfiliado shows the connected ad account."

### Cena 5. As campanhas com os números da Meta (2:05 a 3:30)

**O que fazer**
1. Mostre a lista de campanhas. Abra o cartão da campanha `FONEBT1011` no modo **Dia a dia**.
2. Passe o mouse na coluna **Investimento** de um dia e, na janela do Chrome (Gerenciador de Anúncios),
   mostre o **mesmo valor gasto** na mesma campanha e no mesmo dia. Pare 3 segundos.
3. Passe o mouse em **Cliques** (Meta) e depois em **Comissão**, **Margem** e **ROAS**.
4. Troque para **Consolidado** e **30 dias**.

**Faixa na tela**
> Demonstrating ads_read — campaign spend and clicks read from the Marketing API, shown next to the Shopee commission

**O que falar**
> "Here are the affiliate's campaigns. For each campaign and each day, Appfiliado reads from the
> Marketing API, using ads_read, the amount spent, impressions and link clicks.
> [Ads Manager] On the right is Meta Ads Manager: the spend for this campaign on this day is the same
> number we show in Appfiliado.
> Appfiliado puts this spend next to the Shopee commission of the same campaign, matched by the
> campaign name, which is the affiliate's Shopee Sub ID. So the affiliate sees the margin, 'Margem', and
> the return on ad spend, ROAS, for every campaign and every day, and can stop campaigns that lose money
> in their own Ads Manager."

### Cena 6. Só leitura e desconectar (3:30 a 4:00)

**O que fazer**
1. Mostre que na tela **não há** botão de pausar, editar ou criar anúncio.
2. Clique em **Desconectar** e confirme. Mostre a conta desconectada.

**Faixa na tela**
> ads_read is read-only — the affiliate can disconnect at any time

**O que falar**
> "Appfiliado is read-only: there is no option to create, edit or pause ads. The data is shown only to
> the account owner. The affiliate can disconnect at any time, and the token and the stored data are
> deleted. That's how Appfiliado uses ads_read. Thank you."

---

## 9. Textos do formulário (em inglês)

> Em **Análise do app › Permissões e recursos**, peça **acesso avançado** só de:
> - **`ads_read`** (com o vídeo e o texto abaixo);
> - **Nível de acesso à API de Marketing** (*Marketing API Access Tier*), o botão **+Atualizar** que
>   aparece quando os requisitos estão cumpridos;
> - **`public_profile`**, se o painel mostrar o botão **Aumentar acesso** (é o que deixa quem não tem
>   função no app fazer o login).
>
> **Não** peça `ads_management` nem `business_management`.

**`ads_read`**
> Appfiliado is a web platform for Shopee affiliates (people who earn commissions by recommending
> products). Many of them run ads on Facebook and Instagram that send people to their Shopee affiliate
> links. Affiliates connect their own ad account through Facebook Login for Business and choose which ad
> accounts Appfiliado can read. We use ads_read to read, once an hour, the daily insights of each
> campaign in those ad accounts: campaign name, amount spent, impressions, link clicks, CPC and CTR
> (Insights API, campaign level, daily breakdown). We show this data only to the account owner, next to
> the Shopee commission of the same campaign, matched by the campaign name, which is the affiliate's
> Shopee Sub ID. With this, the affiliate sees the margin and return on ad spend of each campaign and
> each day. Appfiliado is read-only: it never creates, edits, pauses or deletes ads, and does not
> request ads_management. The affiliate can disconnect at any time, which deletes the access token and
> the stored ad data. Data is never sold, shared or used for advertising.
> Screencast: starts logged out; full Facebook Login for Business and consent screen requesting
> ads_read (1:05–2:05); campaign spend and clicks read from the Marketing API, compared with Ads Manager
> and shown next to the Shopee commission (2:05–3:30); read-only and disconnect (3:30–4:00).

**Nível de acesso à API de Marketing** (se pedir descrição)
> We need Full access to read the daily campaign insights of the ad accounts our customers (Shopee
> affiliates) connect to Appfiliado, once an hour, for their own performance reports. All calls are
> read-only (insights and ad account list).

---

## 10. Instruções para o revisor (em inglês)

> Cole em "Instruções passo a passo" e "Credenciais de teste". Preencha o e-mail e a senha da conta do
> revisor só no formulário.

> 1. Go to https://app.appfiliado.com.br/entrar/ and log in with the test account below.
> 2. In the left menu, open "Resultados" (Results), then "Campanhas" (Campaigns). Click "Conectar Meta
>    Ads" (Connect Meta Ads). Facebook Login for Business opens in a new window. Log in with a Facebook
>    account that is an admin or advertiser of an ad account, grant access and choose the ad account.
>    The window closes and the connected ad account is shown.
> 3. ads_read: the campaigns of the chosen ad account are listed with the daily amount spent,
>    impressions and link clicks read from the Marketing API. Open a campaign and switch between "Dia a
>    dia" (Daily) and "Consolidado" (Total). If the campaign name matches a Shopee Sub ID, the Shopee
>    commission, the margin ("Margem") and the ROAS are shown next to the spend. An ad account without
>    recent campaigns shows an empty list; the screencast shows real data.
> 4. Appfiliado is read-only: it never creates, edits or pauses ads. "Desconectar" (Disconnect) removes
>    the connection and deletes the stored data.
>
> The interface is in Portuguese; the screencast has English narration and on-screen captions naming
> the permission shown in each step. Test account: e-mail ______ / password ______.

---

## 11. Política de Privacidade (eu escrevo, você revisa)

Antes do envio, eu acrescento em `https://appfiliado.com.br/privacidade/` uma seção dos anúncios da Meta:

- o que lemos (nome das campanhas, valor gasto, impressões, cliques, CPC e CTR das contas de anúncios
  que a pessoa escolheu);
- para que serve (mostrar o lucro de cada campanha só para a própria pessoa, no painel, no relatório
  por e-mail e na Lia);
- que é só leitura e que não vendemos nem compartilhamos esses dados;
- como desconectar e pedir a exclusão (botão Desconectar e o endereço de exclusão de dados da Meta);
- que os serviços que processam os dados são a hospedagem do Appfiliado e, quando a pessoa pergunta à
  Lia sobre anúncios, o provedor de IA que gera a resposta (os mesmos que já estão listados para os
  outros dados).

**Revise o texto antes do envio**, como fez na seção do Instagram.

---

## 12. Depois do envio

- A resposta costuma levar de alguns dias a algumas semanas. Acompanhe em **Análise do app ›
  Solicitações**.
- **Se aprovar:** eu tiro a chave de beta, as campanhas da Meta abrem para todos os clientes e a gente
  atualiza o site (página de Resultados e metas, planos e perguntas frequentes).
- **Se rejeitar:** me mande o texto exato da rejeição. A gente ajusta o ponto pedido e reenvia
  ("Solicitar novamente") com uma nota curta explicando o que mudou.

---

## Fontes (Meta for Developers)

- Casos de uso da API de Marketing (permissões de cada caso de uso):
  https://developers.facebook.com/documentation/development/create-an-app/marketing-api-use-cases
- Autorização e níveis de acesso (acesso padrão e avançado, nível de acesso à API de Marketing, 500
  chamadas em 15 dias):
  https://developers.facebook.com/documentation/ads-commerce/marketing-api/get-started/authorization
