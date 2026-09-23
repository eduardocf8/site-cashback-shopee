# cash-b — manual de marca

Arquivo único da identidade visual da cash-b: cor, tipografia, logotipo,
elementos gráficos, formatos e o sistema de artes. Qualquer conversa nova
(ou qualquer pessoa) deve conseguir continuar o projeto apontando só para
este arquivo e o repositório.

**Fonte de verdade de cor:** `static/css/brand.css`. Os hexadecimais estão
repetidos aqui porque quem desenha precisa lê-los, mas o CSS é quem manda —
mudou lá, muda aqui junto. Três arquivos Python duplicam os mesmos tokens
porque Pillow e Playwright não leem CSS: `marketing/instagram/carrossel_base.py`,
`marketing/instagram/gerar_cards_produto.py` e `instagram_bot/templates_imagem.py`.
Trocar uma cor significa trocar nos quatro.

**Texto não está aqui.** Tom de voz, verbos e grafia ficam em `VOZ.md` —
inclusive as regras que afetam arte, como "a cash-b" (feminino) e "Pix"
(nunca "PIX").

---

## Índice

1. [A marca](#a-marca)
2. [Logotipo](#logotipo)
3. [Paleta](#paleta)
4. [Tipografia](#tipografia)
5. [Elementos gráficos](#elementos-gráficos)
6. [Formatos e áreas seguras](#formatos-e-áreas-seguras)
7. [O sistema de artes](#o-sistema-de-artes)
8. [Regras que valem em qualquer peça](#regras-que-valem-em-qualquer-peça)
9. [Onde cada coisa mora](#onde-cada-coisa-mora)
10. [Histórico do redesign](#histórico-do-redesign-2026-08)
11. [Infraestrutura ligada à marca](#infraestrutura-ligada-à-marca)

---

## A marca

**cash-b** é um site de cashback para quem compra na Shopee: a pessoa gera um
link de afiliado pelo site, compra normalmente e recebe de volta parte da
comissão que a Shopee paga.

- Domínio: **cash-b.com**
- Repositório: `eduardocf8/site-cashback-shopee`
- Branch de produção (de onde a Render faz deploy): `claude/shopee-cashback-site-6hb939`

### Como escrever o nome

- **Sempre minúsculo, sempre com hífen:** `cash-b`. Nunca "Cash-B", "CashB",
  "cash b" ou "CASH-B" — nem em título, nem em início de frase, nem em legenda.
- **Substantivo feminino:** "a cash-b", "na cash-b", "pela cash-b". A regra
  completa, com as exceções, está em `VOZ.md`.
- **Nunca deixar quebrar linha no hífen.** O navegador quebra depois de hífen,
  e em corpo grande isso vira "cash-" numa linha e "b" na outra, que lê como
  erro de digitação. Em HTML, usar a constante `MARCA` de `carrossel_base.py`
  (o nome dentro de um `white-space:nowrap`) em qualquer texto que possa
  quebrar — título, pastilha, legenda larga.

---

## Logotipo

- **Só o nome**, em minúsculo: `cash-b`. Sem ícone ao lado, sem símbolo, sem
  monograma substituindo o nome.
- Fonte: **Familjen Grotesk 700**, `letter-spacing: -0.03em`.
- **Espaço de proteção:** margem mínima em volta igual à altura do "c" minúsculo.
- **Exceção — monograma "cb":** só para espaço muito pequeno ou quadrado
  (favicon, avatar de rede social). Nunca substitui o logotipo completo em
  nenhum outro lugar.
- **Nunca o ícone "cb" e o nome "cash-b" juntos na mesma peça.** São duas
  formas do mesmo logotipo; lado a lado leem como duas marcas.

### Centro óptico

O flex centraliza a **caixa** da linha de texto, não a **tinta**. A caixa
reserva espaço de descendente embaixo (que "cash-b" não usa) e o
`letter-spacing` negativo a encolhe depois do último "b" — então o wordmark
centralizado por CSS sai visivelmente baixo e à direita.

Correção medida nos arquivos gerados: `transform: translate(-0.0147em, -0.0765em)`.
Vai em `em` e não em `px` de propósito, para valer em qualquer corpo de fonte.
Aplicada em `gerar_cards_produto.py` e `gerar_artes_marca.py`.

### Arquivos prontos

`marketing/instagram/artes-marca/` traz logotipo, monograma, lockups, capa de
YouTube e imagem de compartilhamento. Cada arte quadrada sai também numa versão
`-zoom`, com o desenho maior, para foto de perfil (que o Instagram recorta em
círculo).

`marketing/instagram/artes-marca/sem-fundo/` traz o kit recortado na tinta, com
fundo transparente — para usar sobre foto, vídeo ou material de terceiro:

| Arquivo | Quando usar |
|---|---|
| `wordmark-roxo.png` | Fundo claro. É a versão padrão |
| `wordmark-claro.png` | Fundo escuro, foto ou o roxo da marca |
| `wordmark-preto.png` | Impressão, documento sem cor |
| `cb-roxo.png` / `cb-claro.png` | Espaço pequeno ou quadrado |
| `cb-roxo-anel.png` / `cb-claro-anel.png` | Idem, com o anel âmbar da foto de perfil |

Com fundo transparente não existe versão única: a tinta precisa contrastar com
o que estiver atrás, então cada peça tem a cor de marca (fundo claro) e a clara
(fundo escuro).

---

## Paleta

Tokens em `static/css/brand.css`. Paleta atual desde o redesign de 2026-08.

| Token | Hex | Uso |
|---|---|---|
| `--ink` | `#111827` | Texto principal |
| `--ink-soft` | `#374151` | Texto secundário (labels, subtítulos) |
| `--muted` | `#6b7280` | Texto apagado (legendas, placeholders) |
| `--brand` | `#6d28d9` | Roxo — marca, wordmark, CTAs principais, links, preço |
| `--brand-strong` | `#4c1d95` | Hover e variante escura do roxo |
| `--highlight` | `#f59e0b` | Âmbar — **só** destaque/atenção: grifo `.mark`, badge de campanha/urgência ("Oferta do dia", "Cashback turbinado") |
| `--highlight-ink` | `#111827` | Texto sobre o âmbar |
| `--success` / `--success-bg` | `#059669` / `#ecfdf5` | Verde — **dinheiro**: badge de cashback nos cards, valor em R$, saldo liberado, confirmações |
| `--paper` | `#f8fafc` | Fundo principal (claro) |
| `--paper-2` | `#f1eefb` | Fundo secundário (seções alternadas, cards) |
| `--line` / `--line-soft` | `#e0dcef` / `#ede9f7` | Bordas e divisores |
| `--danger` / `--danger-bg` | `#dc2626` / `#fee2e2` | Erros, badge de desconto |
| `--info` / `--info-bg` | `#2563eb` / `#eef2ff` | Estados informativos |

Gradiente da marca, usado em capa de carrossel e painel de ilustração:
`linear-gradient(165deg, #4c1d95 0%, #6d28d9 55%, #a78bfa 100%)`.
O roxo claro `#a78bfa` não existe no `brand.css` — nasceu no sistema de
carrosséis (`BRAND_LIGHT`) para pastilhas sobre fundo escuro.

### Regra de ouro: cada cor tem um papel fixo

**Roxo é marca e ação. Verde é dinheiro. Âmbar é atenção.**

Não usar cor fora do papel — por exemplo, não usar roxo num selo de cashback só
porque "é a cor da marca". Foi exatamente essa mistura que a paleta anterior
tinha (um único "highlight" fazendo marca, atenção e dinheiro ao mesmo tempo) e
que motivou o redesign.

### Divergência conhecida, ainda não resolvida

O selo de cashback **não tem a mesma cor no site e nas artes do Instagram**:

| Onde | Cor do selo | Arquivo |
|---|---|---|
| Site, card de oferta | **verde** (`--success`) | `static/css/brand.css`, `.oferta-cartao .cashback` |
| Story de oferta do bot | **âmbar** (`highlight`) | `instagram_bot/templates_imagem.py` |
| Cards de produto do reel | **âmbar** | `marketing/instagram/gerar_cards_produto.py` |

A regra de ouro diz que verde é dinheiro, então **o site é quem está certo** e
as artes do Instagram é que fugiram do papel das cores. Os cards do reel
seguiram o story do bot por consistência com o que já existia, propagando a
divergência.

Escolher um dos dois é decisão do dono do produto, não ajuste técnico:
uniformizar em verde alinha com a regra, mas muda a cara de peças já publicadas.
Enquanto não for decidido, **fica registrado aqui para não virar precedente
silencioso**.

### Duas consequências práticas

**Âmbar nunca significa "pior".** Ele marca oportunidade — e, enquanto a
divergência acima não for resolvida, marca cashback nas peças do Instagram. Se
numa comparação o âmbar passar a marcar o lado que rende menos, a mesma cor diz
duas coisas opostas na mesma peça — e, num reel, às vezes com um minuto de
distância.

**Para marcar "menos", use cinza neutro** (`--muted`), não amarelo de semáforo.
Amarelo lê como alerta, e as opções piores da cash-b não são erro: a venda
indireta paga, só paga menos. Essa é a linha editorial decidida pelo dono do
produto no carrossel 07 — *"Todas geram cashback, porém uma delas é menor"*.
Aplicada em `gerar_tela_comparativa.py`.

---

## Tipografia

**Familjen Grotesk** (400–700) — títulos e texto corrido.
`static/fonts/familjen-grotesk.woff2`, licença OFL, sub-setada.

**JetBrains Mono** — números e dados: valores em R$, percentuais, tabelas.
Dá a sensação de extrato/recibo aos valores de cashback.
`static/fonts/jetbrains-mono.woff2`, licença OFL, sub-setada.

As duas são auto-hospedadas e sub-setadas (só os caracteres usados) para ficarem
leves — ver o histórico de commits se precisar regerar os arquivos.

A regra é simples: **todo número que representa dinheiro ou percentual vai na
mono.** Texto vai na Familjen.

### Ajustes que sempre acompanham

- Título grande: `letter-spacing` entre `-0.025em` e `-0.035em`. Sem isso a
  Familjen abre demais em corpo alto.
- Número grande na mono: `letter-spacing: -0.06em`. Na mono a vírgula ocupa a
  largura de um dígito, e acima de ~100px isso abre um buraco no meio de
  "1,6%", que passa a ler como dois números.
- Pastilha e rótulo curto: `white-space: nowrap`.

---

## Elementos gráficos

O sistema é tipográfico. Fora a tipografia, existem poucos elementos — e é
proposital.

### O grifo (`.mark`)

Retângulo âmbar atrás de uma palavra-chave, como marca-texto. Referência direta
a "destacar o dinheiro que volta". Classe `.mark` em `brand.css`.

**No máximo uma vez por página ou por peça.** É para ser um momento único, não
decoração repetida.

Em arte gerada, o grifo é `background` da própria palavra, não pseudo-elemento
atrás dela: `linear-gradient(to top, #f59e0b 0 24px, transparent 24px)`. Com
`z-index` negativo ele cai atrás de qualquer véu ou fundo irmão e some.

### A barra lateral

Bloco com borda esquerda grossa (12px) na cor do papel semântico e fundo na
mesma cor a 10% de opacidade. É o que diferencia dois blocos à distância, antes
de qualquer texto ser lido. Usado no `destaque()` dos carrosséis e na tela
comparativa.

Solto sobre vídeo, o fundo translúcido precisa ser **achatado contra branco**
(a mistura calculada, opaca) — senão a filmagem aparece através e o texto perde
contraste.

### O cartão

Base branca de quase toda arte de conteúdo:

```
background: #fff;
border-radius: 40px;        /* 56px em peça de tela cheia */
padding: 36px;              /* 64px em peça de tela cheia */
box-shadow: 0 30px 60px rgba(17,24,39,0.18);
```

No site os raios são menores: botão 8px, card 12px, badge 10px, painel 20px.
Arte de rede social usa raio maior porque é vista pequena.

### O selo de cashback

Âmbar, `border-radius: 14px`, texto em `--ink`, 700. Nos cards de produto ele é
**absoluto sobre a foto** — flutua, não ocupa espaço. É o que permite ligar e
desligar a informação de cashback sem mudar a altura do cartão.

### Ilustrações

**Sem fotografia de banco de imagens.** Todo elemento ilustrado é forma
geométrica plana (SVG) nas cores da marca — nunca com aparência de arte
genérica de IA. Dois temas em uso:

- **Cashback/moeda:** anel incompleto âmbar em volta de um círculo com "R$" —
  painéis de login/cadastro (`accounts/templates/accounts/_ilustracao_auth.html`).
- **Sacola + selo de desconto:** sacola de compras com selo circular de "%" —
  hero da home.

Ambos sobre painel com o gradiente roxo e uma mancha âmbar de baixa opacidade
ao fundo.

Fotografia de pessoa real (o dono aparecendo em reel) é exceção e não passa por
esse tratamento — ver [Capa de reel](#o-sistema-de-artes).

Para fotografia de banco de imagens, caso um dia se use: aplicar tratamento
duotone nas cores da marca antes de publicar, para não destoar do sistema. O
Claude não gera imagem nem tem acesso a banco de imagens neste ambiente —
alguém precisa fornecer o arquivo.

---

## Formatos e áreas seguras

| Peça | Quadro | Observação |
|---|---|---|
| Carrossel de feed | 420×525 no desenho, exportado a 1080×1350 | proporção 4:5 |
| Story / reel / capa | 1080×1920 | 9:16 |
| Card de produto (vídeo) | 1080×1200, cartão de 720 de largura | escala 2 no arquivo |
| Tira do carrossel de produtos | 8100×1200 (1x) ou 16200×2400 (2x) | 10 elementos |
| Destaque (capa) | 1080×1920 | recortado em círculo pelo Instagram |

### Faixas que a interface do Instagram cobre

- **Story:** ~250px no topo (foto de perfil e nome) e ~300px no pé (barra de
  resposta). Texto ali fica escondido atrás da interface.
- **Reel:** ~300px no pé (nome do perfil e legenda sobre o vídeo).
- **Grade do perfil:** recorta o centro. O que precisa sobreviver ao recorte
  fica na faixa central.

### Escala dos arquivos

Arte para vídeo sai em **escala 2** (`device_scale_factor=2`): no reel a peça
aparece grande, e ampliar um arquivo 1x na edição deixa borda e texto moles.

A exceção é a tira do carrossel de produtos, que sai também em 1x: em 2x ela
passa de 16 mil pixels de largura, acima do que muito aparelho carrega como
textura — a camada simplesmente não aparece no editor.

---

## O sistema de artes

Tudo em `marketing/instagram/`. Cada script é autônomo e documenta no próprio
docstring **por que** cada decisão foi tomada. O histórico completo do
Instagram (roadmap do bot, incidentes resolvidos, decisões de conteúdo) está em
`marketing/instagram/README.md`.

| Script | Produz |
|---|---|
| `carrossel_base.py` | Paleta, fontes e componentes compartilhados pelos carrosséis |
| `gerar_carrossel_*.py` (11) | Carrosséis de feed, numerados por ordem de criação |
| `gerar_artes_marca.py` | Logotipo, monograma, lockups, capa de YouTube, kit sem fundo |
| `gerar_destaques_instagram.py` | Capas e stories dos destaques do perfil |
| `gerar_posts_semeadura.py` | Posts institucionais de semeadura |
| `gerar_story_perguntas.py` | Fundo de story para caixa de perguntas, e o fundo das respostas |
| `gerar_cards_produto.py` | Cards de produto em dois estados + a tira do carrossel |
| `gerar_rolagem_video.py` | A rolagem da tira já renderizada, em vídeo de fundo transparente |
| `gerar_botoes_reel.py` | Botão liga/desliga (interruptor e botão redondo), dois estados |
| `gerar_tela_comparativa.py` | Tela e caixas soltas de venda direta × indireta |
| `gerar_moldura_celular.py` | Moldura de celular com a tela vazada, e fundo roxo chapado |
| `gerar_capa_reel.py` | Capa de reel: foto do vídeo achatada com a camada da marca |

### Medidas fixas que outras peças dependem

**Tira do carrossel de produtos.** Passo de um card para o outro: **780px**
(720 do card + 60 de vão). Os quadros-chave da rolagem vão de `+3510` a
`-3510` em pixels do quadro, num projeto de 1080 de largura.

**Moldura de celular.** Abertura da tela: **740×1554**, canto superior esquerdo
em (170, 183) do quadro de 1080×1920. Borda de 26px, raio 92 no corpo e 68 na
tela. A abertura é vazada de verdade (alfa 0) — a gravação entra numa camada
atrás e aparece pelo buraco.

**Capa de reel.** O escurecimento sobe do pé do quadro e para antes da altura
do rosto: é a pessoa que faz alguém parar de rolar, não a frase. Texto acima
dos 360px do pé.

---

## Regras que valem em qualquer peça

**Estados do mesmo elemento saem do mesmo tamanho.** Card com e sem cashback,
botão ligado e desligado, caixa verde e cinza: mesmas dimensões e mesma posição
dentro do arquivo. Trocar um pelo outro na edição não pode mover nem
redimensionar nada. Conferir comparando a região opaca dos arquivos.

**Fundo transparente em arte para vídeo.** `omit_background=True` no Playwright
— sem ele o PNG sai com fundo branco chapado.

**Recorte na tinta só no kit de logotipo.** Lá ele é necessário (moldura vazia
atrapalha o posicionamento). Em qualquer peça com estados, recortar justo
produziria arquivos de tamanhos diferentes e a peça pularia na troca.

**Sombra também no estado apagado.** É ela que separa a peça do fundo do vídeo.
Sem sombra, um elemento cinza claro some numa parede branca.

**A folga em volta precisa caber o brilho.** Estado aceso com `box-shadow`
espalhado exige margem suficiente no arquivo, senão o degradê sai cortado. Meta:
borda do arquivo em alfa 0.

**Conferir antes de entregar**, não confiar no olho: caixa delimitadora da
tinta, alfa nos cantos, igualdade entre estados. É barato e pega o que a
prévia pequena esconde.

---

## Onde cada coisa mora

| Caminho | O que é |
|---|---|
| `static/css/brand.css` | Tokens de cor, fontes, `.mark`, classes de ilustração |
| `static/fonts/` | Familjen Grotesk e JetBrains Mono (woff2, sub-setadas) |
| `static/favicon.svg` | Favicon com o monograma "cb" |
| `marketing/instagram/` | Sistema de artes + histórico e decisões do Instagram |
| `instagram_bot/templates_imagem.py` | Imagens geradas em tempo de execução pelo bot (Pillow) |
| `accounts/templates/accounts/base.html` | Layout das páginas de conta |
| `accounts/templates/accounts/_campo_formulario.html` | Campo de formulário padrão |
| `accounts/templates/accounts/_ilustracao_auth.html` | Ilustração dos painéis de autenticação |
| `links/templates/links/home.html` | Home (HTML/CSS próprio, não usa `base.html`) |
| `accounts/templates/accounts/dashboard.html` | Painel (HTML/CSS próprio) |
| `paginas/templates/paginas/links.html` | Página `/bio/`, o link da bio do Instagram |
| `VOZ.md` | Tom de voz e grafia — texto, não imagem |

---

## Histórico do redesign (2026-08)

O dono do produto trouxe um documento de pesquisa de UI/UX comparando a cash-b
com portais grandes de cashback e ofertas (ShopBack, Rakuten, Méliuz, Zoom),
com o objetivo de transformar a cash-b de "ferramenta de gerar link" em vitrine
de ofertas. Duas decisões saíram dali:

1. **Identidade visual.** Foram desenhadas 3 opções (manter verde+lima, adotar
   a paleta roxo/verde/âmbar sugerida no documento, ou evoluir o verde+lima com
   um accent novo) e comparadas lado a lado num protótipo aplicado aos
   componentes reais do site. **Escolhida a Opção B** — paleta nova, o que
   caracteriza rebrand completo: logo, favicon, ícones do PWA, ilustrações e as
   cores dos scripts de geração de imagem.
2. **Ordem de execução.** Primeiro a base de cor, depois a home virando vitrine
   de verdade (ver `ROADMAP.md`).

**Correção de semântica feita junto com a troca de cor:** a paleta anterior
usava o mesmo `--highlight` (lima) tanto no grifo `.mark` quanto no badge de
cashback — misturava "destaque genérico" com "valor em dinheiro". Na paleta
nova isso foi separado: verde é sempre dinheiro, âmbar é sempre atenção.

### Reconciliação com a Fase 13 de CRO (2026-08-12)

Enquanto o rebrand e a vitrine eram desenvolvidos numa branch, outra conversa
evoluía a produção com uma "Fase 13 — Conversão e confiança (CRO)" própria:
hero com 1 CTA primário (conversor de link embutido), nav simplificada, timeline
visual de pedido, multiplicador de cashback de campanha e banner gerenciável
pelo admin. As duas branches divergiram nos mesmos arquivos sem se conhecerem.

Resolução: o hero/nav/timeline/multiplicador da Fase 13 foram **mantidos** — são
decisões já testadas. As seções de descoberta (oferta em destaque, "em alta",
categorias) entraram abaixo do hero. **O banner (`paginas.Banner`) foi removido**
por decisão do dono do produto; o multiplicador continua funcionando, só sem
forma de anunciar a campanha na home.

---

## Infraestrutura ligada à marca

Não é identidade visual, mas está aqui por histórico — são as armadilhas já
resolvidas em volta do domínio e do e-mail da marca.

- **Domínio:** `cash-b.com`, registrado no Namecheap, DNS na **Cloudflare**.
- **Site:** hospedado na **Render** (plano gratuito), deploy automático a
  partir da branch de produção.
- **E-mail:** `contato@cash-b.com` **recebe** via Cloudflare Email Routing,
  encaminhando para o Gmail do dono. **Enviar como** é feito via SMTP do Brevo
  no Gmail. O site (Django) manda e-mail pela **API HTTP do Brevo**
  (`cashback_shopee/brevo_email_backend.py`), não por SMTP.

### Não repetir

- **A Render bloqueia SMTP de saída** (porta 587). E-mail transacional do Django
  tem que ser por API HTTP, nunca `smtp.EmailBackend`.
- **`PasswordResetForm` engole exceções de envio** por design. Por isso
  `settings.py` tem `LOGGING` customizado, garantindo que o erro apareça nos
  logs da Render mesmo com `DEBUG=False`.
- **Envio assíncrono em thread não é confiável na Render:** o processo pode ser
  reciclado antes da thread terminar e o e-mail some sem log. Envio é síncrono,
  limitado por `EMAIL_TIMEOUT`.
- **Zoho Mail não tem mais plano gratuito** para novos cadastros no Brasil —
  daí a combinação Cloudflare + Brevo.

---

## Para pedir ajustes de marca numa conversa nova

Aponte este arquivo e o repositório. Todas as decisões de cor, tipografia,
formato e as armadilhas já resolvidas estão aqui — não precisa reexplicar o
histórico. Para ajuste de texto, aponte `VOZ.md` junto.
