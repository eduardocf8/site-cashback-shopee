# cash-b — manual de marca

Este arquivo documenta as decisões de identidade visual e as escolhas de
infraestrutura ligadas à marca, pra qualquer conversa futura (ou qualquer
pessoa) conseguir continuar o projeto sem precisar reconstruir esse
contexto do zero.

## O que é

**cash-b** é um site de cashback pra quem compra na Shopee: o usuário gera
um link de afiliado pelo site, compra normalmente, e recebe de volta uma
parte da comissão que a Shopee paga.

- Domínio: **cash-b.com**
- Repositório: `eduardocf8/site-cashback-shopee`
- Branch de produção (a que a Render usa pra fazer deploy): `claude/shopee-cashback-site-6hb939`

## Logotipo

- **Só o nome**, em minúsculo: `cash-b`. Sem ícone, sem símbolo, sem monograma
  substituindo o nome.
- Fonte: **Familjen Grotesk**, peso 700 (bold).
- Espaço de proteção: margem mínima ao redor igual à altura do "c" minúsculo.
- Exceção: pra ícones muito pequenos (favicon, avatar de rede social), usa-se
  o monograma **"cb"** — mas isso é só uma redução de uso restrito, nunca
  substitui o logotipo completo em nenhum outro lugar.

## Paleta de cores

Definida como CSS custom properties em `static/css/brand.css`. Paleta atual desde o
redesign de 2026-08 (ver "Histórico do redesign" no fim deste arquivo) — três cores
com papel semântico bem separado, pra não repetir o problema da paleta anterior (um
único "highlight" fazendo função de marca, atenção e dinheiro ao mesmo tempo).

| Token | Hex | Uso |
|---|---|---|
| `--ink` | `#111827` | Texto principal |
| `--ink-soft` | `#374151` | Texto secundário (labels, subtítulos) |
| `--muted` | `#6b7280` | Texto apagado (legendas, placeholders) |
| `--brand` | `#6d28d9` | Roxo — marca, wordmark, CTAs principais, links |
| `--brand-strong` | `#4c1d95` | Hover/variante escura do roxo |
| `--highlight` | `#f59e0b` | Âmbar — **só** destaque/atenção: grifo `.mark`, badges de campanha/urgência (ex: "Oferta do dia", "Cashback turbinado") |
| `--highlight-ink` | `#111827` | Texto sobre o âmbar |
| `--success` / `--success-bg` | `#059669` / `#ecfdf5` | Verde — **dinheiro**: badge de cashback nos cards, saldo liberado, confirmações |
| `--paper` | `#f8fafc` | Fundo principal (claro) |
| `--paper-2` | `#f1eefb` | Fundo secundário (seções alternadas, cards) |
| `--line` / `--line-soft` | `#e0dcef` / `#ede9f7` | Bordas e divisores |
| `--danger` / `--danger-bg` | `#dc2626` / `#fee2e2` | Erros, badge de desconto |
| `--info` / `--info-bg` | `#2563eb` / `#eef2ff` | Estados informativos (ex: status "validado") |

**Regra de ouro (atualizada)**: cada cor tem um papel fixo — roxo é ação/marca, verde é
dinheiro/positivo, âmbar é atenção/campanha. Não usar uma cor fora do papel dela (ex:
não usar roxo pra badge de cashback só porque "é a cor da marca") — foi exatamente
essa mistura de papéis que a paleta anterior tinha e que motivou parte da reformulação.

## Tipografia

- **Familjen Grotesk** (peso 400–700) — títulos e texto corrido. Fonte
  auto-hospedada em `static/fonts/familjen-grotesk.woff2` (licença OFL,
  Google Fonts).
- **JetBrains Mono** — números e dados (valores em R$, percentuais, tabelas).
  Dá uma sensação de "extrato/recibo" pros valores de cashback. Arquivo em
  `static/fonts/jetbrains-mono.woff2` (licença OFL).
- Ambas as fontes foram baixadas e sub-setadas (só os caracteres usados) pra
  ficarem leves — ver histórico de commits se precisar regenerar.

## O "mark" (destaque estilo marca-texto)

Um retângulo âmbar (`--highlight`) atrás de uma palavra-chave, tipo grifo de
marca-texto — referência direta ao conceito de "destacar o dinheiro que volta".
É o único elemento gráfico do sistema além da tipografia. Implementado pela
classe `.mark` em `static/css/brand.css`. Exemplo de uso: o "de volta" no
título da home (`links/templates/links/home.html`).

