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

## Appfiliado: vídeo das funcionalidades

Em `src/appfiliado/`: gancho, uma cena por ferramenta (Bot, Radar, Conversor, Carrosséis, Meu site,
Resultados e metas, Emissor NFS-e) e o fechamento, com as telas do painel recriadas em React e o uso
simulado (cursor, digitação, ofertas chegando no grupo, números contando). Texto na tela e sem voz, pra
os creators gravarem por cima. O mesmo vídeo sai em três formatos:

```bash
npm run render:appfiliado-vertical    # 9:16 (Reels, TikTok, stories) -> saida/appfiliado-vertical.mp4
npm run render:appfiliado-retrato     # 4:5 (feed e anúncios)         -> saida/appfiliado-retrato.mp4
npm run render:appfiliado-horizontal  # 16:9 (YouTube, site)          -> saida/appfiliado-horizontal.mp4
```

Textos e duração de cada cena ficam em `FERRAMENTAS` (`src/appfiliado/Video.tsx`); as demonstrações, em
`src/appfiliado/cenas.tsx`. As fotos de produto são as mesmas dos prints do site (`public/appfiliado/produtos/`).

## Appfiliado: vídeos de divulgação por tema

Em `src/divulgacao/`: vídeos curtos (9:16, sem áudio) para Reels, TikTok e Status, cada um mostrando uma
coisa só, mais um completo do Bot. São 4 temas com 2 a 5 versões:

| Tema | Composição | A ideia |
|---|---|---|
| Bot de WhatsApp | `Bot-AntesDepois` | Os 5 passos de postar na mão (e o tempo indo embora) contra um botão que liga tudo |
| | `Bot-UmDiaNoAutomatico` | O relógio vai das 8h às 22h; o grupo recebe ofertas enquanto você vive o seu dia |
| | `Bot-DatasDaShopee` | O modo campanha: as datas já marcadas, o ritmo e o texto que mudam sozinhos |
| | `Bot-GruposCheios` | O link de entrada (um link só pra todos os grupos), a lotação dos grupos e o próximo grupo criado sozinho (Premium) |
| | `Bot-Completo` | Os 13 recursos do Bot em menos de 1 minuto, com a barra de progresso no topo |
| Meu site | `Site-MonteOSeu` | O link na bio se montando no celular na ordem real da página: perfil, botões, redes, conversor e vitrine |
| | `Site-DoStoryAoClique` | O caminho do seguidor, do story até a compra pelo seu link (pela vitrine e pelo conversor) |
| Resultados e metas | `Resultados-QuantoFalta` | A meta do mês, quanto falta pra faixa do bônus e a Lia respondendo "metas" |
| | `Resultados-QualGrupoVende` | O grupo que mais vende, o horário mais forte e de onde veio cada venda |
| Radar e Conversor | `Radar-AcheOProduto` | Da busca ao "copiar link" |
| | `Conversor-ColeEConverta` | A mensagem de outro grupo com os links trocados pelos seus |

```bash
npx remotion render src/index.ts Bot-AntesDepois saida/Bot-AntesDepois.mp4 \
  --browser-executable=/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell
```

Para revisar sem renderizar o vídeo inteiro, `node qa-quadros.mjs <pasta> <id>:todos` salva um quadro por
segundo (ou `<id>:30,90,150` para quadros escolhidos) em PNG.

Onde mexer:

| Arquivo | O que é |
|---|---|
| `src/divulgacao/textos.ts` | Preços (do plano Standard, iguais a `landing/planos.py`), as ferramentas inclusas, o endereço e as ofertas fictícias |
| `src/divulgacao/comum.tsx` | As peças: fundo, título palavra por palavra, cabeçalho, celular, conversa do WhatsApp, legendas, toque na tela, cortina e encerramento |
| `src/divulgacao/botTelas.tsx` | As telas do Bot: página do link de entrada, convite, grupos do link, membros, criação do próximo grupo |
| `src/divulgacao/bot.tsx`, `botGrupos.tsx`, `botCompleto.tsx`, `site.tsx`, `resultados.tsx`, `ferramentas.tsx` | Um arquivo por vídeo ou tema, com o roteiro e o tempo de cada versão |
| `src/divulgacao/Composicoes.tsx` | A lista dos vídeos registrados |

Regras de layout destes vídeos:

- **Legenda é um balão por vez, centralizado** (`Legendas`): cada um sai antes do próximo entrar. Nada de
  etiqueta solta em cima do celular ou de lado.
- Cena com celular: título em `POS.titulo`, celular em `POS.celular` e legenda em `POS.legenda`. Cena com
  cartão: o cartão no meio da área (`Painel centro`) e a legenda embaixo.
- Toda troca de cena passa pela cortina (ou, no completo, um capítulo sai antes do outro entrar): nunca
  tela vazia e nunca duas cenas misturadas.
- O encerramento dos módulos pagos mostra o preço e as ferramentas que vêm em todos os planos (`INCLUSOS`).

Os vídeos só mostram o que já está no ar, com uma exceção: o `Bot-GruposCheios` (e os capítulos 10 e 12 do completo)
mostra o link de entrada, que ainda está liberado só para contas de teste (`beta_link_entrada`). Publique esses
dois depois de liberar o link de entrada para todos. O Estúdio e as Automações do Instagram ficam de fora até o
lançamento. Quando o preço mudar em `landing/planos.py`, mude também em `textos.ts` e renderize de novo.
