# Pesquisa: outras plataformas de afiliados no Appfiliado

Pesquisa feita em 25/10/2026: Mercado Livre, Amazon, Magalu, AliExpress, Temu, Shein, TikTok Shop, redes de afiliados (Awin, Lomadee, Rakuten, Admitad, Actionpay, Impact), produtos digitais e concorrentes.

As páginas oficiais foram lidas diretamente sempre que o site deixou. Mercado Livre, Magalu, Casas Bahia e Reclame Aqui bloqueiam acesso de servidor (anti-bot do próprio site). Nesses casos usei trechos das páginas oficiais devolvidos pela busca, guias de terceiros e código aberto. O que não deu pra confirmar está marcado com **(não confirmado)**.

---

## 1. Resumo

- **A Shopee é exceção.** É a única grande plataforma com API oficial de afiliados que faz tudo que o Appfiliado usa: busca com % de comissão, link curto com sub IDs e relatório de vendas.
- **As outras se dividem em 4 grupos:**

| Grupo | Plataformas | O que dá pra fazer |
|---|---|---|
| **API oficial completa** | **AliExpress**, **Awin** (rede: KaBuM!, Casas Bahia, Centauro, Natura, Dafiti, C&A, Riachuelo, Renner, Nike e outras), **Lomadee** (rede) | Quase tudo que o Appfiliado faz hoje com a Shopee |
| **Link montável, mas sem dados** | **Amazon**, **Magalu** | Conversor e troca de links copiados de outros grupos. Busca, radar e relatórios só em parte (Amazon) ou nada (Magalu) |
| **Difícil** | **Mercado Livre** | Não tem API de afiliado. Gerar link exige a sessão (cookie) da conta do afiliado. É o que todos os concorrentes fazem, com risco |
| **Só manual** | **TikTok Shop**, **Temu**, **Shein** | O afiliado gera o link no app ou painel da plataforma e o Appfiliado só agenda e posta |

- **Concorrência:** o mercado tem mais de 20 ferramentas, a maioria entre R$ 39 e R$ 100/mês. **Quase todas** fazem Shopee + Mercado Livre + Amazon. Ser só Shopee é a maior desvantagem do Appfiliado nesse mercado.
- **O que ninguém tem:**
  - emissor de NFS-e e gerador de carrossel (só o Appfiliado);
  - comissão de Mercado Livre e Amazon nos relatórios (essas ferramentas só contam cliques).
- **Domínios:** não precisa liberar nada. Os bloqueios encontrados são do anti-bot das próprias lojas, não da rede do Appfiliado.

---

## 2. Quadro por função

Legenda:
- ✅ dá pra fazer, de forma oficial;
- ⚠️ dá em parte, ou com risco;
- ❌ não dá;
- ? não confirmado.

| Função | AliExpress | Awin | Lomadee | Amazon | Magalu | Mercado Livre | TikTok Shop | Temu | Shein |
|---|---|---|---|---|---|---|---|---|---|
| 1. Conversor de links | ✅ API | ✅ link montável ou API | ✅ API | ✅ tag no link | ✅ troca do nome da loja | ⚠️ só com cookie da conta | ❌ | ❌ | ❌ |
| 2a. Bot buscando ofertas sozinho | ✅ | ⚠️ por feed (ver quais lojas têm) | ✅ (?) | ⚠️ só com Creators API (10 vendas/30 dias) | ❌ | ⚠️ só produtos de catálogo, comissão estimada | ❌ (✅ se abrir pro Brasil) | ❌ | ❌ |
| 2b. Bot copiando grupos e trocando o link | ✅ | ✅ | ✅ | ✅ (preço copiado é zona cinzenta) | ✅ | ⚠️ só com cookie | ⚠️ link fixo do usuário | ❌ | ❌ |
| 3. Radar de ofertas | ✅ | ⚠️ feed | ✅ (?) | ⚠️ com API | ❌ | ⚠️ catálogo | ❌ | ❌ | ❌ |
| 4. Alerta de preço | ✅ | ⚠️ feed | ✅ (?) | ❌ proibido pela Amazon | ❌ | ⚠️ catálogo | ❌ | ❌ | ❌ |
| 5. Meu site | ✅ | ✅ | ✅ | ⚠️ regras de preço | ✅ | ⚠️ site declarado ao ML | ⚠️ manual | ⚠️ manual | ⚠️ manual |
| 6. Resultados e metas | ✅ API | ✅ API | ✅ API | ⚠️ importar CSV | ❌ | ❌ | ❌ | ❌ | ❌ |
| 7. Emissor de NFS-e | ⚠️ 1 nota de exportação | ✅ nota por pagamento | ? | ✅ 1 nota por mês | ❌ (só PF, INSS retido) | ⚠️ ML diz que não precisa | ? | ❌ (só PF) | ? |
| 8. Carrossel | ✅ | ⚠️ feed | ✅ (?) | ⚠️ fotos da API não podem ser editadas | ⚠️ manual | ⚠️ catálogo | ⚠️ manual | ⚠️ manual | ⚠️ manual |

