# Roadmap — cash-b

Continuação das fases do `README.md` (que vai até a Fase 7 — deploy em produção).
Cada fase é um pacote de trabalho que pode virar uma conversa/sessão própria.
Marca o checkbox conforme for implementando.

## Fase 8 — Jurídico e confiança ✅

O mais urgente do roadmap: o site já coleta CPF, e-mail e chave PIX, e mexe
com transferência de dinheiro (hoje em sandbox da Asaas) — isso deixa de ser
"bom ter" e vira exigência básica antes de abrir pra usuários de verdade.

- [x] **Termos de Uso** — regras de cashback, prazos, motivos de cancelamento,
      responsabilidades do cash-b e do usuário. (`paginas/templates/paginas/termos.html`)
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
- [x] **Páginas de erro 404/500 customizadas** — identidade visual do cash-b,
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
- [ ] **13.8 Prova social real** (médio, depende de ter dado/canal) —
      contador de "R$ já pago via PIX", print de um saque real
      anonimizado, ou link pro grupo de WhatsApp/Instagram do cash-b no
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

---

Pra continuar esse roadmap numa conversa nova, basta apontar esse arquivo
(`ROADMAP.md`) e o `BRAND.md` — juntos eles dão o contexto de identidade
visual e do que falta implementar, sem precisar reconstruir o histórico da
conversa original.