**Regra**: usar no máximo uma vez por página — é pra ser um momento único,
não decoração repetida.

## Ilustrações

**Sem fotografia.** Todo elemento visual do sistema é forma geométrica plana
(SVG), nas cores da marca — nunca fica com aparência de arte genérica de IA.
Dois temas usados até agora:

- **Cashback/moeda**: um anel incompleto em âmbar ao redor de um círculo com
  "R$" — usado nos painéis de login/cadastro/recuperação de senha
  (`accounts/templates/accounts/_ilustracao_auth.html`).
- **Sacola + selo de desconto**: uma sacola de compras com um selo circular
  de "%" no canto — usado no hero da home (`links/templates/links/home.html`).

Ambos ficam sobre um painel com gradiente `--brand-strong` → `--brand` (roxo),
com uma "mancha" (blob) orgânica em âmbar ao fundo, baixa opacidade.

Se um dia quiser usar fotografia de verdade (o Claude não tem ferramenta de
geração de imagem nem acesso a bancos de imagem neste ambiente — precisa que
alguém forneça o arquivo), a orientação é aplicar um tratamento duotone nas
cores da marca antes de usar, pra não destoar do resto do sistema.

## Onde cada coisa mora no código

- `static/css/brand.css` — tokens de cor, fontes, classes de ilustração e do `.mark`.
- `static/fonts/` — Familjen Grotesk e JetBrains Mono (woff2, sub-setadas).
- `static/favicon.svg` — favicon com o monograma "cb".
- `accounts/templates/accounts/_campo_formulario.html` — partial de campo de
  formulário padrão (já com botão de mostrar/esconder senha nos campos de senha).
- `accounts/templates/accounts/_ilustracao_auth.html` — ilustração do painel
  de login/cadastro/recuperação de senha.
- `accounts/templates/accounts/base.html` — layout compartilhado das páginas
  de conta (login, cadastro, recuperação de senha, chave PIX, gerar link).
- `links/templates/links/home.html` e `accounts/templates/accounts/dashboard.html`
  — páginas com HTML/CSS próprio (não usam `base.html`).
- `marketing/instagram/` — histórico e decisões do Instagram da cash-b
  (roadmap do bot de postagens, posts institucionais já aprovados, script
  que gera as artes). Ver `marketing/instagram/README.md`.
- `VOZ.md` — guia de tom de voz (como a cash-b escreve, verbos e
  expressões a evitar). Separado deste arquivo porque trata de texto, não
  de identidade visual.

## Infraestrutura ligada à marca

- **Domínio**: `cash-b.com`, registrado no Namecheap, DNS gerenciado pela **Cloudflare**.
- **Site**: hospedado na **Render** (plano gratuito), deploy automático a
  partir da branch `claude/shopee-cashback-site-6hb939`.
- **E-mail**:
  - `contato@cash-b.com` **recebe** via Cloudflare Email Routing, encaminhando
    pro Gmail pessoal do dono.
  - **Enviar como** `contato@cash-b.com` pelo Gmail pessoal é feito via SMTP
    do Brevo (Gmail → Configurações → Contas e importação → Enviar e-mail como).
  - O **site em si** (Django) manda e-mail de recuperação de senha usando a
    **API HTTP do Brevo** (`cashback_shopee/brevo_email_backend.py`, variável
    `BREVO_API_KEY`) — **não usa SMTP**. Isso é proposital: a Render bloqueia
    conexões SMTP de saída (porta 587), então qualquer envio de e-mail feito
    pelo próprio site precisa ser por API HTTP.

## Decisões e armadilhas já resolvidas (não repetir)

- **Render bloqueia SMTP de saída.** Qualquer envio de e-mail transacional
  feito pelo Django tem que ser via API HTTP de um provedor (hoje: Brevo),
  nunca `django.core.mail.backends.smtp.EmailBackend`.
- **`PasswordResetForm` do Django engole exceções de envio silenciosamente**
  (por design, pra não revelar se um e-mail tem conta ou não). A configuração
  padrão de logging do Django só manda esses erros pro console quando
  `DEBUG=True` — por isso `cashback_shopee/settings.py` tem um `LOGGING`
  customizado garantindo que erros sempre apareçam nos logs da Render, mesmo
  em produção.