---

## 3. Plataforma por plataforma

### 3.1 AliExpress: a mais parecida com a Shopee

**Programa (AliExpress Portals)**
- Aceita pessoa física e jurídica. A empresa que paga é a Alibaba.com Singapore E-Commerce (Singapura), em **dólar**, por remessa bancária, com saldo acima de US$ 15 e taxa bancária descontada.
- **Comissão:** vem na própria resposta da API. Blogs citam 3% a 9%, com produtos "hot" de comissão maior. A tabela oficial exige login (não confirmado).
- **Divulgação:** o contrato não proíbe WhatsApp, Telegram nem encurtadores. Exige respeitar leis antispam.
  - A cláusula 6.7 pede que o afiliado informe "agências ou subparticipantes" que usa (relevante pra um SaaS).
  - A cláusula 5.4 diz que um link curto pode deixar de funcionar com mais de 1 ano, ou sem clique por 6 meses.

**API (AliExpress Open Platform, categoria "AE-Affiliate")**
- Cada afiliado cria o próprio app "Affiliates API" e passa pro Appfiliado App Key, App Secret e Tracking ID. É o mesmo modelo que já usamos com a Shopee, e é o que FluxoPromo, Pro Afiliados e Botize fazem.
- **Aprovação:** de minutos a 2 dias. Um app por conta. O e-mail precisa ser o mesmo do Portals.
- **Métodos úteis:**
  - `aliexpress.affiliate.product.query` / `hotproduct.query`: busca por palavra ou categoria, em páginas de até 50 itens. Ordena só por preço ou por vendas.
  - `featuredpromo.products.get`: produtos de campanhas, ordenando por **comissão** ou **desconto**.
  - `productdetail.get` / `product.sku.detail.get`: preço em tempo real, fotos e vídeo.
  - `link.generate`: até 50 links por chamada, com `tracking_id`.
  - `order.list` / `order.get`: pedidos com comissão estimada e liquidada, por tracking_id.
  - `category.get`: árvore de categorias.
- **Parâmetros:** aceita `target_currency=BRL`, `target_language=PT` e `ship_to_country=BR`. Falta confirmar se o preço em BRL já inclui o ICMS.
- **Assinatura:** HMAC-SHA256 em `https://api-sg.aliexpress.com/sync`. Os métodos de afiliado não precisam de token de usuário.
- **Lacunas:**
  - Não há 5 sub IDs. Só o `tracking_id`, criado à mão no Portals.
  - A API de cupons não atende o Brasil.
  - O limite de chamadas não é publicado.

**Impostos:** a comissão vem do exterior. Pra PJ, é exportação de serviço, com PIS/Cofins isentos e ISS com risco de cobrança pelo município. A nota é **uma NFS-e de exportação por período**, pra um único tomador estrangeiro, e não uma por vendedor como na Shopee. Pra PF, carnê-leão.

**Taxa das blusinhas:** desde 13/05/2026, compras de até US$ 50 têm Imposto de Importação zerado (o ICMS continua). A Lei 15.502 (10/09/2026) só *autoriza* isso, então pode mudar. Isso ajuda a conversão de AliExpress, Shein e Temu.

### 3.2 Awin: uma integração, várias lojas

**Lojas brasileiras na Awin (a aceitação de pessoa física varia):**

