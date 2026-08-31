# Roadmap — cash-b

Continuação das fases do `README.md` (que vai até a Fase 7 — deploy em produção).
Cada fase é um pacote de trabalho que pode virar uma conversa/sessão própria.
Marca o checkbox conforme for implementando.

## Fase 8 — Jurídico e confiança ✅

O mais urgente do roadmap: o site já coleta CPF, e-mail e chave PIX, e mexe
com transferência de dinheiro (hoje em sandbox da Asaas) — isso deixa de ser
"bom ter" e vira exigência básica antes de abrir pra usuários de verdade.

- [x] **Termos de Uso** — regras de cashback, prazos, motivos de cancelamento,
      responsabilidades da cash-b e do usuário. (`paginas/templates/paginas/termos.html`)
- [x] **Política de Privacidade (LGPD)** — quais dados são coletados (CPF,
      e-mail, chave PIX, histórico de cliques/pedidos), pra que servem, com
      quem são compartilhados (Shopee, Asaas, Brevo), e os direitos do
      titular. (`paginas/templates/paginas/privacidade.html`)
- [x] **Política de Cookies** — hoje o site só usa cookies essenciais (sessão
      de login e CSRF), então um aviso/página basta; se no futuro entrar
      analytics ou pixel de anúncio, essa página precisa ser atualizada e aí
      sim vira necessário um banner de consentimento de verdade.
      (`paginas/templates/paginas/cookies.html`)
- [x] **Página "Regras do cashback"** — versão mais completa do que já está
      na home (venda direta x indireta), prazo de liberação, o que cancela um
      pedido, percentual de repasse e valor mínimo de saque (puxados
      dinamicamente das configurações). (`paginas/templates/paginas/regras_cashback.html`)
- [x] Links pra essas páginas no rodapé de `home.html`.

⚠️ **Atenção**: esse texto foi escrito pela Claude com base no que o site já
faz, mas não é aconselhamento jurídico — vale revisar com um advogado antes
de contar 100% com isso legalmente, principalmente antes de aceitar
pagamentos reais (hoje ainda em sandbox da Asaas).

## Fase 9 — Suporte ✅

- [x] **FAQ / Perguntas frequentes** — accordion (`<details>`/`<summary>`,
      sem JS) cobrindo os 4 tipos de saldo, prazos, cancelamento, saque,
      senha e a regra de uma conta por CPF. (`paginas/templates/paginas/faq.html`)
- [x] **Fale conosco** — formulário que manda e-mail pra `contato@cash-b.com`
      via API do Brevo, com Reply-To pro e-mail de quem preencheu e um
      honeypot simples contra spam. (`paginas/templates/paginas/contato.html`,
      `paginas/forms.py`)

## Fase 10 — Conta do usuário ✅

Dá pra aproveitar a infraestrutura de e-mail que já está funcionando
(recuperação de senha) pra essas features.

- [x] **Confirmação de e-mail no cadastro** — token assinado (expira em 3
      dias) enviado no cadastro e reenviável pelo painel; saque bloqueado até
      confirmar. (`accounts/tokens.py`, `accounts/views.py`,
      `accounts/migrations/0003_user_email_verificado.py`,
      `accounts/migrations/0004_verificar_usuarios_existentes.py`,
      `saques/views.py`)
- [x] **Trocar senha estando logado** — reaproveita as views padrão do
      Django (`PasswordChangeView`/`PasswordChangeDoneView`) com templates
      próprios. (`accounts/urls.py`,
      `accounts/templates/accounts/senha_trocar.html`,
      `accounts/templates/accounts/senha_trocar_concluido.html`)
- [x] **Editar dados cadastrais** — nome, e-mail, CPF; trocar o e-mail marca
      a conta como não verificada de novo e reenvia a confirmação.
      (`accounts/forms.py`, `accounts/views.py`,
      `accounts/templates/accounts/editar_perfil.html`)
- [x] **E-mails automáticos de status** — pedido validado, cashback liberado
      e saque pago, disparados nas transições de status (inclusive nos
      caminhos em lote de `sincronizar()`/`liberar_saldo()`, que não geram
      sinais do Django). (`pedidos/notificacoes.py`, `saques/notificacoes.py`,
      `pedidos/services.py`, `saques/services.py`)

## Fase 11 — Polimento técnico ✅

- [x] **Paginação/filtro no histórico** — pedidos, saques e links gerados
      paginados (10 por página) e filtráveis por status/tipo, com query
      params independentes por seção. (`accounts/views.py`,
      `accounts/templates/accounts/dashboard.html`)
- [x] **Páginas de erro 404/500 customizadas** — identidade visual da cash-b,
      autocontidas (sem depender do manifesto de arquivos estáticos, pra
      continuar funcionando mesmo se essa for a causa do erro).
      (`templates/404.html`, `templates/500.html`)
- [x] **SEO básico** — meta description por página, sitemap.xml (via
      `django.contrib.sitemaps`) e robots.txt bloqueando áreas autenticadas.
      (`accounts/templates/accounts/base.html`, `paginas/sitemaps.py`,
      `cashback_shopee/urls.py`, `cashback_shopee/views.py`)

## Fase 12 — Crescimento (não essencial agora)

- [ ] **Programa de indicação** — "chame um amigo, ganhe X de cashback" ou
      similar. Absorvido pela Fase 13.9, ver abaixo.

## Fase 13 — Conversão e confiança (CRO)

Baseado numa análise de UX/conversão do site pronto (home, `/ofertas/`,
`/regras-do-cashback/`), comparando com concorrentes estabelecidos
(Méliuz, Cuponomia). Confirmei os pontos contra o código antes de
transformar em roadmap — duas correções relevantes: o "%" na ilustração
do hero é decorativo (SVG do `BRAND.md`), não um bug de template; e a
notificação de status por e-mail já existe desde a Fase 10. O resto se
sustentou contra o código.

Ordem sugerida por impacto/esforço - marca o checkbox conforme for
implementando. Cada item pode virar uma conversa própria.

- [x] **13.1 Trazer confiança pro hero** (rápido) — mostra o percentual
      real de repasse (`settings.SHOPEE_CASHBACK_PERCENTUAL`, dinâmico) e
      a mecânica básica (saque via PIX, valor mínimo) direto no hero.
- [x] **13.2 Simplificar o hero pra 1 CTA primário** (rápido/médio) — o
      conversor de link virou o CTA único e primário; "Ir pra Shopee"
      agora é um link secundário e discreto. A explicação direta/indireta
      continua existindo mais abaixo, como conteúdo de apoio.
- [x] **13.3 "Cadastrar" como botão sólido, "Entrar" como link** (muito
      rápido) — feito na home e na página de Ofertas (mesmo padrão de nav).
