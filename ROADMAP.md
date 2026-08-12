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
      similar.

## Fase 13 — Redesign: de "gerador de link" a vitrine de ofertas (em andamento)

Motivada por uma pesquisa de UI/UX comparando o cash-b com portais grandes de
cashback/ofertas (ShopBack, Rakuten, Méliuz, Zoom etc.), trazida pelo dono do
produto — ver `BRAND.md`, seção "Histórico do redesign", pro racional
completo e as opções de identidade comparadas antes de escolher.

- [x] **Rebrand de identidade visual** — nova paleta roxo (marca/CTA) + verde
      (dinheiro/cashback) + âmbar (destaque/campanha), substituindo o
      verde+lima original. (`static/css/brand.css`, `BRAND.md`)
- [x] **Home vira vitrine** — oferta em destaque, carrossel "Em alta" e
      categorias mais vendidas logo após o hero, antes da explicação de como
      funciona. (`links/views.py`, `links/templates/links/home.html`)
- [x] **Cashback em R$ além de %** — `Oferta.valor_cashback_estimado`,
      mostrado nos cards de oferta (home e `/ofertas/`, via partial
      compartilhado `ofertas/templates/ofertas/_card.html`).
- [x] **Barra de progresso de saque** — "R$ X de R$ Y pra sacar" no painel
      (`accounts/templates/accounts/dashboard.html`), usando
      `SAQUE_VALOR_MINIMO` que já existe.
- [ ] **Busca na navegação** — hoje a busca só existe dentro de `/ofertas/`;
      o documento de pesquisa sugere um campo de busca já no header.
- [ ] **Cashback turbinado / campanhas** — badges de urgência reais (ex:
      comissão extra ativa numa categoria) usando o âmbar — só quando for
      informação verdadeira, nunca inventada.
- [ ] **Retenção** (fase mais distante, avaliar se faz sentido pro tamanho
      atual da base de usuários): favoritos/alertas de categoria, e
      gamificação só se tiver relação econômica real por trás.

---

Pra continuar esse roadmap numa conversa nova, basta apontar esse arquivo
(`ROADMAP.md`) e o `BRAND.md` — juntos eles dão o contexto de identidade
visual e do que falta implementar, sem precisar reconstruir o histórico da
conversa original.
