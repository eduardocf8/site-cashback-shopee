# Vídeos da marca com Remotion

Projeto Remotion para os vídeos **gerados** da cash-b: vinheta, apresentação, card
animado. O que é filmagem — você na câmera, corte de cena, áudio — continua no editor
de vídeo; aqui fica o que nasce de dado e de tipografia.

O ganho é o mesmo dos outros geradores: o vídeo sai com a cor exata da marca, com os
números reais do site, e o mesmo comando produz sempre o mesmo arquivo.

## Rodar

```bash
cd marketing/remotion
npm install
npm run render     # gera saida/apresentacao.mp4
npm run studio     # abre o editor visual, para ajustar tempo e ver ao vivo
```

**A flag `--browser-executable` do script `render` não é opcional.** O Remotion tenta
abrir o Chrome no modo headless antigo, que foi removido do binário; o ambiente tem um
`chrome-headless-shell` separado e é para ele que a flag aponta. Sem ela o render quebra
com "Old Headless mode has been removed".

## Onde mexer

| Arquivo | O que é |
|---|---|
| `src/constantes.ts` | **Todo o texto e todo o número.** É aqui que se faz variação |
| `src/marca.ts` | Paleta, fontes e a faixa segura do Instagram |
| `src/Base.tsx` | Cena, entrada animada, título, número e linha de apoio |
| `src/Apresentacao.tsx` | Monta as cenas em `<Sequence>` |
| `public/` | Fundos, logo e as fontes |

Para um vídeo com outra mensagem, mexa só em `constantes.ts`. Os componentes não têm
texto escrito dentro deles de propósito.

## Regras deste projeto

- **Animação só com `useCurrentFrame()`, `interpolate()` e `spring()`.** Sem
  `animation` nem `transition` de CSS: o render é quadro a quadro, e CSS animation não
  sabe em que quadro está.
- **Nada de `Math.random()` sem semente nem `Date.now()`.** Cada quadro é renderizado
  separadamente; valor que muda a cada chamada faz o vídeo tremer.
- **Nada legível fora da faixa y 285–1635.** É o que sobra do quadro 9:16 depois do
  recorte 4:5 do feed. O player ainda cobre os ~300px de baixo.
- **Os números saem de `settings.py`**, não de estimativa: cashback mínimo de 1% na
  venda indireta, saque a partir de R$ 20. Ver `constantes.ts`.
- **Nenhum elemento visual da Shopee.** A cash-b é afiliada independente; o nome pode
  ser dito como texto, a marca dela não pode aparecer.
- **O nome da marca é sempre minúsculo**, inclusive em cena de caixa alta. Ver
  `BRAND.md`.

## O roteiro da apresentação

15 segundos, 8 cenas. As três primeiras são **uma frase cortada em três** — e a ordem
importa: a condição ("comprando pela cash-b") vem antes da promessa ("parte do dinheiro
volta"). Separada, a terceira cena sozinha seria uma afirmação falsa.

A cena do `1%` mostra o piso da venda **indireta**, não o 1,6% da direta: o 1,6% exigiria
explicar a diferença entre as duas, e isso não cabe em quinze segundos. Logo depois vem
"muitas vezes, bem mais", que existe para o piso não ser lido como teto.

A cena do saque vira para o fundo claro de propósito: a troca de cor marca a passagem de
"promete" para "mostra". Todo site de cashback promete; o que separa é mostrar como o
dinheiro sai.

O fechamento usa o fundo `06-halo`, o único da família em que o miolo não fica vazio -
ele existe para emoldurar, que é o que uma assinatura pede.
