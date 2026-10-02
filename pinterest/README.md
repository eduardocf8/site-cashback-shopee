# Pinterest

Caminho A do plano de 30/09/2026: planilha semanal pro "Importar conteúdo" do
Pinterest. Nada é publicado sozinho — o dono sobe o arquivo e confere.

## Toda semana

1. Logado como staff, abrir `https://cash-b.com/pinterest/planilha.csv`
   (ou, no Shell do Render: `python manage.py gerar_planilha_pinterest > pins.csv`).
2. No Pinterest (conta business, desktop): Criar → Importar conteúdo → subir o CSV.
3. Conferir a prévia e agendar.

A planilha traz 14 Pins, um por categoria mais vendida, dois por dia (12h e 20h de
Brasília) a partir do dia seguinte. A arte de cada Pin é gerada no primeiro acesso à
"Media URL" (normalmente o do próprio Pinterest na importação) e fica guardada em
`MEDIA_ROOT/pinterest/`.

## Antes do primeiro upload

- **Conferir as colunas** com o modelo que o painel oferece para baixar. As de
  `COLUNAS_CSV` em `services.py` vêm de fonte secundária; se o modelo for diferente, é
  só ali que muda. Idem o formato de "Publish date" (hoje em UTC,
  `AAAA-MM-DDTHH:MM:SS`).
- **Criar os boards** com o nome exato de `PINTEREST_NOME_BOARD`
  (padrão "Ofertas de {categoria} na Shopee"), ou trocar a variável de ambiente.
- `MEDIA_ROOT` precisa estar no disco persistente do Render, senão a arte é refeita a
  cada deploy (continua funcionando, só baixa as fotos de novo).

## Decisões embutidas

- **Link:** página da categoria na cash-b com `utm_source=pinterest`, nunca o link
  curto da Shopee. A tag nativa de produto Shopee só existe no app do Pinterest; não
  entra em planilha.
- **Sem preço na arte:** preço de Shopee envelhece em dias; um Pin circula por meses.
- **Divulgação:** toda descrição termina com "Contém link de afiliado."

## Medindo

Cadastro que chega com `utm_source` grava a origem no `User` (primeiro toque, ver
`accounts/middleware.py`). Para ver o funil só de quem veio do Pinterest:

    python manage.py funil_cadastros --origem pinterest

## Registro do teste manual (passo 0)

Comparação entre Pin que leva para a cash-b e Pin com a marcação nativa da Shopee.
Conferir os cliques de cada grupo em Análises, no Pinterest, 3 a 4 semanas depois.

| Data de envio | Pins | Destino |
|---|---|---|
| 30/09/2026 | 5 tipográficos: Casa e decoração, Beleza, Celular e acessórios, Moda feminina, Esporte e ar livre (`marketing/pinterest/pins-teste/`) | Página da categoria na cash-b, `utm_source=pinterest` |
| 01/10/2026 | 5 com foto do produto e "Marcar produtos": 01 (produto não informado), 02 mop spray com reservatório (Casa e Decoração), 03 ventilador de teto com luminária (Eletrodomésticos), 04 kit 7 saquinhos maternidade (Mãe e Bebê), 05 legging com cinta modeladora (Roupas Femininas) | Tag nativa da Shopee, sem link de destino |
