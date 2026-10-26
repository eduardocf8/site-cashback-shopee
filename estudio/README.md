# Estúdio de posts

Editor de posts e stories do Instagram dentro do admin, um para cada marca:

- **Appfiliado:** admin › 📱 Appfiliado › 🎨 Estúdio de posts
- **cash-b:** admin › 🛒 Site Cash-B › 🎨 Estúdio de posts

## Como funciona

- **Começar:** do zero, de um modelo (`modelos/<marca>.json`) ou com a IA ("Criar ou ajustar com IA").
- **Formatos:** post 1:1 (1080x1080), post 4:5 (1080x1350) e story (1080x1920).
- **Cada slide** tem um tipo, os textos, o fundo e os ajustes.
  - Fundo: cor da marca, arte da família de fundos ou imagem enviada, com véu.
  - Ajustes: tamanho do título e do texto, margens, alinhamento e posição do texto.
  - No feed, qualquer slide pode ser marcado como capa. A capa usa as margens que cabem no recorte 3:4 da grade do perfil.
- **Destaque:** palavra entre asteriscos (`*assim*`).
- **Margens de segurança:** o editor mostra as linhas e avisa na hora quando um texto sai da área segura, entra nas faixas que o Instagram cobre no story, encosta no rodapé ou fica com letra menor que 26 px.
- **Baixar:** "Baixar slide" (PNG) ou "Baixar tudo" (ZIP com os PNGs e a legenda). A imagem é gerada no navegador, a partir do mesmo HTML da prévia.

## Onde está cada coisa

| Arquivo | O que faz |
|---|---|
| `static/estudio/marca-appfiliado.js` | Desenho dos slides do Appfiliado. Mesmo visual de `marketing/appfiliado/instagram/gerar_instagram.py`. |
| `static/estudio/marca-cashb.js` | Desenho dos slides da cash-b. Segue o `BRAND.md` e `marketing/instagram/carrossel_base.py`; os fundos são os de `marketing/gerar_fundos_marca.py`. |
| `static/estudio/estudio.js` | O editor: lista, prévia, campos, checagem de margens, exportação, IA e salvamento. |
| `marcas.py` | Tipos de slide, campos, cores, artes, ícones e prints de cada marca. É o que o servidor aceita. |
| `ia.py` | A IA (Claude, `ESTUDIO_MODELO`). O prompt inclui o `VOZ.md` e o material do site de cada marca; `limpar()` só deixa passar o que o editor conhece. |
| `modelos/*.json` | Modelos iniciais. Os do Appfiliado vêm dos posts e destaques publicados. |

Mudou uma cor ou um tamanho nas artes de `marketing/`? Mude também no `marca-*.js` correspondente.

## Estúdio Instagram (painel do afiliado)

O mesmo editor, dentro do painel, para o afiliado fazer os posts dele. Está **em teste**: só aparece
para a conta com "testa o Estúdio Instagram" marcado no admin (Contas do Appfiliado). Para as outras,
o item do menu some e todas as páginas respondem 404.

- **Criar:** do link de um produto da Shopee (a IA escreve; sem IA, sai do modelo de produto com a foto
  e o preço), de um modelo, com um pedido para a IA ou em branco. A IA gasta o mesmo limite do dia do
  gerador de carrosséis e usa `ESTUDIO_MODELO_AFILIADOS`.
- **Preço e foto** vêm sempre dos dados da Shopee (`afiliados.com_produto`): a IA não escreve valores.
- **Standard** (modo "simples"): edita textos e a foto, reordena e apaga slides. Cores e fundos vêm do modelo.
- **Premium** (modo "completo"): tudo do estúdio do admin, mais as cores, a fonte e o logo da Minha marca.
- **Imagens** (fotos enviadas, logo e miniaturas) ficam no banco, como no resto do painel.

| Arquivo | O que faz |
|---|---|
| `static/estudio/marca-afiliado.js` | Desenho dos slides do afiliado: temas do gerador de carrosséis ou a Minha marca, com contraste calculado por slide. |
| `afiliados.py` | Regras de plano, criar post, limite da IA, imagens e Minha marca. |
| `modelos/afiliado.json` | Modelos dos afiliados (`"produto": true` recebe a foto e o preço do produto). |
| `painel/views_estudio.py` | As telas do painel. |