| Loja | ID Awin | Comissão | Observação |
|---|---|---|---|
| KaBuM! | 17729 | 2,3% (1,15% marketplace) | Janela de **1 dia** |
| Casas Bahia | 17629 | 3% | **Não aceita PF desde 2023** |
| Centauro | 17806 | — | Janela de 1 dia |
| Natura | 17658 | — | — |
| Carrefour | 17665 | — | Não aceita PF |
| Dafiti | 17697 | 6% | — |
| C&A | 17648 | 6% | — |
| Riachuelo | 86587 | 6% | Aceita "grupos de ofertas" |
| Renner | 17801 | — | Sem PF; há o programa "Favoritos Renner" à parte |
| O Boticário | 17659 | — | Sem PF |
| Nike, Decathlon, LG, Lego, Olympikus | — | — | — |
| AliExpress | 18879 | — | — |
| Americanas | — | — | Roda numa rede privada feita com a Awin |
| Netshoes | — | — | Fontes divergem |

**Link montável (sem API):**
`https://www.awin1.com/cread.php?awinmid={loja}&awinaffid={afiliado}&clickref={sub}&ued={URL}`

**APIs:**
- Link Builder: 1 por chamada, ou 100 em lote.
- Transações: com `clickRef` a `clickRef6`, ou seja, **6 sub IDs**, que cobrem os 5 do Appfiliado.
- Ofertas e cupons.
- Feeds de produto: preço, preço antigo, % de desconto, imagem e grupo de comissão. Falta confirmar quais lojas brasileiras publicam feed.
- **Token:** por usuário, sem escopos, com limite de 20 chamadas/minuto. Precisa ser guardado como senha.

**Pagamento:** em reais pela Awin Brasil, duas vezes por mês, mínimo de R$ 50.

**NFS-e:**
- **Encaixe perfeito com o emissor do Appfiliado.** O afiliado PJ emite uma NFS-e pra Awin Brasil (CNPJ 14.182.871/0001-88) a cada ordem de pagamento, em até 3 dias:
  - código 17.06 ou 17.25;
  - descrição com o nº da ordem;
  - PDF com o nome igual ao nº da ordem;
  - envio pra brasil-financeiro@awin.com.
- **A partir de 01/01/2027, vale também pra pessoa física autônoma.**

### 3.3 Lomadee: rede brasileira, aceita PF

- Voltou ao nome Lomadee em 2025 (antes Social Soul). Aceita **pessoa física sem CNPJ** e paga por **Pix**.
- **API moderna:**
  - busca de produtos com preço e preço de tabela;
  - encurtador/deeplink;
  - pedidos;
  - chave com **escopos** (`products:read`, `shortener:write`, `orders:read`), ideal pra ferramenta de terceiros;
  - limite de 60 chamadas/minuto.
- **Sub ID:** só um campo (`mdasc`).
- Tem um **SDK de parceiro** que permite cadastrar afiliados direto na Lomadee. Pode virar parceria B2B.
- **Atenção:**
  - O catálogo lista Casas Bahia, Netshoes, Carrefour, Centauro, Natura, Boticário, Drogasil, Raia, Shein (1%) e Shopee (10%). A maioria aparece com comissão "informada no cadastro". Falta confirmar quais estão ativos.
  - Magalu, Americanas, KaBuM!, Amazon, Mercado Livre e AliExpress **não estão** na Lomadee.

### 3.4 Amazon: link fácil, dados difíceis

**Programa (Amazon Associados, associados.amazon.com.br)**
- **Quem pode entrar:** PF ou PJ (CPF/CNPJ e conta no Brasil).
- **Aprovação:** exige **3 vendas nos primeiros 180 dias**. Precisa de um "site" cadastrado: Facebook (páginas e grupos abertos), Instagram, X, YouTube, Twitch ou site. **WhatsApp e Telegram não estão na lista.**
- **Comissão:**
  - 13%: beleza, bebê, saúde, alimentos;
  - 11%: roupas, pet;
  - 10%: livros;
  - 8%: casa, eletrônicos, informática, celulares;
  - 7%: calçados, joias, automotivo e o resto.
  - A tabela personalizada por conta é não confirmada.
- **Janela:** 24h, ou 89 dias se o produto entrou no carrinho dentro das 24h.
- **Pagamento:** a Amazon Serviços de Varejo do Brasil (**CNPJ 15.436.940/0001-03**) paga por TED, cerca de 60 dias depois do fim do mês, com mínimo de R$ 30.
- **Nota fiscal:** a Amazon não exige. Pra PJ, é obrigação fiscal: **uma NFS-e por mês pra Amazon**. PF tem IR retido.

