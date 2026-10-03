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
npm run studio            # abre o editor visual, para ajustar tempo e ver ao vivo
npm run render            # versão calma  -> saida/cash-b-apresentacao.mp4
npm run render:dinamica   # versão com mais movimento -> saida/cash-b-apresentacao-dinamica.mp4
npm run render:espera     # calma com o gancho "Espera." -> saida/cash-b-apresentacao-espera.mp4
npm run render:animada    # a de mais movimento -> saida/cash-b-espera-animada.mp4
python3 exportar_dados_campanha.py   # antes: atualiza os números da campanha 10.10
npm run render:campanha   # reel 10.10 A (objetos), 18 s -> saida/cash-b-campanha-10-10.mp4
npm run render:campanha-b # reel 10.10 B (gravação de tela) -> saida/cash-b-campanha-10-10-b.mp4
```

`saida/` fica fora do git. Os dois vídeos prontos para baixar e postar estão em
[`videos/`](videos/) — ver o README de lá para saber quando copiar um render para
essa pasta.

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
| `src/Apresentacao.tsx` | Versão calma: monta as cenas em `<Sequence>` |
| `src/Dinamica.tsx` | Versão dinâmica: cenas que se empurram, fundo em zoom, números contando |
| `src/animada/` | A versão animada: `elementos.tsx` (moeda, raios, barras, marcas), `transicoes.tsx` (as seis transições), `cenas.tsx` (as sete cenas) e `EsperaAnimada.tsx` (a linha do tempo) |
| `src/campanha/` | Os dois reels da campanha 10.10 (18 s cada). A (`Campanha1010`): calendário, letreiro, recibo, relógio, fundos de cor chapada. B (`CampanhaRolagem`): gravação de tela, uma rolagem contínua por telas de app, com dedo tocando. Linguagem visual diferente entre si e da do "Espera", de propósito. Os números vêm de `dados.json`, gerado por `exportar_dados_campanha.py` |
| `src/Minimo.tsx` | A cena de dois tempos do piso de cashback |
| `src/Fechamento.tsx` | O fechamento em dois tempos da assinatura |
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

## As duas versões

| Composição | Duração | Para quê |
|---|---|---|
| `Apresentacao` | 18,3s | Corte seco entre cenas, quadro parado, números prontos |
| `EsperaAnimada` | 20,5s | Mesmas informações, com seis transições, a moeda da marca em voo (nascida da palavra "dinheiro") e números que contam e rolam. O fechamento é o da versão calma. Ver `src/animada/` |
| `ApresentacaoEspera` | 18,4s | A calma com outro gancho em dois tempos ("Vai comprar na Shopee?" ... "Espera." aos 0,9s); as demais cenas são as mesmas |
| `Dinamica` | 15,8s | As cenas se empurram, o fundo dá zoom lento, os números contam |

**As duas leem os mesmos textos e os mesmos números de `constantes.ts`.** Só o tempo de
cada cena é próprio de cada uma — é por isso que dá para manter as duas sem elas
divergirem: corrigir uma frase corrige nos dois vídeos.

Na dinâmica, o conteúdo **viaja junto com o quadro** em vez de entrar depois que ele
para. A primeira tentativa fazia o contrário, e o resultado era meio segundo de tela sem
texto a cada troca — oito vezes num vídeo de quinze segundos, que é exatamente o buraco
em que o polegar rola. Por isso ela desliga a entrada individual de cada elemento (o
contexto `SemEntrada`, em `Base.tsx`): o empurrão é a entrada.

O que deliberadamente **não** entrou na dinâmica: partícula, brilho, tremor de câmera,
giro de texto e transição de *glitch*. Todos aumentam movimento e todos custam a mesma
coisa — a peça passa a parecer template, e um produto que guarda dinheiro do usuário não
pode parecer template.

## O roteiro da apresentação

18 segundos na versão calma, 8 cenas. As três primeiras são **uma frase cortada em
três** — e a ordem importa: a condição ("comprando pela cash-b") vem antes da promessa
("parte do dinheiro volta"). Separada, a terceira cena sozinha seria uma afirmação
falsa.

A cena do `1%` tem dois tempos. Primeiro o piso da venda **indireta**, que vale para
qualquer compra; depois a frase some, sobra a palavra "mínimo", que sobe e vira o rótulo
do número, e o 1% dá lugar ao **1,6%** da venda direta, com "dependendo da forma que você
compra" embaixo. O número subir na tela é a própria frase: o mínimo sobe. Logo depois vem
"muitas vezes, bem mais", que existe para nenhum dos dois pisos ser lido como teto.

Cada cena destaca no máximo uma palavra, e **os mecanismos nunca se repetem**: a cor
varre "cashback", uma barra cresce atrás de "cash-b,", "volta" chega de fora depois do
resto da frase, "bem mais" cresce. A cor é sempre âmbar — trocá-la a cada cena faria
procurar significado onde não há. O que varia é como a ênfase funciona.

A cena do saque vira para o fundo claro de propósito: a troca de cor marca a passagem de
"promete" para "mostra". Todo site de cashback promete; o que separa é mostrar como o
dinheiro sai.

O fechamento usa o fundo `06-halo`, o único da família em que o miolo não fica vazio -
ele existe para emoldurar, que é o que uma assinatura pede.