- [x] **13.4 Suavizar o aviso de cancelamento por outro link de afiliado**
      (rápido) — trocado o tom de aviso legal ("fará com que o cashback não
      seja pago") por uma dica direta; ficou na home (seção "Como ganhar
      mais cashback?") porque já é o lugar mais relevante pro contexto, e a
      regra completa continua documentada no FAQ e em regras_cashback.html.
- [ ] **13.5 Identidade jurídica no rodapé** (rápido, adiado por decisão sua) —
      já tem CNPJ (63.842.267/0001-46, MEI), mas a razão social hoje é só
      "63.842.267 EDUARDO CARREÃO FREIRE" (padrão feio de MEI). Combinamos
      esperar a migração pro Simples Nacional (prevista pra este mês) pra
      não trocar o texto do rodapé duas vezes - me avisa quando sair a
      razão social nova.
- [x] **13.6 Timeline visual de status do pedido** (médio) — mini-timeline
      de pontos (Pendente → Validado → Liberado) em cada linha da tabela
      de pedidos no dashboard, junto da etiqueta de status já existente;
      pedidos cancelados continuam só com a etiqueta + motivo, sem a
      timeline (não dá pra saber em que ponto exato cancelou). Versão
      pública equivalente em `regras_cashback.html`, ilustrando o mesmo
      caminho antes da lista de status. "PIX enviado" não virou uma etapa
      porque o saque não é vinculado a um pedido específico no modelo de
      dados (é sacado do saldo agregado).
- [x] ~~13.7 Badge "comissão extra ativa" nas ofertas em campanha~~ —
      **cancelado.** Dependia de `sellerCommissionRate` (bônus do
      vendedor), o mesmo campo que já provou ser não confiável no bug do
      percentual errado (17,8% na API vs. 8% no app da Shopee, indício de
      que é "MCN-gated" e talvez nem esteja disponível pra essa conta).
      Anunciar urgência em cima de um dado em que já não confiamos o
      bastante pra calcular cashback quebraria a mesma promessa que
      corrigimos antes.
      Em vez disso, virou **13.7b Multiplicador de campanha própria**
      (`CASHBACK_MULTIPLICADOR_CAMPANHA`, padrão 1) — uma alavanca pro
      negócio rodar campanhas de verdade (ex: "cashback em dobro" no
      aniversário do site), sem depender de dado nenhum da Shopee. Afeta
      o cashback pago de verdade em `pedidos/services.py` e
      `ofertas/models.py`, e o hero/regras_cashback.html refletem o mesmo
      valor automaticamente.
      E **13.7c Banner de anúncio na home** (`paginas.Banner`, gerenciado
      pelo Django admin) — o multiplicador muda o número, mas não
      anunciava a campanha pra ninguém. Faixa fina logo abaixo do hero,
      com texto+link opcionais por banner, ativo/inativo e ordem editáveis
      no admin (mesmo padrão já usado pra aprovar saques); com 2+ banners
      ativos, alterna sozinha a cada 5s. Zero banners ativos = a faixa
      simplesmente não aparece. Serve tanto pra campanhas de cashback
      quanto pra qualquer outro anúncio (destaque de ofertas, etc.).
      **Removido em 2026-08-12** (ver Fase 14) — por decisão do dono do
      produto, na reconciliação com o redesign da vitrine de ofertas: o
      antigo lugar do banner virou a seção de ofertas em destaque, e não
      fazia sentido manter as duas coisas competindo pelo mesmo espaço
      logo abaixo do hero. O multiplicador de campanha (13.7b) continua
      valendo normalmente, só sem uma forma de anunciar a campanha na
      home por enquanto.
- [ ] **13.8 Prova social real** (médio, depende de ter dado/canal) —
      contador de "R$ já pago via PIX", print de um saque real
      anonimizado, ou link pro grupo de WhatsApp/Instagram da cash-b no
      rodapé. Precisa ter volume mínimo pra não soar fraco.
- [ ] **13.9 Programa de indicação** (grande) — "indique um amigo, ganhe
      R$X quando ele comprar". Herda o item que já estava reservado na
      Fase 12.
- [x] **13.10 Conversor de link no topo do hero** (rápido) — em vez de
      duplicar, o conversor virou o próprio CTA principal do hero (ver
      13.2) e a seção antiga, redundante, foi removida.
- [ ] **13.11 Reduzir a fricção do login-wall** (grande, mexe na
      arquitetura) — hoje clicar em "Ir pra Shopee" ou converter um link
      exige login antes de qualquer valor percebido. Precisa de um
      desenho novo: mostrar uma prévia/estimativa de cashback sem exigir
      conta, e só pedir login no momento do clique real que gera o link
      rastreado de verdade (a lógica atual de `gerar_click` está acoplada
      a um usuário autenticado desde a raiz).
- [ ] **13.12 Prévia do dashboard na home** (rápido/médio, menor
      prioridade) — print ou mockup da tela de saldo/histórico, pra
      reduzir a incerteza de quem ainda não decidiu se cadastra.

## Fase 14 — Redesign: de "gerador de link" a vitrine de ofertas ✅ (pausada por decisão do dono, ver abaixo)

Motivada por uma pesquisa de UI/UX comparando a cash-b com portais grandes de
cashback/ofertas (ShopBack, Rakuten, Méliuz, Zoom etc.), trazida pelo dono do
produto — ver `BRAND.md`, seção "Histórico do redesign", pro racional
completo e as opções de identidade comparadas antes de escolher. Numerada
como Fase 14 (não 13) porque, sem essa conversa saber, a branch de produção
já tinha uma "Fase 13 — Conversão e confiança (CRO)" própria rodando em
paralelo (ver acima) — as duas foram reconciliadas em 2026-08-12, ver
`BRAND.md` seção "Reconciliação com a Fase 13 de CRO".

- [x] **Rebrand de identidade visual** — nova paleta roxo (marca/CTA) + verde
      (dinheiro/cashback) + âmbar (destaque/campanha), substituindo o
      verde+lima original. (`static/css/brand.css`, `BRAND.md`)
- [x] **Home vira vitrine** — oferta em destaque, carrossel "Em alta" e
      categorias mais vendidas logo após o hero, antes da explicação de como
      funciona. (`links/views.py`, `links/templates/links/home.html`)
- [x] **Cashback em R$ além de %** — `Oferta.valor_cashback_estimado`,
      mostrado nos cards de oferta (home e `/ofertas/`, via partial
      compartilhado `ofertas/templates/ofertas/_card.html`).
- [x] **Seção "Como funciona" (3 passos)** — encontre → compre → receba,
      logo depois da vitrine e antes dos blocos mais profundos (benefícios,
      venda direta x indireta), com link direto na nav. O id `#como-funciona`
      antigo (venda direta x indireta) virou `#maximizar-cashback`, mais
      fiel ao conteúdo dele. (`links/templates/links/home.html`)
- [x] **Microanimação de recompensa** — depois de gerar o link no conversor
      do hero: selo verde com check faz um "pop", acompanhado de confete
      discreto (nas cores da marca). Copy trocada pra "Cashback ativado! 🎉"
      / "Agora é só concluir sua compra na Shopee." Respeita
      `prefers-reduced-motion`. (`links/templates/links/home.html`)
- [x] **Estimativa de cashback em tempo real** — ao colar um link de domínio
      válido da Shopee no conversor, mostra na hora "💰 Essa compra pode
      gerar até X% de cashback" (100% client-side, sem chamada de API).
      Decisão: não buscar preço/comissão reais do produto, porque a Shopee
      não expõe consulta por URL/item específico hoje (só catálogo por
      categoria) - mostrar um valor em R$ sem dado real violaria o próprio
      princípio de "não inventar informação" do documento de pesquisa.
      (`links/templates/links/home.html`)
- [x] **Barra de progresso de saque** — "R$ X de R$ Y pra sacar" no painel
      (`accounts/templates/accounts/dashboard.html`), usando
      `SAQUE_VALOR_MINIMO` que já existe.
- [x] **Busca na navegação** — campo de busca no header da home
      (`links/templates/links/home.html`), submete pra
      `/ofertas/?q=...` (reaproveita o filtro `q` que já existia lá).
- [ ] ~~**Cashback turbinado / campanhas**~~ — badges de urgência reais (ex:
      comissão extra ativa numa categoria) usando o âmbar — só quando for
      informação verdadeira, nunca inventada. **Pulado por decisão do dono do
      produto (2026-08-12)** — não é prioridade agora.
- [ ] ~~**Retenção**~~ (favoritos/alertas de categoria, gamificação só se
      tiver relação econômica real por trás). **Pulado pelo mesmo motivo** —
      avaliar de novo quando a base de usuários crescer.

Esses dois itens ficam registrados aqui só pra não serem "reinventados" numa
conversa futura sem contexto — se quiser retomá-los, é só apontar pra esse
trecho do roadmap.

## Fase 15 — Indique e ganhe ✅

Programa de indicação: não é um valor fixo em R$, é um multiplicador (2x,
configurável via `CASHBACK_MULTIPLICADOR_INDICACAO`) aplicado a dois pedidos
reais específicos — a 1ª compra validada de quem foi indicado, e a compra
seguinte validada de quem indicou, depois disso.

- [x] **Código e link de indicação** — `User.codigo_indicacao` (gerado
      automaticamente, único). Link `‹site›/registrar/?ref=CODIGO` preenche
      um campo oculto no formulário de cadastro; se o código bater com um
      usuário existente, cria um `accounts.Indicacao` vinculando os dois.
      (`accounts/models.py`, `accounts/views.py::registrar`)
- [x] **Cashback em dobro nos dois lados** — durante a sincronização diária
      de pedidos, quando um pedido vira "validado": se é a 1ª compra
      validada de um indicado, dobra o cashback *daquele pedido* e marca a
      indicação; se quem comprou já indicou alguém cujo indicado validou a
      1ª compra, o próximo pedido validado dele recebe o dobro (fila FIFO
      se a pessoa tiver várias indicações pendentes ao mesmo tempo). O
      vínculo fica gravado em `Indicacao.pedido_bonus_indicado` /
      `pedido_bonus_indicador`, pra reaplicar o dobro em toda sincronização
      seguinte sem duplicar (a Shopee reenvia o mesmo pedido validado
      indefinidamente). (`pedidos/services.py`)
- [x] **Teto de R$ 20 no pedido bonificado** — o teto normal (Fase 16) é por
      produto, não por pedido, então um pedido com vários itens já pode somar
      mais que R$10 antes do dobro entrar em cena (ex: 2 itens capados a R$10
      cada = R$20 no pedido). Sem um teto próprio pro pedido bonificado, o
      dobro multiplicaria esse total pra R$40 em vez de dobrar só o limite de
      um produto (`_limite_cashback_indicacao()` = `CASHBACK_MAXIMO_POR_PRODUTO`
      × `CASHBACK_MULTIPLICADOR_INDICACAO`, aplicado nas duas sincronizações -
      quando o bônus é concedido pela 1ª vez e quando é reaplicado depois).
      (`pedidos/services.py`)
- [x] **Painel "Indique e ganhe"** — seção no dashboard com o link (botão
      copiar), quantas indicações foram feitas e concluídas, e uma tabela
      com o status de cada uma. (`accounts/templates/accounts/dashboard.html`)
- [x] **Liga/pausa a campanha pelo admin, sem deploy** — pensado pro mês de
      inauguração: se o cashback já está em dobro por uma campanha geral
      (`CASHBACK_MULTIPLICADOR_CAMPANHA`), empilhar o dobro de indicação em
      cima ficaria inviável (120% da comissão em cashback). `accounts.
      ConfiguracaoIndicacao` é uma linha única (pk=1, criada pela migração)
      editável só pelo admin - pausada, bloqueia a criação de indicações
      *novas* (cadastro com `?ref=`) e esconde a seção/link inteira do
      dashboard; indicações que já existiam continuam recebendo o dobro
      normalmente, porque o cálculo do bônus não depende desse flag, só a
      criação de vínculos novos. (`accounts/models.py`, `accounts/views.py`,
      `accounts/admin.py`)

## Fase 16 — Comissão de campanha do vendedor + teto por produto ✅

Descoberto ao investigar por que os builds recentes no Render estavam
falhando: comparando um pedido real sincronizado com o painel oficial de
afiliados da Shopee (ver `pedidos/management/commands/consultar_comissoes.py`),
confirmamos que `itemTotalCommission` (usado no cálculo real do cashback pago)
**já inclui** a comissão extra de campanha do vendedor, não só a comissão
base da Shopee. Antes disso, o catálogo de ofertas mostrava só a comissão
base (decisão da Fase 13/14, achando que o bônus não era garantido) - ou
seja, o usuário às vezes recebia mais cashback do que o site anunciava.

- [x] **Catálogo passa a contar a comissão de campanha** — `commissionRate`
      (Shopee + vendedor) em vez de só `shopeeCommissionRate`.
      (`links/shopee_client.py`, `ofertas/services.py`)
- [x] **Teto de R$ 10 por produto** (`CASHBACK_MAXIMO_POR_PRODUTO`, novo
      setting) — sem isso, um produto com comissão de campanha muito alta
      pagaria um cashback desproporcional ao preço. Aplicado tanto no
      cálculo real (`pedidos/services.py`, item a item, não por pedido) 
      quanto na estimativa mostrada no site (`ofertas/models.py`).
- [x] **Site sempre mostra o valor já ajustado pelo teto** — badge de %,
      valor em R$ nos cards (home e `/ofertas/`) e no card "Oferta do dia"
      já vêm reduzidos quando o teto se aplica, com uma nota "(máximo por
      produto)" pra transparência. Nova seção nas
      [regras do cashback](paginas/templates/paginas/regras_cashback.html)
      explicando o teto com exemplo.
