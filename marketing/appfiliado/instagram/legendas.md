# Instagram do Appfiliado — lançamento

Imagens geradas por `gerar_instagram.py` (rode de novo depois de mudar texto, preço ou print).
Posts do feed em `feed/<post>/`, stories dos destaques em `destaques/<destaque>/`, capas em `destaques/capas/`.
As folhas `previa-*.jpg` mostram cada post inteiro de uma vez, só para conferir (não publicar).

Tamanhos: feed em **1080x1080 (1:1)**, stories e capas dos destaques em **1080x1920**. Na capa de cada post, o
texto fica nos 810 px do meio, porque a grade do perfil mostra os posts em 3:4 e corta as laterais. Nos stories,
nada importante fica nos 250 px de cima nem nos 250 px de baixo, que o Instagram cobre.

## Perfil

- **Nome:** Appfiliado | Ferramentas para afiliados da Shopee
- **Foto:** `marketing/appfiliado/identidade/redes-sociais/avatar-amarelo-redondo-1080.png`
- **Bio:**
  ```
  O painel do afiliado da Shopee 🧡
  Bot de WhatsApp • Link na bio • Carrosséis • Notas fiscais
  Ofertas, links e resultados num lugar só
  👇 Planos a partir de R$ 19,90/mês
  ```
- **Link:** https://appfiliado.com.br (ou uma página de links com o site e o WhatsApp de vendas)
- **Categoria:** Software / Produto ou serviço
- **Botão de contato:** WhatsApp de vendas (o número do agente)

## Ordem de publicação

O Instagram mostra o último post no canto de cima à esquerda. Publique na ordem abaixo (1 primeiro) e
**fixe** os posts 1, 2 e 9, que são os que mais respondem quem chega no perfil.

| Ordem | Post | Pasta |
|---|---|---|
| 1 | Apresentação | `feed/01-apresentacao` |
| 2 | API da Shopee (passo a passo) | `feed/02-api-da-shopee` |
| 3 | Bot de WhatsApp | `feed/03-bot-de-whatsapp` |
| 4 | Meu site | `feed/04-meu-site` |
| 5 | Gerador de carrosséis | `feed/05-gerador-de-carrosseis` |
| 6 | Radar de ofertas | `feed/06-radar-de-ofertas` |
| 7 | Conversor de links | `feed/07-conversor-de-links` |
| 8 | Resultados e metas | `feed/08-resultados-e-metas` |
| 9 | Emissor NFS-e | `feed/09-emissor-nfse` |

Dá para publicar tudo no mesmo dia (perfil novo) ou 1 a 2 por dia na semana do lançamento. Os 3 fixados
ficam no topo de qualquer jeito.

## Destaques

| Destaque | Capa | Stories |
|---|---|---|
| Sobre | `destaques/capas/sobre.jpg` | `destaques/sobre/` |
| Comece aqui | `destaques/capas/comece-aqui.jpg` | `destaques/comece-aqui/` |
| Planos | `destaques/capas/planos.jpg` | `destaques/planos/` |
| Bot | `destaques/capas/bot.jpg` | `destaques/bot/` |
| Meu site | `destaques/capas/meu-site.jpg` | `destaques/meu-site/` |
| Carrosséis | `destaques/capas/carrosseis.jpg` | `destaques/carrosseis/` |
| Notas | `destaques/capas/notas.jpg` | `destaques/notas/` |
| Dúvidas | `destaques/capas/duvidas.jpg` | `destaques/duvidas/` |

Publique os stories de cada destaque (com figurinha de link pro site ou pro WhatsApp no último) e adicione
ao destaque. Deixe "Sobre" como o primeiro destaque. No story final de "Sobre", "Comece aqui" e "Planos", use a figurinha **Link** apontando pro site.

---

## Legendas

Hashtags base (use 5 a 8 por post, não precisa de todas):
`#afiliadoshopee #shopeeafiliados #afiliados #marketingdeafiliados #shopeebrasil #achadinhosdashopee #rendaextra #automacao`

### 1. Apresentação

```
Tudo que você usa como afiliado Shopee num painel só 🧡

O Appfiliado nasceu para tirar o trabalho repetitivo da rotina do afiliado:

🤖 Bot de WhatsApp: ofertas no automático nos seus grupos, sempre com o seu link
🌐 Meu site: um link na bio com vitrine e conversor de links
🖼️ Gerador de carrosséis: cole um link e receba o carrossel pronto
📊 Radar, Conversor e Resultados: incluídos em todos os planos
🧾 Emissor NFS-e: as notas da comissão extra direto do relatório da Shopee

Planos a partir de R$ 19,90/mês, com 7 dias de garantia.
👉 Link na bio

#afiliadoshopee #shopeeafiliados #marketingdeafiliados #achadinhosdashopee #rendaextra
```