- **Zoho Mail não tem mais plano gratuito** pra novos cadastros no Brasil —
  por isso o e-mail usa Cloudflare Email Routing + Brevo em vez de uma caixa
  de e-mail hospedada de verdade.
- Envio de e-mail assíncrono (numa thread separada) **não é confiável na
  Render**: o processo pode ser reciclado antes da thread terminar, e o
  e-mail simplesmente some sem nenhum log. Por isso o envio é síncrono
  (aceitando alguns segundos de espera, limitados por `EMAIL_TIMEOUT`).

## Histórico do redesign (2026-08)

O dono do produto trouxe um documento de pesquisa de UI/UX comparando a cash-b
com portais grandes de cashback/ofertas (ShopBack, Rakuten, Méliuz, Zoom, etc.)
com o objetivo de transformar a cash-b de "ferramenta de gerar link" em uma
vitrine de ofertas. Duas decisões saíram dessa conversa:

1. **Identidade visual**: foram desenhadas 3 opções (manter verde+lima, adotar
   a paleta roxo/verde/âmbar sugerida no documento, ou evoluir o verde+lima
   com um accent novo) e comparadas lado a lado num protótipo visual aplicado
   aos componentes reais do site. **Escolhida a Opção B** — paleta nova
   (roxo/verde/âmbar, ver tabela acima), o que caracteriza um rebrand
   completo: logo (só texto, recolore sozinho), favicon, ícones do PWA,
   ilustrações, e as cores usadas nos scripts de geração de imagem do
   Instagram (`instagram_bot/templates_imagem.py` e
   `marketing/instagram/gerar_posts_semeadura.py`, que duplicam os tokens em
   Python porque Pillow/Playwright não leem `brand.css` diretamente).
2. **Ordem de execução**: primeiro a base de cor (esta seção), depois a home
   vira vitrine de ofertas de verdade (ver `ROADMAP.md` pra fases seguintes:
   cashback em R$, carrossel de destaque, categorias na home, barra de
   progresso de saque).

**Correção de semântica feita junto com a troca de cor**: a paleta anterior
usava o mesmo `--highlight` (lima) tanto pro grifo `.mark` quanto pro badge de
cashback nos cards de oferta — misturava "destaque genérico" com "valor em
dinheiro". Na paleta nova isso foi separado: `--success` (verde) é sempre
dinheiro/positivo (badge de cashback, saldo liberado), `--highlight` (âmbar) é
sempre atenção/campanha. Essa mesma correção foi aplicada ao cartão "Liberado"
do painel (`accounts/templates/accounts/dashboard.html`), que antes usava
`--brand` diretamente.

## Reconciliação com a Fase 13 de CRO (2026-08-12)

Enquanto essa conversa desenvolvia o rebrand + a vitrine de ofertas numa branch
separada, outra conversa evoluía a branch de produção (`claude/shopee-cashback-site-6hb939`)
com uma "Fase 13 — Conversão e confiança (CRO)" própria (ver `ROADMAP.md`):
hero com 1 CTA primário (conversor de link embutido), nav simplificada
("Cadastrar" sólido / "Entrar" como link), timeline visual de pedido,
multiplicador de cashback de campanha e um banner de anúncio gerenciável pelo
admin. As duas branches divergiram bastante nos mesmos arquivos (`home.html`,
`dashboard.html`) sem se conhecerem.

Reconciliação feita nesta conversa: o hero/nav/timeline/multiplicador da Fase
13 (CRO) foram **mantidos como estão** — são decisões já testadas e válidas,
não faz sentido desfazer. As seções novas de descoberta (oferta em destaque,
"em alta", categorias) entraram logo abaixo do hero, no lugar do antigo banner
"quer cashback mas não sabe o que comprar?" (agora redundante, já que a
vitrine mostra ofertas de verdade). **O banner de campanha/anúncio (`paginas.Banner`)
foi removido** por decisão do dono do produto — a rotação de slides e o
gerenciamento pelo admin saíram do site; o multiplicador de cashback
(`CASHBACK_MULTIPLICADOR_CAMPANHA`) continua funcionando normalmente, só sem
uma forma de anunciar a campanha na home.

## Pra pedir ajustes de marca numa conversa nova

Basta apontar esse arquivo (`BRAND.md`) e o repositório — todas as decisões
de cor, tipografia e as armadilhas de infraestrutura já resolvidas estão
documentadas aqui. Não precisa reexplicar o histórico da conversa original.