- [x] Ferramenta de diagnóstico (`consultar_comissoes`) que originou essa
      descoberta permanece no projeto pra futuras verificações.
- [x] **"Até X%" no hero, calculado do catálogo real** — o "até 2,4%" fixo
      era contestado assim que a pessoa entrava no catálogo e via ofertas com
      comissão de campanha bem maior. Agora `sincronizar_ofertas()` calcula o
      maior % de cashback real entre as ofertas sincronizadas (excluindo
      ofertas onde o teto por produto reduziu o valor - senão um produto caro
      e capado poderia "roubar" o topo com um número artificialmente baixo) e
      salva num cache pequeno (`ofertas.CashbackMaximoCache`, 1x por dia, não
      recalculado a cada visita) - a home lê esse valor, então nunca diverge
      do catálogo. Sem nenhuma sincronização ainda, cai pro piso fixo
      `CASHBACK_MAXIMO_ANUNCIADO` como fallback. Nova seção nas regras do
      cashback explica por que esse número varia (reajuste mensal da Shopee,
      mais ofertas em campanha aumentam o valor). (`ofertas/models.py`,
      `ofertas/services.py`, `links/views.py`,
      `links/templates/links/home.html`)

      Chegou a virar uma faixa ("de X% a Y%") numa primeira tentativa, mas o
      dono do produto pediu pra reverter pra só o máximo - decisão de negócio
      importante: mostrar o mínimo dava a entender que a maioria das ofertas
      rende pouco, o oposto do diferencial da cash-b (% de cashback maior que
      concorrentes como Méliuz, especialmente com comissão de campanha ativa).
      **Lição registrada:** esse tipo de decisão de copy/apresentação deve ser
      perguntada ao dono do produto antes de implementar, não decidida e
      corrigida depois.
- [x] **Ordenação "Maior cashback" corrigida** — ordenava pela comissão
      bruta no banco (`percentual_comissao`), que diverge do % exibido
      (`percentual_cashback`, já com o teto aplicado) assim que um produto
      caro tem a comissão bruta reduzida pelo teto. Sintomas: ofertas fora
      de ordem na listagem, e a última página nunca chegando no mínimo real
      da faixa anunciada (o item de comissão mínima ficava escondido no meio
      da lista, com comissão bruta alta mas % exibido baixo por causa do
      teto). Esse ordering agora é feito em Python pelo valor exibido de
      verdade, não mais `.order_by()` no banco. (`ofertas/views.py`)

**Risco conhecido e aceito conscientemente:** a Fase 13.7 (mais acima) já
tinha cancelado o uso de `sellerCommissionRate` no catálogo por um motivo
concreto - um bug anterior viu 17,8% via API contra 8% no app da Shopee pro
mesmo produto, indício de que esse campo pode ser "MCN-gated" (não confiável
pra essa conta) *especificamente na query `productOfferV2`* (catálogo,
estimativa pré-compra). O que confirmamos agora com `consultar_comissoes` foi
a query **diferente** `conversionReport` (`itemTotalCommission`, pedido real
já concluído) - que bateu exatamente com o painel da Shopee. Ou seja: temos
certeza que o **pagamento real** está correto, mas **não** verificamos se o
`commissionRate` do catálogo é igualmente confiável pra essa conta. Decisão
do dono do produto (2026-08-13): usar mesmo assim, aceitando o risco de o
catálogo mostrar um % inflado se aquele bug antigo ainda se aplicar. Vale
revisitar comparando alguns itens do catálogo com o app da Shopee, se algum
usuário reportar um percentual anunciado que não bateu com o que recebeu.

## Fase 17 — Analytics no admin ✅

Painel de números do negócio dentro do Django admin (`/admin/pedidos/pedido/analytics/`),
com filtro por período (via `data_compra`) e status do pedido, e exportação em CSV.

- [x] **Cards de KPI** — quantidade de pedidos, comissão total, cashback
      repassado (e % da comissão), margem retida, ticket médio de cashback,
      saldo a liberar (pendente + validado), saldo liberado, total sacado,
      novos usuários e indicações (total e concluídas).
      (`pedidos/analytics.py::obter_analytics`)
- [x] **Detalhamento por status** — tabelas de pedidos por status e saques por
      status, incluindo status sem nenhum registro no período (zerado, não
      omitido).
- [x] **Ranking de indicadores** — quem mais indicou no período e quantas
      indicações já viraram bônus concluído.
- [x] **Filtro de origem** — separa pedidos "gerados no site" (têm um Click
      vinculado, geram cashback pago de verdade) de "fora do site" (a
      sincronização traz TODOS os pedidos da conta de afiliado Shopee, não só
      os daqui - o que sobra sem Click tem um valor_cashback calculado no
      banco mas não é pago a ninguém, mesma lógica do `OrigemFilter` já usado
      na listagem de Pedidos do admin). Sem filtro, conta todos - filtrar é
      opt-in, não muda o comportamento padrão que já existia.
      (`pedidos/analytics.py::obter_pedidos_filtrados`)
- [x] **Exportar CSV** — mesma base filtrada da tela (`obter_pedidos_filtrados`),
      pra abrir no Excel/Sheets.
- [x] **Exportar Excel (.xlsx) já formatado** — `openpyxl` (novo em
      `requirements.txt`). Planilha com 2 abas: "Resumo" (os mesmos KPIs e
      tabelas da tela) e "Pedidos" (lista bruta filtrada, igual ao CSV).
      Cabeçalho em negrito com fundo azul, moeda/percentual/data com
      `number_format` de verdade (célula numérica formatada, não texto com
      "R$" grudado), largura de coluna ajustada e primeira linha da aba
      "Pedidos" congelada. (`pedidos/analytics.py::gerar_planilha_analytics`)
- [x] **Sem view/rota nova fora do admin** — usa `ModelAdmin.get_urls()` (técnica
      documentada pelo Django) em `PedidoAdmin`, então herda a autenticação e
      permissão de staff do admin de graça. Link "Ver analytics" no topo da
      página inicial do admin via `AdminSite.index_template`.