**Regras que afetam o Appfiliado**
- **WhatsApp e Telegram:** zona cinzenta. A política permite links em "mensagens diretas de redes sociais solicitadas (opt-in)". Grupo não é exatamente isso, e há relatos de contas encerradas.
- **Nome do grupo:** é proibido ter "Amazon" no nome do grupo ou do perfil.
- **Preço:** só pode ser exibido se vier da API (ou de link oficial que já o mostre), com cache de no máximo 24h, **data e hora do preço** e um aviso legal.
- **Alerta ou histórico de preço:** **proibido** sem aprovação da Amazon.
- **Encurtador:** o próprio é arriscado. O destino precisa ficar claro, e o domínio não pode conter "amazon".
- **Aviso obrigatório:** "Como Associado da Amazon, sou remunerado pelas compras qualificadas efetuadas".
- **Chaves de API:** a chave é "de uso pessoal" e não pode ser repassada a terceiros. Guardar as chaves dos clientes é risco contratual. Não há programa oficial pra ferramentas.

**Técnico**
- **Link montável sem API:** `https://www.amazon.com.br/dp/{ASIN}?tag={tag}`. É o que todos os concorrentes fazem.
- **Links curtos:** `amzn.to`/`a.co` são resolvidos seguindo o redirecionamento.
- **Sub ID:** até 100 "IDs de rastreamento" (tags) por conta, criados à mão. Um por link.
- **API:** a **PA-API 5 foi desligada em maio/2026.** A substituta é a **Creators API** (OAuth, `creatorsapi.amazon/catalog/v1/...`, header `x-marketplace: www.amazon.com.br`).
  - Exige **10 vendas qualificadas nos últimos 30 dias**. Abaixo disso, perde o acesso.
  - Traz preço, preço de referência, % de economia, ofertas relâmpago e imagens.
  - **Não traz % de comissão.** Não ordena por vendas nem por desconto. No máximo 100 resultados por busca, 1 chamada/segundo no começo.
  - O SDK tem `listReports`/`getReport`, mas sem documentação pública (não confirmado no Brasil).
- **Relatórios:** pelo portal, com download (por dia, por tag e por produto). Dá pra **importar o CSV** no Appfiliado.

### 3.5 Magalu: link montável, sem dados

**Programa (Influenciador Magalu / Parceiro Magalu, vitrine magazinevoce.com.br)**
- **Só pessoa física** (CPF e PIS), uma loja por CPF. **O Magalu retém 11% de INSS** e paga por depósito, mínimo de R$ 50, duas vezes por mês. **Não há nota fiscal.**
- **Comissão:** depende do nível da loja (Novato → Diamante) e da categoria, de 3% a 12%. Produtos de lojistas parceiros (marketplace) pagam de 2% a 4%. A tabela pública pode estar desatualizada.
- **Termos proibidos:** não pode usar "Magazine Luiza", "Influenciador Magalu" nem "Lu" em nenhuma mídia. Não pode anunciar no Google/Bing.

**Técnico**
- **Link montável:** `magazineluiza.com.br/{produto}/p/{sku}/...` vira `magazinevoce.com.br/magazine{loja}/{produto}/p/{sku}/...`. O nome da loja não muda depois de criado.
- **Trocar o link de outro afiliado:** basta trocar `magazine{outro}` por `magazine{seu}`. Links `maga.lu` precisam ser resolvidos antes.
- **Sem sub ID, sem API, sem feed, sem relatório.** O site bloqueia acesso de servidor (CAPTCHA/403), então preço e foto só com o usuário digitando.

### 3.6 Mercado Livre: o mais pedido e o mais difícil

**Programa ("Afiliados e Criadores")**
- Aberto a PF e PJ, maiores de 18. Precisa de conta Mercado Pago e perfil público aprovado. Quem vende no ML não pode participar.
- **Comissão** (tabela de out/2026, fonte secundária):
  - 16%: beleza, moda, esportes;
  - 12%: casa, bebês, brinquedos, ferramentas, games;
  - 5%: celulares, eletrônicos, informática, eletrodomésticos;
  - 0%: alimentos.
  - Venda de outra categoria paga a metade.
  - Grupos grandes (acima de R$ 50 mil/mês em vendas) têm tabela própria.
- **Janela:** **24 horas**.
- **Pagamento:** o **próprio ML** paga, na conta Mercado Pago, mensalmente. Mínimo de R$ 30, com compras de pelo menos 3 pessoas diferentes.
- **Nota fiscal:** a página do ML diz que **PJ não precisa emitir nota**, e PF tem IR retido. Quem vende emissor recomenda uma nota mensal (não confirmado).

