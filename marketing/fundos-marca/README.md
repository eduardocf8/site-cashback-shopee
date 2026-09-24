# Fundos da marca

Plano de fundo abstrato da cash-b, para qualquer peça que precise de uma base
com cara da marca e o miolo livre para texto: banner de e-mail, capa de reel,
story, carrossel, avatar.

São 48 arquivos — 6 composições × 2 cores × 4 formatos. **Nenhum deles é
editado à mão:** todos saem de `../gerar_fundos_marca.py`. Mexer no PNG faz o
ajuste sumir na próxima vez que alguém rodar o script.

```
python3 marketing/gerar_fundos_marca.py
```

## Como o nome do arquivo é montado

```
fundo-03-canto-roxo-9x16.png
      └──┬──┘ └┬─┘ └┬──┘
    composição cor formato
```

Escolher um fundo é responder três perguntas, nessa ordem: **qual formato a
peça tem**, **que tipo de peça é** e **sobre qual cor o texto vai**.

## 1. Formato — a proporção do quadro

| Sufixo | Tamanho | Onde usar |
|---|---|---|
| `16x9` | 1536×864 | Banner de e-mail (comunicação em massa do admin) |
| `4x5` | 1080×1350 | Post e carrossel do feed do Instagram |
| `9x16` | 1080×1920 | Story, capa de reel, capa de destaque |
| `1x1` | 1080×1080 | Avatar, miniatura, thumbnail |

Cada formato é **redesenhado**, não recortado — a mancha cai no mesmo canto em
todos eles. Por isso nunca recorte um arquivo de um formato para virar outro:
pegue o arquivo do formato certo. Recortando, a mancha ou os arcos saem fora
dependendo de onde o corte cair.

Precisa de um formato que não está aqui? É uma linha em `FORMATOS`, no script.

## 2. Composição — o papel de cada uma

| Arquivo | Desenho | Quando usar |
|---|---|---|
| `01-manchas` | Duas manchas em cantos opostos + arcos no alto | Peça curta e solta: um aviso, um story de recado |
| `02-ondas` | Só arcos, sem mancha cheia | Peça com muito texto — é o mais silencioso |
| `03-canto` | Mancha grande embaixo à esquerda + arcos no alto à direita | **Padrão.** Use este quando não houver motivo para outro |
| `04-moldura` | Manchas nos quatro cantos, miolo totalmente limpo | Texto centralizado, que pede simetria |
| `05-diagonal` | Elipse larga atravessando o quadro inclinada | Campanha e data dupla — o de mais energia |
| `06-halo` | Arcos concêntricos no centro | Fechamento e assinatura |

Duas ressalvas que valem a pena saber:

- **O `06-halo` é a exceção da família:** o centro dele *não* fica vazio, porque
  ele existe para emoldurar. Serve quando o meio leva a marca ou uma frase
  curta — nunca um bloco de texto, que ficaria por cima dos arcos.
- **O `03-canto` no formato `4x5` com muita lista** é o limite do conjunto: as
  caixas de baixo entram na área da mancha. Continua legível (a mancha é roxo
  claro sobre roxo), mas nesse caso a versão `claro` respira melhor.

## 3. Cor — sobre o que o texto vai

| Sufixo | O que é | Texto por cima |
|---|---|---|
| `roxo` | Gradiente `--brand-strong` → `--brand` | Branco, com a palavra-chave em âmbar |
| `claro` | `--paper` com as formas em lilás | `--ink`, com a palavra-chave em roxo |

Numa sequência (um carrossel, uma série de stories respondendo perguntas),
**mantenha a mesma cor do começo ao fim**. Alternar roxo e claro no meio quebra
a leitura de "isto tudo é a mesma conversa", que é justamente o que o fundo
repetido está construindo.

## A regra da família

Se um dia alguém criar uma composição nova, é isto que a mantém parecendo a
mesma marca:

- **Só dois elementos:** mancha arredondada e arco fino. Nada mais.
- **Tudo sangra pela borda.** Forma inteira e centralizada lê como adesivo;
  forma cortada pela borda lê como recorte de um sistema maior.
- **O miolo fica vazio** — é onde o texto cai, e é o que diferencia fundo de
  ilustração.
- **Monocromático, só roxo.** Sem âmbar: num fundo ele competiria com o
  destaque do próprio texto que vai por cima, e é o texto que precisa da cor de
  atenção.

A versão completa, com paleta, tipografia e o resto do sistema, está em
[`BRAND.md`](../../BRAND.md) na raiz do repositório.