- [x] **Faturamento (GMV) ficou de fora por decisão do dono do produto** — hoje
      só guardamos `valor_comissao` e `valor_cashback` por pedido, não o valor
      de venda do produto. Adicionar isso exigiria um campo novo + descobrir se
      a query `conversionReport` da Shopee expõe esse dado, e só valeria pra
      pedidos sincronizados dali pra frente. Fica pra uma iteração futura, se
      for necessário.
- [ ] **Quantidade de produtos vendidos ficou de fora por decisão do dono do
      produto** — a query `conversionReport` não retorna quantidade por item,
      só uma entrada por linha de item (sem confirmação de que comprar várias
      unidades do mesmo produto vira mais de uma linha), e esse dado nem é
      guardado hoje no banco. Precisaria de um campo novo (contando linhas de
      item por pedido, a única aproximação disponível hoje) + só valeria pra
      pedidos sincronizados dali pra frente. Fica pra decidir numa conversa
      futura, se for necessário.

## Fase 18 — Health check pra evitar 502 durante deploy ✅

Usuário reportou ver a página de erro 502 da própria Render (não personalizável -
é a página de infraestrutura deles, servida antes da requisição chegar no Django)
sempre que um deploy estava rolando. Causa: sem um "Health Check Path" configurado,
a Render só confere se a porta abriu antes de desligar a instância antiga e mandar
tráfego pra nova - o que pode considerar a instância nova "pronta" antes do banco
estar de fato acessível.

- [x] **`/healthz/`** — consulta o banco (`SELECT 1`) antes de responder 200;
      responde 503 se o banco não estiver acessível. (`cashback_shopee/views.py`)
- [x] **Configurar no dashboard da Render** — campo "Health Check Path" do serviço
      web, valor `/healthz/` (documentado no `README.md`, seção de deploy). **Isso
      precisa ser feito manualmente no dashboard da Render** - não tem como
      configurar por código/env var nesse projeto (não usa `render.yaml`).
- [x] **Investigado 502 residual mesmo com health check + plano Starter** — o
      log do deploy mostrou a instância antiga desligando (`SIGTERM`) e só uns
      15s depois a nova começando a subir - sequencial, não simultâneo. Causa:
      o serviço tem um **Disk** (disco persistente) anexado na Render, usado
      pelo `MEDIA_ROOT` (imagens do bot do Instagram - ver
      `cashback_shopee/settings.py`). Um disco só pode estar montado numa
      instância por vez, então a Render **não consegue fazer deploy sem
      downtime nesse caso** - precisa desligar a antiga (soltando o disco)
      antes de montar na nova. É uma trava da própria Render, documentada,
      **não depende de plano nem de health check**. Decisão do dono do
      produto: aceitar os poucos segundos de indisponibilidade por deploy por
      enquanto, em vez de migrar as imagens pra um armazenamento externo tipo
      Cloudflare R2 (que eliminaria o downtime, mas exige mudança de código
      com `django-storages` + criar/configurar o bucket). Se um dia isso virar
      um problema real (deploys mais frequentes, por exemplo), essa é a opção
      a considerar.

## Fase 19 — "Liberado" não descontava o que já foi sacado ✅

Usuário reportou: depois de sacar R$20 com R$40 liberado, o saldo "Liberado" no
dashboard continuava mostrando R$40 - dando a impressão de que ainda tinha R$40 pra
sacar, quando na real só restavam R$20. O card "Liberado" mostrava a soma bruta
histórica de `valor_cashback` dos pedidos com `status=liberado`, sem descontar saques
já feitos (a única conta que já descontava isso, `calcular_saldo_disponivel`, só
aparecia embaixo como "Saldo disponível pra saque" - dois números diferentes pra
teoricamente a mesma coisa, um deles enganoso).

- [x] **"Liberado" agora mostra `calcular_saldo_disponivel()`** — o mesmo valor de
      "Saldo disponível pra saque" mais embaixo na página, sempre em sincronia.
      (`accounts/views.py::dashboard`)
- [x] **Nova caixa "Já sacado"** — a diferença entre o total histórico liberado e o
      saldo disponível (ou seja, tudo que já foi solicitado, está processando ou já
      foi pago em algum saque). Decisão do dono do produto: contar solicitado e
      processando também, não só pago - assim os dois números (Liberado + Já sacado)
      sempre somam o total histórico liberado, sem parecer que sumiu dinheiro.
- [x] **Mesmo ajuste no menu de conta no topo do site** (`saldo_liberado_nav`, usado
      no dropdown da home e de `/ofertas/`) — tinha o mesmo problema, corrigido
      reaproveitando `calcular_saldo_disponivel()`. (`saques/services.py::
      calcular_resumo_saldo_nav`)

## Fase 20 — Separar a tarefa diária (dinheiro) dos posts do Instagram ✅

Usuário testou 2 saques, aprovou e a Asaas pagou os dois - mas o site continuou
mostrando "Processando", porque a checagem de status (`verificar_saques_pendentes`)
só roda dentro da tarefa diária agendada, uma vez por dia. Ao perguntar sobre esse
horário, o usuário pediu pra mover pra madrugada (11h podia ter gente usando o site
na hora da sincronização) - só que o mesmo endpoint também dispara os posts diários do
Instagram, cujo horário (11h) foi escolhido de propósito por causa do alcance (de
madrugada o engajamento era baixo). Resolvido separando as duas coisas.

- [x] **`executar_tarefas_agendadas` agora só cuida de dinheiro** — sincronizar
      pedidos, sincronizar ofertas, liberar saldo e verificar saques. Passou a rodar
      às **03:00 (Brasília)**, não mais 11h. (`cashback_shopee/views.py`,
      `.github/workflows/tarefas-diarias.yml`)
- [x] **Nova `executar_publicacoes_instagram`** — só os posts do Instagram e a
      checagem de validade do token, num endpoint próprio (`/tarefas/publicar-
      instagram/`), continuando às **11:00 (Brasília)** no workflow dedicado
      `.github/workflows/instagram-diario.yml`. Mesmo segredo `TAREFAS_URL`, só troca
      o caminho da URL.

## Fase 21 — Pedido "fora do site" não deve ter cashback calculado ✅

Usuário notou, testando o filtro de origem do analytics (Fase anterior): pedidos "fora
do site" (sem Click vinculado) continuavam com `valor_cashback` calculado, mesmo não
tendo usuário nenhum pra receber esse dinheiro. Fazia sentido pro `valor_comissao` (é o
que a Shopee realmente paga pra conta de afiliado, não depende de quem comprou), mas
não pro `valor_cashback` - um número que nunca vai ser pago é só ruído inflando os
KPIs do analytics.

- [x] **`_montar_defaults` só soma cashback quando tem Click** — `valor_comissao`
      continua sendo calculado normalmente pra todos os pedidos; `valor_cashback` fica
      zerado quando não há Click (e, por consequência, não há usuário) vinculado.
      (`pedidos/services.py`)
- [x] **Só vale pra pedidos sincronizados dali pra frente** — pedidos "fora do site"
      já existentes no banco só ficam com `valor_cashback` zerado na próxima vez que
      a Shopee reenviar aquele pedido numa sincronização (dentro da janela de 60 dias
      que `sincronizar()` olha pra trás).

## Fase 22 — E-mail avisando o indicador sobre o bônus pendente ✅

Levantamento de todos os e-mails que o site manda pro usuário (verificação de
cadastro/troca de e-mail, esqueci a senha, pedido validado, cashback liberado, saque
pago) mostrou uma lacuna: quem indica alguém não é avisado quando a indicação "ativa" o
bônus - só descobre o dobro de cashback quando o próximo pedido já validou (ou olhando
o painel "Indique e ganhe" manualmente).

- [x] **`notificar_indicador_bonus_pendente(indicacao)`** — dispara quando a 1ª
      compra do indicado valida, avisando o indicador que o *próximo* pedido dele vem
      com o dobro. (`pedidos/notificacoes.py`)
- [x] **Dispara uma vez só** — ligado em `sincronizar()` a partir dos vínculos que
      `_selecionar_bonus_indicacao` acabou de decidir NESSA sincronização (não a cada
      vez que a Shopee reenvia o mesmo pedido validado) - mesma garantia que já
      existia pra não duplicar o bônus em si. (`pedidos/services.py`)

## Fase 23 — Auditoria de segurança + proteção contra força bruta no login ✅

Usuário pediu uma auditoria de segurança geral. Cobrimos: settings de segurança do
Django, uso de SQL raw/`|safe`/`mark_safe` (nenhum encontrado), `csrf_exempt` (só o
webhook da Asaas, protegido por token com `hmac.compare_digest`), IDOR (consultas de
dado privado sempre filtradas por `usuario=request.user`), segredos hardcoded no
código atual (nenhum) e **no histórico do Git**.