**Regras que afetam o Appfiliado**
- **WhatsApp e Telegram:** só em grupos ou canais **públicos e abertos**, **declarados no cadastro**. Venda vinda de canal não declarado não paga e pode suspender a conta.
- **Proibido encurtar, editar ou mascarar o link** (cláusula 1.8). É preciso usar o link do próprio ML (`meli.la` ou `mercadolivre.com/sec`).
- Vendas "ligadas a robôs" não pagam. Os termos de desenvolvedor proíbem scraping. Um guia lê nos termos que "software client-side pra distribuir links é vedado" (não confirmado no texto oficial).
- O preço postado precisa bater com o anúncio.

**Técnico**
- **Não existe API de afiliado.** A API pública (api.mercadolibre.com) foi fechada em 2025–2026:
  - a busca de anúncios dá 403 mesmo com token;
  - um item de outro vendedor dá 403;
  - sobra só o **catálogo** (`/products/...`, `/highlights/...`), com login OAuth do usuário.
- **Como os concorrentes geram o link:** com o **cookie de sessão da conta do afiliado**, chamando endpoints internos do ML:
  - `POST /affiliate-program/api/v2/affiliates/createLink`, com `{urls, tag}`, até 20 links;
  - `POST /affiliate-program/api/v2/stripe/user/links`, com `{url, tag}`;
  - ambos devolvem `meli.la/...`.
  - A sessão é capturada por **extensão do Chrome** (Divulgador Inteligente, Shozap, Manda Boa, Promium, AfiliAI) ou pelo usuário colando o cookie (Espelha Grupos).
  - A sessão expira e precisa ser renovada.
  - **Guardar esse cookie dá acesso total à conta do ML e do Mercado Pago do cliente.**
- **Alternativa sem cookie:** montar o link com `matt_word` (etiqueta) e `matt_tool` (ID), tirados de um link que o usuário gerou. **Não está comprovado que essa venda é atribuída:** um teste de out/2026 não registrou o clique.
- **Sub ID:** só "etiquetas", uma por link, no máximo 100 por conta, sem poder apagar.
- **Relatórios:** só no painel. Sem API. Exportação CSV não confirmada.

### 3.7 TikTok Shop: estratégico, mas fechado por enquanto

- **Afiliado:** 18+, **1.000 seguidores**, verificação de identidade. A comissão é definida pelo vendedor (8% a 15% em média).
- **Link:** vale fora do TikTok (redes, sites, apps), com atribuição de 14 dias, e o link vale 100 dias. Mas **só é gerado no app do TikTok**.
- **API:** existem APIs pra criadores no TikTok Shop Partner Center:
  - busca de produtos com comissão;
  - pedidos e comissões;
  - links de compartilhamento;
  - autorização OAuth do criador.
- **Pro Brasil, a documentação diz "Not open"** (jul/2026).
- **Pra aplicar como parceiro:** empresa com 1 ano ou mais e produto SaaS existente.
- **Hoje dá pra fazer:** modo manual, com o afiliado colando o link gerado no app. O Espelha Grupos faz isso desde out/2026.

### 3.8 Temu e Shein: só manual

**Temu**
- **Programa oficial no Brasil:** só **pessoa física**. Cita WhatsApp e Telegram como canal.
- **Comissão:** até 35%, quase só sobre **novos usuários**.
- **Saque:** Pix, PayPal ou banco, mínimo de R$ 100.
- **Sem API.** A política proíbe:
  - encurtador que esconda a Temu;
  - redirecionamento;
  - software não aprovado;
  - "mensagens sem consentimento prévio da Temu".

**Shein**
- **Programa reformulado em 2024:** exige validar Instagram, TikTok ou YouTube.
- **Comissão:** até 20% em cliente novo, 2% nos demais.
- **Janela:** **24h**.
- **Só rastreiam produtos escolhidos no Centro de Afiliados.**
- **Saque:** Pix, mínimo de R$ 100.
- **Sem API.**

### 3.9 O resto

- **Kwai Shop:** afiliado só dentro do app, sem API. Não vale.
- **Shoppings de bancos** (Nubank, Inter, PicPay, Mercado Pago, Méliuz): são cashback, não programas pra afiliados de terceiros. Disputam o último clique com o afiliado. Não vale.
- **Produtos digitais** (Hotmart, Eduzz, Kiwify, Monetizze):
  - têm API de vendas, e a Hotmart permite passar credenciais a terceiros;
  - não têm API pra buscar produtos nem gerar link;
  - o público é outro (infoprodutos).
  - Só faria sentido o módulo Resultados, e só se houver demanda.