### 2. API da Shopee

```
Antes de usar qualquer ferramenta de afiliado, tem um passo que muita gente não conhece: liberar a API da Shopee 🔑

É ela que gera o seu link de afiliado e traz os seus números. O pedido é feito direto à Shopee e a resposta sai em até 5 dias úteis.

Arraste pro lado para ver o passo a passo e como preencher o formulário.

💡 Dica: não espere o e-mail. Entre todo dia na página Open API do portal de afiliados. Quando aparecer o botão "Aplicar", a API foi liberada.

Salve este post para não perder 📌

#afiliadoshopee #shopeeafiliados #apishopee #marketingdeafiliados #afiliados
```

### 3. Bot de WhatsApp

```
Seus grupos de WhatsApp com ofertas da Shopee no automático 🤖

O bot escolhe as ofertas, gera o seu link de afiliado e publica nos grupos e canais que você definir, no ritmo e nos horários que você quiser.

✅ Conexão por QR Code, sem computador ligado
✅ Busca por palavra-chave, loja ou categoria
✅ Modo campanha pro 11.11 e a Black Friday
✅ Alerta de preço dos produtos que você escolher
⭐ Premium: copia ofertas de outros grupos e troca pelo seu link

A partir de R$ 49,90/mês. Comece no modo simulação, que faz tudo sem enviar nada.
👉 Link na bio

#afiliadoshopee #grupodeofertas #botwhatsapp #achadinhosdashopee #shopeeafiliados
```

### 4. Meu site

```
Um link na bio que vende por você 🌐

Com o Meu site você tem uma página em seunome.appfiliado.com.br com:

• Botões de link com os cliques de cada um
• Suas redes sociais
• Vitrine de ofertas com o seu link
• Conversor de links: o visitante cola o link e compra pelo seu

A partir de R$ 22,90/mês.
👉 Link na bio

#linknabio #afiliadoshopee #shopeeafiliados #marketingdeafiliados #achadinhosdashopee
```

### 5. Gerador de carrosséis

```
Cole um link da Shopee. O carrossel sai pronto 🖼️

O Appfiliado puxa os dados do produto, a IA escreve o roteiro dos slides, a legenda e as hashtags, e você ajusta tudo no editor e baixa as imagens já no formato do feed.

• 10 modelos
• 2 a 10 slides por carrossel
• Preço sempre certo, direto da Shopee
• Seu link de afiliado com o Sub ID "instagram"

A partir de R$ 19,90/mês.
👉 Link na bio

#carrosselinstagram #afiliadoshopee #achadinhosdashopee #shopeeafiliados #conteudo
```

### 6. Radar de ofertas

```
Ache o produto certo para divulgar em segundos 🎯

O Radar reúne mais de 30 mil produtos da Shopee com comissão de afiliado, atualizados todo dia. Filtre por comissão, desconto, preço e categoria e copie o seu link em um clique.

Vem incluído em todos os planos do Appfiliado.
👉 Link na bio

#afiliadoshopee #achadinhosdashopee #shopeeafiliados #comissao #ofertasshopee
```

### 7. Conversor de links

```
Viu uma lista de ofertas boa? Troque todos os links pelo seu em um clique 🔗

Cole a mensagem de um canal ou links soltos: o Appfiliado troca todos os links da Shopee pelo seu link de afiliado e devolve o texto pronto para encaminhar. Links curtos também funcionam.

Incluído em todos os planos.
👉 Link na bio

#afiliadoshopee #linkdeafiliado #shopeeafiliados #achadinhosdashopee #afiliados
```

### 8. Resultados e metas

```
Quanto você vendeu hoje? E de onde veio? 📊

No Appfiliado você vê faturamento, comissão e pedidos por dia, semana ou mês, descobre qual grupo, site ou post vende mais com os Sub IDs e recebe os números de ontem toda manhã por e-mail.

Agenciado? Cadastre as faixas de meta e acompanhe quanto falta pro bônus.

Incluído em todos os planos.
👉 Link na bio

#afiliadoshopee #shopeeafiliados #metas #marketingdeafiliados #resultados
```

### 9. Emissor NFS-e

```
Afiliado PJ: as notas da comissão extra em poucos cliques 🧾

Envie o Relatório Mensal da Shopee e o Appfiliado emite uma nota por loja no Emissor Nacional, com e-mail para cada vendedor com o PDF e o XML.

• Para MEI ou Simples Nacional, com certificado A1
• Comece pelo ambiente de testes do governo
• Planos pela quantidade de notas, a partir de R$ 17,90/mês

👉 Link na bio

#afiliadopj #notafiscal #nfse #afiliadoshopee #mei
```