- [x] **🔴 Achado crítico, já resolvido pelo dono do produto**: um `.env` com
      credenciais reais da Shopee (`SHOPEE_AFFILIATE_APP_ID`/`_SECRET`) foi commitado
      em 28/07 e removido no dia seguinte - mas removido do commit atual não apaga do
      histórico (`git show <commit-antigo>:.env` ainda recupera o valor). Ação: girar
      o `SHOPEE_AFFILIATE_SECRET` no painel da Shopee (invalida o valor exposto,
      independente de reescrever o histórico do Git - o que não foi feito de
      propósito, já que a branch está compartilhada com outra sessão trabalhando nela
      ao mesmo tempo, e um force-push seria muito disruptivo). Só essas duas
      credenciais estavam nesse `.env` - nada de `DJANGO_SECRET_KEY`, Asaas ou
      `TAREFAS_TOKEN`.
- [x] **Proteção contra força bruta no login (`django-axes`)** — sem isso, `/login/`
      não tinha limite de tentativas. `AXES_LOCKOUT_PARAMETERS = [["username",
      "ip_address"]]` (não só username, pra um atacante não conseguir bloquear a
      conta de outra pessoa de propósito de um IP diferente), 5 tentativas, 1h de
      cooloff. Como o `AUTHENTICATION_BACKENDS` é global, também protege
      `/admin/login/` de graça. (`cashback_shopee/settings.py`)
- [x] **Página de bloqueio com a identidade visual do site** — o padrão do
      django-axes é texto puro em inglês; trocado por
      `accounts/templates/accounts/login_bloqueado.html` (mesmo estilo do
      404/500), com link direto pra "Esqueci minha senha" (esse fluxo não passa
      pelo axes, continua liberado mesmo com o login bloqueado).
- [x] **Bug real encontrado ao testar**: com 2 backends de autenticação
      configurados, o `login(request, usuario)` direto em `registrar()` (depois de
      criar a conta) parou de funcionar - o Django não consegue mais inferir sozinho
      qual backend usar. Corrigido passando `backend=` explicitamente.
      (`accounts/views.py`)
- [ ] **Achado de menor gravidade, ainda não endereçado**: `DEBUG`/`SECRET_KEY` têm
      fallback inseguro se a variável de ambiente sumir (degrada silenciosamente em
      vez de travar o startup) - baixo risco enquanto as variáveis da Render
      continuarem configuradas certinho. Fica registrado pra decidir numa conversa
      futura se vale a pena travar o startup nesse caso.

## Fase 24 — Exemplo errado no texto do prazo de liberação ✅

Usuário notou: o texto de "Regras do cashback", Termos de Uso e FAQ dava um exemplo
errado pro prazo de liberação de saldo ("validado em janeiro libera em 1º de abril").
O código (`calcular_data_prevista_liberacao`) sempre esteve certo (mês N -> libera no
mês N+2, confirmado pelos testes existentes) - o bug era só no texto, que descrevia
"o mês seguinte a dois meses após a validação" (N+3) só nesses 3 exemplos, enquanto o
README (com outro exemplo, março -> maio) batia certinho com N+2.

- [x] **Reescrita a frase ambígua** — "o dia 1º do segundo mês seguinte ao mês da
      validação" no lugar de "o primeiro dia do mês seguinte a dois meses após a
      validação", nos 3 lugares que tinham o exemplo errado (`regras_cashback.html`,
      `termos.html`, `faq.html`) e nos 2 do README que já estavam certos (só pra
      manter a frase consistente). Exemplo corrigido pra "janeiro -> março".

---

## Fase 25 — Ajustes finos de CSS na home (desktop) ✅

Usuário mandou 4 prints da home ao vivo com 5 ajustes pontuais, todos escopados
pra versão desktop.

- [x] **Conversor de link centralizado** — label "Link do produto na Shopee" e
      o texto (placeholder/valor) do campo de URL agora ficam centralizados
      dentro da caixa, só em desktop (`@media (min-width: 861px)`, o inverso
      exato do breakpoint mobile de 860px já usado no resto do arquivo) —
      mobile continua alinhado à esquerda, sem mudança.
- [x] **Fonte do label maior** — `font-size` de 13px pra 15px, mesmo escopo
      desktop-only acima.
- [x] **"do dia" roxo em "Oferta do dia"**, **"funciona" roxo em "Como
      funciona"** e **"cashback" roxo em "Como ganhar mais cashback?"** —
      reaproveitado o `<span class="destaque-marca">` já usado em "Ofertas em
      alta" e "Por que usar a cash-b?", sem CSS novo.
- [x] **Bônus**: encontrado de passagem um "Por que usar o cash-b?" que tinha
      escapado da varredura de gênero da Fase anterior — corrigido pra "usar
      a cash-b", conforme regra já validada em `VOZ.md`.

Verificado com Playwright em 1400px (desktop) e 390px (mobile) antes de
commitar — mobile idêntico ao anterior, desktop com os 5 ajustes aplicados.
Suite completa (`links`, `pedidos`, `accounts`, `saques`, 122 testes) verde.

---

## Fase 26 — Guardar o valor do pedido (não só comissão e cashback) ✅

Usuário perguntou se dava pra guardar, além da comissão e do cashback, o
valor da compra em si ao consultar pedidos no admin. A API da Shopee nunca
foi consultada com esse dado - a query `conversionReport` só pedia
`itemTotalCommission` de cada item.

- [x] **Campo novo** — `Pedido.valor_pedido` (migração `0005`), somando o
      `actualAmount` (valor realmente pago pelo comprador, já descontando
      cupom/desconto - mesma base de cálculo da comissão) de cada item do
      pedido, igual já era feito com `itemTotalCommission`.
- [x] **Query GraphQL** (`links/shopee_client.py`) passou a pedir
      `actualAmount` também.
- [x] Aparece no `list_display` do admin, na exportação CSV e na aba
      "Pedidos" do Excel de analytics - sempre ao lado de comissão e
      cashback, na mesma ordem que a Shopee reporta.
- [x] Somado independente de ter Click vinculado (igual `valor_comissao`) -
      é o que o comprador realmente pagou, não depende de quem recebe
      cashback.

Suite completa (`pedidos`, 68 testes) verde.

---

## Fase 27 — Diferenciar a origem de cada pedido ✅

Usuário pediu pra diferenciar de onde veio cada pedido: conversão de link
direto, clique na vitrine de ofertas ou venda indireta (botão "Ir pra
Shopee"). O `Click.tipo` já existia, mas só tinha 2 valores - `produto`
cobria tanto o conversor de link quanto o clique num card da vitrine
(`ofertas/views.py::ir_para_oferta`), misturando as duas origens.

- [x] **`Click.TIPO_VITRINE`** — terceiro valor de `tipo` (migração
      `links/0002`), usado só por `ir_para_oferta`. O conversor de link
      (`links/views.py`) continua gerando `TIPO_PRODUTO`; o botão "Ir pra
      Shopee" continua `TIPO_HOME`. `gerar_click` ajustado pra tratar
      qualquer tipo != `TIPO_HOME` como "usa a URL informada", não só
      `TIPO_PRODUTO`.
- [x] **`origem_detalhada(pedido)`** (`pedidos/analytics.py`) — rótulo por
      pedido: "Link direto", "Vitrine de ofertas", "Venda indireta (Ir pra
      Shopee)" ou "Fora do site" (sem Click). Reaproveitado no
      `list_display` do admin, na exportação CSV e na aba "Pedidos" do
      Excel de analytics.
- [x] **Filtro nativo por `click__tipo`** no admin, ao lado do filtro
      "origem" (site/fora) que já existia - dá pra cruzar as duas
      granularidades.

Suite completa (179 testes) verde; conferido visualmente no admin com
Playwright (4 pedidos de exemplo, um de cada origem).

---

## Fase 28 — Avisar sobre o atraso da Shopee em reportar pedidos ✅

Usuário relatou um caso real: alguém converteu um link e comprou à noite,
achou que o pedido ia aparecer na sincronização das 03h e não apareceu.
Investigado: não é bug - a Shopee normalmente leva **alguns dias** (não
horas) pra reportar um pedido na API de afiliados, atraso do lado deles,
fora do nosso controle. O site nunca deixava isso explícito, então quem
passasse por isso podia achar que o site "sumiu" com o pedido ou é falso.

- [x] **Nota fixa em "Meus pedidos"** (`accounts/templates/accounts/dashboard.html`)
      — sempre visível, não só quando a lista está vazia: "Sua compra não
      aparece na hora nem no dia seguinte: a Shopee pode levar alguns dias
      pra confirmar o pedido pra gente. É normal, não precisa se preocupar."
- [x] **Estado vazio reforçado** — "...e eles aparecem aqui em alguns
      dias" (antes não dizia quanto tempo).