- **Rakuten, Admitad, Actionpay, Impact:** ativas.
  - Rakuten aceita PF e cita WhatsApp.
  - Admitad deve ser integrada como app OAuth, porque proíbe repassar credenciais.
  - Actionpay tem Netshoes, Samsung e Polishop.
  - Ficam pra depois, conforme a demanda.

---

## 4. Concorrentes

| Ferramenta | Preço/mês | Plataformas | Como faz no Mercado Livre | Como faz na Amazon |
|---|---|---|---|---|
| Pro Afiliados / Nexo | grátis, R$ 50, R$ 100 | 13 (inclui AliExpress, Magalu, Shein, Awin, Lomadee, Rakuten) | Etiqueta ou link do usuário, sem cookie | Tag |
| Achadinho Pro | R$ 49,97 (Shopee), R$ 59,97 (+ML+AMZ) | Shopee, ML, Amazon | Tag | Tag |
| Divulgador Inteligente | R$ 67 a R$ 189 | Mais de 100 lojas | Extensão lê o cookie de sessão | Tag; Creators API opcional |
| Shozap | ~R$ 90 a R$ 180 | Shopee, ML, AMZ, Shein, Magalu | Extensão captura o "token" | Extensão |
| Espelha Grupos | R$ 39 a R$ 99 | 8 lojas + Awin + Rakuten + TikTok (manual) | Etiqueta + cookie opcional (Cookie-Editor) | Tag + cookie opcional |
| Manda Boa | R$ 69,90 a R$ 269,90 | Amazon, ML, Shopee | Extensão grava cookie + token CSRF | Tag |
| FluxoPromo | R$ 97 a R$ 397 | Até 42 lojas | Lê `matt_word`/`matt_tool` de um link colado | Tag |
| Promium | R$ 97,90 a R$ 397,90 | Mais de 20 | Extensão captura cookies | Extensão gera `amzn.to` |
| Afilira | R$ 47 a R$ 197 | ML, Shopee, AMZ, Magalu, AliExpress + redes | ID | ID |

**Padrões observados:**
- **Busca automática** de ofertas quase sempre é **só na Shopee**. O resto do mercado vive de **espelhar grupos** e trocar o link.
- **Comissão real** nos relatórios: só Shopee e Awin. Mercado Livre e Amazon aparecem só como cliques, contados pelo encurtador da própria ferramenta.
- **WhatsApp:** todas usam conexão não oficial (QR Code), como o Appfiliado.
- **Reclamações frequentes:** contas de afiliado suspensas no ML e na Amazon, números de WhatsApp banidos, comissão desviada quando a troca de link falha. Os melhores **não publicam a oferta se a troca falhar**.
- **Ninguém tem** emissor de NFS-e nem gerador de carrossel.

---

## 5. Recomendação

### Fase 1: rápido e de baixo risco
1. **Conversor e bot (cópia de grupos) aceitando links de outras lojas:**
   - **Amazon:** tag + IDs de rastreamento.
   - **Magalu:** nome da loja.
   - **AliExpress:** chaves da API do próprio afiliado.
   - **Awin:** ID de afiliado + ID da loja, com `clickref`.
   - **Regra de ouro:** se a troca falhar, a oferta não é publicada.
2. **Modo manual** pra TikTok Shop, Temu, Shein e Mercado Livre: o afiliado cola o link gerado na plataforma, e o Appfiliado agenda, posta e usa no Meu site.
3. **Avisos de regras por loja** no painel. Exemplos:
   - Amazon: nada de "Amazon" no nome do grupo, aviso de associado, data no preço;
   - Magalu: nada de "Magazine Luiza" nem "Lu".

### Fase 2: integrações completas
4. **AliExpress completo:**
   - bot buscando ofertas, radar, alerta de preço, resultados (pedidos) e carrossel;
   - NFS-e de exportação mensal.
5. **Awin completa:**
   - feeds pro bot e o radar;
   - transações pros resultados;
   - **NFS-e por ordem de pagamento pra Awin Brasil** (encaixa direto no emissor).
6. **Amazon com Creators API** pra quem tiver 10 vendas/mês:
   - busca e radar com preço datado;
   - resultados por importação do CSV;
   - NFS-e mensal.
   - **Sem alerta de preço**, que a Amazon proíbe.

