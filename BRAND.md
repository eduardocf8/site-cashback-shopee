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

Definida como CSS custom properties em `static/css/brand.css`:

| Token | Hex | Uso |
|---|---|---|
| `--ink` | `#12211a` | Texto principal |
| `--ink-soft` | `#3c4a41` | Texto secundário (labels, subtítulos) |
| `--muted` | `#667069` | Texto apagado (legendas, placeholders) |
| `--brand` | `#1b5e44` | Cor da marca — botões, links, wordmark |
| `--brand-strong` | `#123e2d` | Hover/variante escura da cor de marca |
| `--highlight` | `#d8ff5e` | Lima — o "marcador de destaque", ver abaixo |
| `--highlight-ink` | `#12211a` | Texto sobre o destaque lima |
| `--paper` | `#f6f7f1` | Fundo principal (claro) |
| `--paper-2` | `#eef1e8` | Fundo secundário (seções alternadas, cards) |
| `--line` / `--line-soft` | `#cdd6c5` / `#e2e6dc` | Bordas e divisores |
| `--danger` / `--danger-bg` | `#b23b3b` / `#fdecea` | Erros |
| `--info` / `--info-bg` | `#1a6fb0` / `#e8f2fa` | Estados informativos (ex: status "validado") |
| `--success` / `--success-bg` | `#1b5e44` / `#e3f3ea` | Estados de sucesso (ex: status "liberado") |

**Regra de ouro**: o lima (`--highlight`) é a única cor de destaque forte do
sistema — usar no máximo **uma vez por página**, nunca espalhado.

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

Um retângulo lima atrás de uma palavra-chave, tipo grifo de marca-texto —
referência direta ao conceito de "destacar o dinheiro que volta". É o único
elemento gráfico do sistema além da tipografia. Implementado pela classe
`.mark` em `static/css/brand.css`. Exemplo de uso: o "de volta" no título da
home (`links/templates/links/home.html`).

**Regra**: usar no máximo uma vez por página — é pra ser um momento único,
não decoração repetida.

## Ilustrações

**Sem fotografia.** Todo elemento visual do sistema é forma geométrica plana
(SVG), nas cores da marca — nunca fica com aparência de arte genérica de IA.
Dois temas usados até agora:

- **Cashback/moeda**: um anel incompleto em lima ao redor de um círculo com
  "R$" — usado nos painéis de login/cadastro/recuperação de senha
  (`accounts/templates/accounts/_ilustracao_auth.html`).
- **Sacola + selo de desconto**: uma sacola de compras com um selo circular
  de "%" no canto — usado no hero da home (`links/templates/links/home.html`).

Ambos ficam sobre um painel com gradiente `--brand-strong` → `--brand`, com
uma "mancha" (blob) orgânica em lima ao fundo, baixa opacidade.

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
- `marketing/instagram/` — histórico e decisões do Instagram do cash-b
  (roadmap do bot de postagens, posts institucionais já aprovados, script
  que gera as artes). Ver `marketing/instagram/README.md`.

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

## Pra pedir ajustes de marca numa conversa nova

Basta apontar esse arquivo (`BRAND.md`) e o repositório — todas as decisões
de cor, tipografia e as armadilhas de infraestrutura já resolvidas estão
documentadas aqui. Não precisa reexplicar o histórico da conversa original.