- [x] **FAQ** ("Minha compra na Shopee não apareceu no meu painel")
      reescrito pra ser concreto em vez de vago: "não aparece na hora, nem
      no dia seguinte" + limiar de quando vale entrar em contato subiu de
      "alguns dias" pra "mais de uma semana", pra não gerar contato de
      suporte por algo que ainda está dentro do prazo normal.

Suite completa (`accounts`, `paginas`, 40 testes) verde; conferido
visualmente com Playwright (nota fixa, estado vazio e FAQ expandido).

---

## Fase 29 — Ofertas manuais no carrossel da home ✅

Usuário pediu uma forma de inserir manualmente produtos no carrossel "Ofertas
em alta" da home, sem depender só do catálogo sincronizado com a Shopee -
com preço antigo/novo/à vista e desconto digitados à mão, cashback calculado
normalmente, e um selo de "oferta imperdível" opcional.

Duas decisões de design perguntadas ao usuário antes de implementar:
- **% de comissão**: digitada manualmente no cadastro (não busca ao vivo na
  API da Shopee) - a Shopee não oferece um jeito confiável de consultar a
  comissão de um produto específico por link/ID, só catálogo paginado. O
  cashback continua calculado pela mesma fórmula de sempre a partir daí.
- **Cadastro**: admin padrão do Django (uma oferta por tela, com "Salvar e
  adicionar outro(a)") em vez de um formulário customizado com JS pra
  empilhar campos numa página só - menos código novo pra manter, e a
  lista de ofertas manuais já cadastradas fica pronta pra editar/remover.

- [x] **`OfertaManual`** (`ofertas/models.py`) — link, nome, imagem, preço
      antigo/novo/à vista (opcional), % desconto, % comissão e o checkbox
      "imperdível". Nunca é apagada por `sincronizar_ofertas()` (que só
      mexe em `Oferta`) - fica até alguém remover no admin.
- [x] **Fórmula de cashback compartilhada** — extraído
      `_CashbackEstimadoMixin` de dentro de `Oferta` (mesma matemática,
      zero duplicação) - `OfertaManual` usa `preco_avista` (ou `preco_novo`
      se não preenchido) como base, `Oferta` continua usando `preco_min`.
- [x] **`selecionar_carrossel_home()`** (`ofertas/services.py`) — ofertas
      manuais entram primeiro (mais recentes primeiro), preenchendo o
      resto das vagas com as mais vendidas do catálogo sincronizado. Sem
      limite de manuais: se houver mais que o tamanho do carrossel, todas
      aparecem (ele cresce). A "Oferta do dia" (destaque) nunca vem de uma
      manual, só do catálogo sincronizado, como sempre foi.
- [x] **`ir_para_oferta_manual`** (`ofertas/views.py` + `ofertas_manual_ir`
      em `urls.py`) — mesmo fluxo de clique/gerar link de
      `ir_para_oferta`, com `Click.TIPO_VITRINE` (mesma origem "vitrine de
      ofertas" das ofertas sincronizadas - ver Fase 27); erro redireciona
      pra home (não pra `/ofertas/`, já que só aparece lá).
- [x] **`OfertaManualAdmin`** — cadastro padrão do Django, com um campo
      readonly "Cashback calculado" mostrando o % e o R$ resultante (só
      atualiza depois de salvar, sem JS ao vivo - é uma property Python).
- [x] **`ofertas/_card.html`** — selo "🔥 Oferta imperdível" + borda
      destacada quando `imperdivel=True`; preço riscado/novo quando
      `preco_antigo` preenchido; linha "à vista" quando `preco_avista`
      preenchido - tudo condicional, então o card das ofertas sincronizadas
      (sem esses campos) continua exatamente igual.

Suite completa (190 testes) verde; conferido visualmente com Playwright
(formulário do admin, lista com o cashback calculado, e o card no
carrossel da home com o selo, borda e preços).

---

## Fase 30 — "Oferta do dia" manual, numa página separada ✅

Mesma ideia da Fase 29 (produto cadastrado à mão, preço antigo/novo/à
vista, % de desconto, comissão digitada e cashback calculado
normalmente), agora pro hero "Oferta do dia" - só que numa página
própria no admin, já que só existe UM destaque por vez (diferente do
carrossel, que é uma lista sem limite).

- [x] **`_OfertaCuradaBase`** — extraídos os campos comuns entre
      `OfertaManual` e o novo `OfertaDestaqueManual` (link, nome, imagem,
      preços, % desconto, % comissão) pra uma model abstrata, sem
      duplicar. `OfertaManual` ganhou de volta só o `imperdivel` (não faz
      sentido pro destaque, que já é o único item da seção).
- [x] **`OfertaDestaqueManual`** — sem campo de tipo/flag pra marcar
      "singleton": a garantia de que só existe um registro é só no admin
      (`has_add_permission` só libera "Adicionar" quando não existe
      nenhum ainda). Cheguei a tentar forçar `pk=1` no `save()` pra
      garantir isso no model, mas isso quebra `criado_em`
      (`auto_now_add`) numa instância nova sendo "salva por cima" de uma
      já existente (vira `UPDATE` com o campo vazio, em vez de `INSERT`)
      - desisti dessa abordagem e vali só do admin mesmo, como o
      `has_add_permission` já garante na prática.
- [x] **Página dedicada** (`OfertaDestaqueManualAdmin.changelist_view`) —
      clicar em "Oferta do dia (destaque manual)" no menu do admin nunca
      mostra uma lista: vai direto pro formulário de criação (se ainda
      não existe nenhuma) ou de edição (se já existe) - sem passo
      intermediário. Trocar de produto é editar os campos da mesma
      página; remover a oferta cadastrada (botão "Remover" já nativo do
      admin) volta a "Oferta do dia" pro automático (mais vendido do
      catálogo sincronizado).
- [x] **`selecionar_carrossel_home()`** atualizado — quando existe uma
      `OfertaDestaqueManual`, ela vira a hero e nenhuma vaga extra do
      catálogo sincronizado precisa ser reservada pra isso, sobrando uma
      vaga a mais pro carrossel "Ofertas em alta".
- [x] **`ir_para_oferta_destaque_manual`** (view + `ofertas_destaque_manual_ir`
      em `urls.py`) e markup do hero (`home.html`) com o mesmo tratamento
      de preço riscado/novo/à vista já usado no carrossel.

Suite completa (221 testes) verde; conferido visualmente com Playwright
(menu do admin indo direto pra página dedicada, formulário de criação e
depois de edição com "Cashback calculado" e botão "Remover", e o hero
da home com o produto manual).

---

## Fase 31 — Remover o teto de cashback por produto ✅

Usuário levantou que o teto de R$10/produto (Fase 16) desincentivava compras
caras: com um concorrente (Méliuz) repassando um % fixo sem teto, produto caro
comprado por lá rendia mais. Analisado com dado real da conta de afiliado
(comando avulso, não versionado, rodado direto no Shell do Render) antes de
decidir: no período analisado, tirar o teto custaria pouco (~R$750 a mais em
90 dias) porque o volume de produtos caros é baixo - e nunca dá prejuízo,
porque o cashback já é sempre uma fração fixa (`SHOPEE_CASHBACK_PERCENTUAL`,
hoje 20%) da comissão recebida, nunca mais do que ela. Virou diferencial de
marketing: sem teto por produto, ninguém mais oferece isso.

- [x] **`CASHBACK_MAXIMO_POR_PRODUTO` removida** de `settings.py` e
      `.env.example` - não é mais lida em lugar nenhum do código.
- [x] **`pedidos/services.py`** — `_montar_defaults()` não limita mais
      `cashback` a um teto por item; `_limite_cashback_indicacao()` (o teto
      dobrado do bônus de indicação) foi removida inteira, já que sem teto
      normal não tem mais teto pra dobrar.
- [x] **`ofertas/models.py`** — `_CashbackEstimadoMixin` perdeu
      `_limite_por_produto` e `cashback_no_limite`; `valor_cashback_estimado`
      não usa mais `min()`. `_atualizar_cashback_maximo` (o "até X%" da home)
      não precisa mais excluir ofertas capadas, porque não existe mais oferta
      artificialmente reduzida por teto.
- [x] **`ofertas/views.py`** — a ordenação "maior cashback" da vitrine
      (`/ofertas/`) voltou a ser um `.order_by()` direto no banco (era feita
      em Python só por causa da divergência entre comissão bruta e % exibido
      que o teto causava - sem teto, as duas ordens são sempre iguais).
- [x] **Textos do site** (`home.html`, `regras_cashback.html`) — removidas
      as menções a "limitado a R$X por produto"; a seção de regras agora
      afirma "sem limite de cashback por produto" como algo positivo, não
      uma limitação a explicar.
- [x] **`instagram_bot/conteudo.py`** — `maior_cashback_de_hoje()` e
      `combo_de_stories_do_dia()` não precisam mais evitar ofertas capadas
      (o cenário "produto caro capado rouba o topo com % artificialmente
      baixo" não existe mais).
- [x] Removidos os testes que validavam especificamente o comportamento do
      teto (inclusive um comando de diagnóstico avulso, criado só pra essa
      análise e removido depois de decidido - não fazia sentido versionar
      algo que lê uma configuração que não existe mais).

Fase 16 (que introduziu o teto) foi deixada como está no histórico deste
arquivo - documenta uma decisão real da época, não precisa ser reescrita.

Suite completa (212 testes) verde.

---

## Fase 32 — Ordenar a vitrine por maior cashback em R$ ✅

Usuário pediu uma segunda ordenação na vitrine de ofertas: além de "maior
cashback" por %, agora também por valor em R$ - as duas dão ordens
diferentes (produto caro com % baixo pode valer mais em R$ que um barato com
% alto).

- [x] **`maior_cashback_reais`** em `ORDENACOES`/`ORDENACOES_ROTULOS`
      (`ofertas/views.py`) - rótulos existentes renomeados pra "Maior
      cashback (%)" e "Maior cashback (R$)", pra distinguir as duas.
- [x] Ordenado direto no banco via `annotate(cashback_reais=F("preco_min") *
      F("percentual_comissao"))` - `valor_cashback_estimado` (a property
      real) multiplica esses dois campos por um repasse que é constante pra
      toda a consulta, então a ordem bate sem precisar calcular a property
      item por item em Python (mesma simplificação da Fase 31).
- [x] Corrigido `instagram_bot/conteudo.py::ORDENACAO_MAIOR_CASHBACK`
      ("Maior cashback" → "Maior cashback (%)") - o rótulo usado no
      passo a passo do story pra ensinar a ordenar na vitrine, pra continuar
      batendo com a opção real do dropdown (um teste já existente
      (`test_passo_a_passo_usa_o_rotulo_real_da_vitrine`) pegou a
      divergência sozinho).

Suite completa (213 testes) verde; conferido visualmente com Playwright as
duas ordenações dando ordens opostas com os mesmos dois produtos de teste.

---

## Fase 33 — Combo diário do Instagram vira 5 stories (% e R$ separados) ✅

Depois da Fase 32 (duas ordenações na vitrine), o combo diário de stories
ainda só falava do maior cashback em %. Usuário pediu uma sequência de 5
stories: capa → produto de maior % (com um segundo story mostrando a conta
em R$, já que % sozinho não deixa claro o retorno) → produto de maior R$
(esse já mostra o valor direto, sem precisar de conta) → passo a passo de
como achar esses produtos, agora citando as duas ordenações que existem.

- [x] **`combo_de_stories_do_dia()`** (`instagram_bot/conteudo.py`)
      reestruturada de 3 pra 5 stories: capa (frase de efeito) →
      número+produto do maior % → conta detalhada desse mesmo produto →
      número+produto do maior R$ → passo a passo. Os dois produtos podem
      ser diferentes (um preço baixo com % alto, outro caro com % baixo
      mas R$ maior) - a consulta já buscava os dois separadamente, só a
      montagem do combo não aproveitava isso ainda.
- [x] **`ORDENACAO_MAIOR_CASHBACK_REAIS`** nova constante, ao lado da
      `ORDENACAO_MAIOR_CASHBACK` já existente - `como_achar_na_vitrine()`
      passou a citar as duas ordenações no passo a passo ("Ordene por
      'Maior cashback (%)' ou 'Maior cashback (R$)'"), continuando
      acoplada de propósito ao rótulo real do dropdown de `ofertas/views.py`
      (mesmo teste de acoplamento da Fase 32 pegou uma divergência
      esquecida durante essa implementação).
- [x] **Story de capa novo** — usa `gerar_imagem_texto_simples()` (já
      existia, reaproveitado sem mudança de assinatura) com um título tipo
      "Os maiores cashbacks de hoje 💸", nas cores da marca.
      (`instagram_bot/services.py::publicar_combo_de_stories`)
- [x] Testes de `instagram_bot/tests.py` reescritos pra validar a
      sequência de 5 stories, incluindo um cenário novo em que o produto
      de maior % e o de maior R$ são produtos diferentes de propósito.

Suite completa (213 testes) verde; conferidas visualmente as 5 imagens
geradas (PIL, mesmas funções de `templates_imagem.py` usadas em produção)
com dados de exemplo onde os dois produtos escolhidos divergem.

---

## Fase 34 — Cashback real ao converter um link no site ✅

Usuário notou: ao converter o link de um produto na home, o site só mostrava o "até
X%" genérico (maior % do catálogo sincronizado no dia) - mas a Shopee tem muito mais
produtos do que os que entram nesse catálogo, então esse número não reflete a
comissão real daquele produto específico.

- [x] **`links/views.py::_buscar_cashback_real()`** — reaproveita
      `ofertas.services.buscar_oferta_por_link()` (já existia, criada pra postar um
      story manual de um produto específico) pra consultar a comissão REAL do produto
      convertido direto na Shopee (`productOfferV2` filtrado por `itemId`), calculando
      o % e o R$ de cashback de verdade daquele item - não mais um valor genérico do
      catálogo. O link já foi gerado nesse ponto, então qualquer falha nessa busca
      extra (rede, produto não resolvido) só significa "sem estimativa exata pra
      mostrar", nunca desfaz o link.
- [x] **`ofertas.services.SemComissaoError`** — nova exceção (subclasse de
      `LinkProdutoInvalidoError`, então quem já tratava esse erro genericamente, como
      `postar_oferta_especifica`, continua funcionando sem mudança), levantada quando
      a Shopee não retorna nenhuma oferta pro `item_id` - ou seja, não tem comissão de
      afiliado ativa nesse produto agora. Antes isso caía no mesmo erro genérico de
      "link inválido"; separar deixa o site mostrar uma mensagem clara e específica
      ("A Shopee não oferece comissão para esse produto, portanto também não há
      cashback") em vez de confundir com link malformado ou dar a entender que a
      cash-b está ficando com a comissão sem repassar nada.
- [x] **`home.html`** — a caixa de resultado da conversão mostra o % e R$ reais
      quando a busca funciona, a mensagem de "sem comissão" (sem confete, já que não é
      uma comemoração) quando não há comissão ativa, e só cai pro "Cashback ativado!"
      genérico como último recurso, se a busca falhar por outro motivo.

Suite completa (219 testes) verde.

---

## Fase 35 — Bug real: link curto caindo sempre no genérico ✅

Testando a Fase 34 em produção, o dono do produto reportou dois links curtos reais
(`s.shopee.com.br/...`) que sempre caíam no "Cashback ativado!" genérico, nunca no %
real nem na mensagem de "sem comissão" - sinal de que a busca estava falhando por um
motivo diferente dos dois já tratados. Com o log adicionado nessa mesma investigação
(`[links] não consegui buscar o cashback real de ...`), a causa apareceu: a Shopee não
chegou a redirecionar de verdade pro pedido feito pelo servidor (a "URL final" voltava
idêntica à original) - preciso do dono do produto abrir o mesmo link num navegador de
verdade pra confirmar o que estava acontecendo.

- [x] **Causa raiz encontrada**: a Shopee usa dois formatos de link de produto - o
      antigo `.../produto-exemplo-i.<shopId>.<itemId>` (o único que `_resolver_item_id`
      reconhecia) e um mais novo `.../product/<shopId>/<itemId>`, visto no navegador
      resolvendo o link curto reportado. O regex simplesmente não reconhecia esse
      segundo formato - por isso caía sempre no erro genérico "não consegui
      identificar o produto", mesmo com o item certo bem ali na URL.
- [x] **`PADRAO_ITEM_ID_NA_URL`** (`ofertas/services.py`) passou a reconhecer os dois
      formatos. Resolve de imediato quem cola o link já no formato novo (nem precisa
      de chamada de rede) e também os redirecionamentos que terminam nesse formato.
- [x] **Limite confirmado**: o dono do produto testou de novo o mesmo link curto
      depois desse fix e bateu exatamente no cenário previsto - "URL final" idêntica à
      original, ou seja, a Shopee nem chega a redirecionar de verdade pro pedido feito
      pelo servidor (sem executar JS, sem sessão/cookies de navegador). O regex
      corrigido continua certo e necessário (resolve quem cola o link já resolvido, ou
      cujo redirecionamento funciona), só não alcança esse caso específico.
- [x] **Headers de navegador mais completos** (`_resolver_item_id`,
      `ofertas/services.py`) — além do User-Agent que já existia, passou a mandar
      `Accept`, `Accept-Language`, `Upgrade-Insecure-Requests` e os `Sec-Fetch-*` que um
      navegador de verdade sempre manda e o requests não. **Não resolveu** - o dono do
      produto testou de novo e o log confirmou status 200 com 0 redirecionamentos, o
      mesmo resultado de antes. Isso descarta bloqueio por header/fingerprint simples:
      o formato da resposta (200 direto, sem `Location` nenhum) é típico de link
      dinâmico resolvido via JavaScript no navegador, não redirecionamento HTTP - uma
      barreira que `requests` não tem como vencer, com header nenhum.
- [x] **Decisão do dono do produto**: não vale investir num navegador headless
      (Playwright/Chromium no servidor) só pra esse tipo de link - custo real demais
      (mais segundos por conversão, mais memória/CPU no plano da Render) pra um caso
      que não é a maioria dos links colados. Aceitar a limitação e ajustar o texto pra
      não prometer nada que não foi confirmado (ver Fase 36).

Suite completa (219 testes) verde.

---

## Fase 36 — Não afirmar cashback quando a busca real falha ✅

Consequência direta da decisão da Fase 35: enquanto a busca da comissão real
(`buscar_oferta_por_link`) falhava por um motivo genérico (nem confirma comissão, nem
confirma ausência dela - ex: o link dinâmico da Fase 35), a caixa de resultado ainda
dizia "Cashback ativado! 🎉", com confete - afirmando algo que o site não tinha
confirmado de verdade.

- [x] **`home.html`** — esse terceiro cenário (nem % real, nem confirmação de "sem
      comissão") trocou "Cashback ativado! 🎉" + "Agora é só concluir sua compra na
      Shopee." por "Link gerado!" + "Para conferir o cashback desse produto, acesse
      sua conta em alguns dias." - tom neutro, sem confete (reservado só pro caso em
      que o % real foi confirmado de verdade).
- [x] **`links/tests.py`** — teste do cenário de falha genérica atualizado pra cobrir
      o novo texto e confirmar ausência de confete.

Suite completa (220 testes) verde.

---

## Fase 37 — Navegador headless (Browserless) pra resolver links dinâmicos (revertida)

Continuação direta da Fase 35/36. Com o comando de diagnóstico rodado em produção,
descobrimos que **44,1%** de todos os links de produto já convertidos no site são
curtos (`s.shopee.com.br`/`shp.ee`), e testando de verdade contra a Shopee, **100%**
deles falharam na resolução simples - um problema bem maior do que o esperado, não um
caso raro. Pesquisei alternativas antes de decidir: não existe endpoint oficial da
Shopee pra resolver esse tipo de link (até bibliotecas de terceiros fazem o mesmo
"seguir redirect HTTP" que a gente já tentava), então só um ambiente que executa
JavaScript resolve. Comparado o custo de hospedar Chromium no próprio servidor
(exigiria upar o plano da Render de Starter/$7 pra Standard/$25 só pela RAM) contra um
serviço externo de navegador headless - Browserless.io tem plano gratuito de 1.000
unidades/mês, recorrente, que cobre o volume atual do site sem custo nenhum.

- [x] **`BROWSERLESS_API_KEY`/`BROWSERLESS_API_URL`** (settings.py, .env.example) -
      opcional, como o GEMINI_API_KEY: sem preencher, esses links específicos continuam
      caindo no texto neutro (Fase 36), o resto do site funciona normal.
- [x] **`ofertas/services.py::_resolver_url_final_via_navegador()`** - chama a API
      REST do Browserless (`/function`, rodando um Puppeteer real: `page.goto` +
      `page.url()`) só como último recurso, depois que a resolução simples
      (`_resolver_item_id`) já tentou e falhou. `buscar_oferta_por_link()` ganhou um
      parâmetro `usar_navegador` (padrão `False`) pra não mudar o comportamento de quem
      já chamava essa função (ex: `postar_oferta_especifica`).
- [x] **Busca em segundo plano, sem travar a conversão do link** - o navegador headless
      é mais lento (alguns segundos) e usa uma cota mensal limitada, então só é chamado
      DEPOIS que a página já carregou, via JS (`fetch`), não durante a resposta da
      conversão. Fluxo: link aparece na hora (como sempre) → se a resolução rápida não
      conseguiu confirmar nada, mostra "Buscando o cashback real..." → JS chama
      `/cashback-real/<click_id>/` (`cashback_real_pendente`, `links/views.py`) → quando
      responde, atualiza a caixa sozinha (% real, "sem comissão" ou o texto neutro final,
      se o navegador headless também não conseguir).
- [x] **`Click.id` (UUID) identifica o pedido pendente** - o endpoint novo filtra por
      `usuario=request.user`, pra ninguém conseguir consultar o click de outra pessoa
      (404 se não for dono).
- [x] Testes cobrindo: `usar_navegador` só chama o Browserless quando pedido
      explicitamente, erro claro se `BROWSERLESS_API_KEY` não estiver configurada, os
      3 status do endpoint novo (`ok`/`sem_comissao`/`falhou`) e o controle de posse do
      click. Verificado também com Playwright que o JS atualiza a caixa corretamente
      nos 4 cenários (sucesso, sem comissão, falha explícita, erro de rede) - sem poder
      testar contra o Browserless de verdade nesse ambiente (sem credenciais aqui),
      então a integração real (endpoint/formato exato da API) precisa de teste em
      produção depois que a chave for configurada.

**Confirmado em produção, com dois achados:**
- [x] **Bug de parsing corrigido** - a resposta real do `/function` vem embrulhada no
      mesmo formato que a função JS retornou (`{"data": {"url": ...}, "type": ...}`),
      não achatada como eu tinha suposto (`{"url": ...}`) - `_resolver_url_final_via_navegador`
      ajustada pra ler `dados["data"]["url"]`.
- [x] **Achado mais sério, motivo da reversão**: mesmo com um navegador de verdade
      (que executa JavaScript, diferente do `requests`), a Shopee **bloqueou** o
      Browserless como tráfego suspeito - a URL final resolvida foi uma página de
      verificação (`/verify/traffic/error?...&is_logged_in=false`), não o produto.
      Testado uma segunda vez com outro link curto, mesmo resultado - **100% de
      bloqueio**, não um caso raro. O problema não é só "precisa executar JS", é
      "precisa parecer um navegador humano de verdade" pra passar pela proteção
      anti-bot da Shopee nesse tipo de link de rastreamento - e é bem provável que
      seja um bloqueio por reputação de IP (faixas de datacenter/automação
      conhecidas), não algo específico do Browserless que outro serviço parecido
      resolveria. Decisão do dono do produto: não vale investir em camuflagem extra
      (proxy residencial, stealth mode pago) pra contornar isso - aceitar a
      limitação e reverter.
- [x] **Revertida por completo** - removidos `BROWSERLESS_API_KEY`/`BROWSERLESS_API_URL`
      (settings.py, .env.example), `_resolver_url_final_via_navegador` e o parâmetro
      `usar_navegador` (`ofertas/services.py`), o endpoint `cashback_real_pendente` e
      `click_id_pendente` (`links/views.py`, `links/urls.py`), e o JS/HTML
      correspondente em `home.html`. Voltou a ser exatamente o comportamento da Fase
      36: resolução rápida e síncrona, sem segunda tentativa - se falhar, mostra o
      texto neutro na hora, sem a espera "Buscando..." que nunca resolvia de verdade
      pra esse tipo de link.

Essa fase fica registrada aqui como decisão real, já revertida - documenta a
investigação e o motivo de não valer a pena, não precisa ser reescrita se alguém
tiver a mesma ideia numa conversa futura.

Suite completa de volta a 220 testes verde (mesma contagem da Fase 36) depois da
reversão.

---

## Fase 38 — Explicar a limitação do cashback real nos textos do site ✅

Consequência das Fases 34-37: usuário pediu pra deixar explícito, em todo lugar que
fala sobre como o site funciona, que a cash-b tenta mostrar o cashback real ao
converter um link, mas que isso nem sempre é possível por restrição da própria
Shopee (não é falta de vontade nem falha do site) - e que isso não afeta o cashback
de verdade, só a confirmação imediata na tela.

- [x] **`home.html`** - nova observação na seção "Como ganhar mais cashback?", logo
      depois da dica existente sobre não passar por outros links de afiliado.
- [x] **`regras_cashback.html`** - nova seção "Cashback real ao converter um link",
      entre "Venda direta x venda indireta" e "Sem limite de cashback por produto".
- [x] **`faq.html`** - nova pergunta ("Por que às vezes não aparece o % de cashback
      ao converter um link?"), logo depois da pergunta sobre venda direta/indireta.
- [x] **`termos.html`** - novo parágrafo na seção "2. Como funciona o cashback",
      com o mesmo conteúdo em tom mais formal.

Verificado com Playwright (screenshot das 4 páginas, sem erros de console) e suite
completa (220 testes) verde - conteúdo textual novo, sem mudança de comportamento.

---

Pra continuar esse roadmap numa conversa nova, basta apontar esse arquivo
(`ROADMAP.md`) e o `BRAND.md` — juntos eles dão o contexto de identidade
visual e do que falta implementar, sem precisar reconstruir o histórico da
conversa original.