### Fase 3: Mercado Livre (precisa de decisão)
7. Antes de construir:
   - (a) testar, com uma conta real de afiliado, se o link com `matt_word` + `matt_tool` é atribuído;
   - (b) mandar e-mail ao time de afiliados do ML perguntando sobre API ou parceria.
8. Se o (a) falhar, o único caminho é o dos concorrentes: **extensão do Chrome capturando a sessão**. Funciona, mas:
   - quebra quando a sessão expira;
   - dá acesso total à conta ML/Mercado Pago do cliente (risco de segurança e LGPD);
   - pode violar os termos.

### Em paralelo
9. **TikTok Shop:** cadastrar o Appfiliado no Partner Center e pedir um gerente de parceiros pro Brasil, pra estar pronto quando abrir.
10. **Lomadee:** confirmar quais lojas estão ativas. Se valer a pena, a API com escopos e o SDK de parceiro são os mais fáceis de integrar.

---

## 6. O que precisa do dono do Appfiliado pra seguir

- **Contas de afiliado pra testar:** Amazon (tag), Mercado Livre (etiqueta e `matt_tool`), AliExpress (Portals + app da API) e Awin (ID de publisher).
- **Decisão sobre o Mercado Livre:** aceitar ou não o modelo de extensão com cookie.
- **Contador:**
  - NFS-e de exportação (AliExpress);
  - código de serviço da Awin (17.06 ou 17.25);
  - se o afiliado do ML precisa emitir nota.

---

## 7. Referência técnica rápida

| Plataforma | Link de afiliado | Sub ID | Dados de produto | Relatório |
|---|---|---|---|---|
| AliExpress | `link.generate` (até 50) → `s.click.aliexpress.com/e/...` | `tracking_id` (criado no Portals) | `product.query`, `productdetail.get` (BRL, PT, BR) | `order.list` |
| Awin | `awin1.com/cread.php?awinmid=&awinaffid=&clickref=&ued=` ou Link Builder API | `clickref` a `clickref6` | Feed CSV/JSONL por loja | `GET /publishers/{id}/transactions/` (31 dias por vez) |
| Lomadee | `POST /affiliate/shortener/url` → `lmdee.link` | `mdasc` | `GET /affiliate/products` | `GET /affiliate/orders` |
| Amazon | `amazon.com.br/dp/{ASIN}?tag={tag}` | Tag (até 100 por conta) | Creators API (10 vendas/30 dias) | CSV do portal |
| Magalu | `magazinevoce.com.br/magazine{loja}/{produto}/p/{sku}/...` | — | — | — |
| Mercado Livre | Endpoints internos com cookie → `meli.la`, ou `?matt_word=&matt_tool=` (atribuição duvidosa) | Etiqueta (até 100) | Só catálogo, via OAuth (`/products/...`) | — |
| TikTok Shop | Só no app (API "Not open" pro Brasil) | — | — | — |
| Temu, Shein | Só no app ou painel | — | — | — |

### Principais fontes
- AliExpress: contrato do programa (terms.alicdn.com) e docs da API em openservice.aliexpress.com (cid 21407).
- Awin: help.awin.com/apidocs, success.awin.com (pagamento e nota fiscal) e termos BR do publisher.
- Lomadee: docs.lomadee.com.br e lomadee.com.br/pt-br/afiliados.
- Amazon:
  - associados.amazon.com.br/help/operating/policies (14/04/2026) e /agreement (15/10/2025);
  - affiliate-program.amazon.com/creatorsapi/docs.
- Magalu: divulgador-magalu.zendesk.com (central de ajuda, set–out/2026) e parceiromagalu.com.br.
- Mercado Livre:
  - mercadolivre.com.br/ajuda/termos-condicoes-programa-afiliados-criadores_30228 (lida por trechos e guias de out/2026);
  - developers.mercadolivre.com.br;
  - relatos técnicos no GitHub (e-Click, Teilor-MIA, botafiliado, Afilimax).
- TikTok Shop: partner.tiktokshop.com/docv2 e seller-br.tiktok.com/university.
- Temu: temu.com/br/affiliate_policy.html (11/06/2026).
- Shein: br.shein.com/campus--a-1500.html.
- Concorrentes: sites, páginas de ajuda e código das extensões do Chrome de cada ferramenta.
