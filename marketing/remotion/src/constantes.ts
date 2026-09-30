/** Todo o texto e todos os números do vídeo, num lugar só.
 *
 * É daqui que saem as variações: para um vídeo com outra mensagem, mexe-se neste
 * arquivo e nada mais. Os números NÃO são arredondados nem inventados - saem de
 * cashback_shopee/settings.py (CASHBACK_MINIMO_VENDA_INDIRETA e SAQUE_VALOR_MINIMO).
 *
 * Regras de voz aplicadas (VOZ.md): cashback afirmativo ("volta", nunca "pode voltar"),
 * "você" e não "tu", a cash-b no feminino, e o nome sempre minúsculo - inclusive onde a
 * cena usa caixa alta. */
export const FPS = 30;

/** As cenas 2 e 3 são UMA frase cortada em duas. A ordem importa: a condição
 * ("comprando pela cash-b") vem antes da promessa ("parte do dinheiro volta"). Invertida
 * ou separada, a última cena sozinha viraria uma afirmação falsa.
 *
 * O   é espaço que não quebra. Sem ele a última palavra cai sozinha numa linha, e
 * palavra órfã em corpo de cartaz lê como erro de diagramação. */
export const CENAS = [
  {
    id: 'compra',
    frames: 72,
    // Quatro linhas, e cada quebra cai numa fronteira de sentido: a frase são duas
    // orações ("você já compra na Shopee" / "e ainda não recebe cashback?"), e cada uma
    // se parte em duas. Quebrar à mão em vez de deixar o navegador embrulhar é o que
    // permite o corpo maior: embrulhando sozinha, a linha mais longa era "Você já
    // compra na Shopee", com 24 caracteres, e ela é que travava o tamanho em 82px.
    // Terminar em "cashback?" sozinho é de propósito - é a palavra que o vídeo vende.
    // O * marca a palavra que ganha ênfase. Ver TipoDestaque, em Base.tsx.
    texto: 'Você já compra\nna Shopee\ne ainda não recebe\n*cashback*?',
    // É o gancho: continua sendo a tela mais longa do vídeo e a que fica mais tempo.
    corpo: 114,
    // Entra inteira e calma. É a pergunta que monta o problema; quatro linhas
    // entrando uma a uma aqui atrasariam a leitura logo no primeiro segundo.
    entrada: 'sobe',
    // A palavra já está escrita em branco; o que chega depois é a tinta.
    destaque: {tipo: 'pintura', inicio: 24},
  },
  // As duas entram deslizando do mesmo lado: é o que mantém a frase inteira. Ver o
  // comentário do tipo Entrada, em Base.tsx.
  {
    id: 'condicao',
    frames: 48,
    // A vírgula entra no grifo junto. Fora dele ela ficaria branca colada na barra,
    // e para evitar isso a barra tinha de parar rente ao "b", o que deixava a
    // palavra torta dentro da pastilha. Caneta marca-texto passa por cima da
    // pontuação mesmo - o que não muda é a palavra, que continua "cash-b".
    texto: 'Comprando pela *cash-b,*',
    entrada: 'desliza',
    // 48 frames e não 36: a barra do grifo leva 20 para crescer, e numa cena de 36
    // ela terminaria junto com o corte - o espectador veria o efeito, não a palavra.
    destaque: {tipo: 'grifo', inicio: 16},
  },
  {
    id: 'promessa',
    frames: 48,
    // A quebra é explícita para "volta" ficar sozinha na linha: é ela que se move, e
    // palavra que se move no meio de uma linha empurra as vizinhas.
    texto: 'parte do dinheiro\n*volta*',
    entrada: 'desliza',
    // A palavra chega depois do resto, vindo de fora. O movimento é a própria
    // palavra: "volta" é a única da frase que pode entrar voltando.
    destaque: {tipo: 'chega', inicio: 15},
  },
  // `otico` corrige a folga do desenho do "1" e do "%" - ver o comentário em Numero,
  // em Base.tsx. Valor medido na tinta do quadro renderizado, não chutado.
  // Cena de dois tempos, montada em Minimo.tsx: o piso de 1% vira 1,6% e a palavra
  // "mínimo" sobrevive à troca. Os dois vêm de settings.py, não de estimativa -
  // CASHBACK_MINIMO_VENDA_INDIRETA = 1 e CASHBACK_MINIMO_VENDA_DIRETA = 1.6.
  {
    id: 'minimo',
    frames: 136,
    primeiro: '1%',
    otico: -13,
    segundo: '1,6%',
    // Mesma correção de folga de desenho do "1%", medida de novo: a vírgula e o 6
    // mudam as sobras laterais, então o valor não é o mesmo.
    oticoSegundo: -14,
    condicao: 'dependendo da forma\nque você compra',
  },
  {
    id: 'mais',
    frames: 54,
    texto: 'Muitas vezes,\n*bem mais*',
    entrada: 'sobe',
    // Cresce e fica maior que a linha de cima. É a ênfase que o próprio texto pede.
    destaque: {tipo: 'cresce', inicio: 14},
  },
  // Aqui o rótulo vem ACIMA do número: "saque a partir de R$ 20" é uma frase só, e
  // quebrá-la com o número no meio é o que a deixa legível de relance.
  {
    id: 'saque',
    frames: 66,
    acima: 'saque a partir de',
    numero: 'R$ 20',
    abaixo: 'no Pix',
    entrada: 'cresce',
  },
  // Duas frases, duas entradas: a pausa entre elas é o que faz o espectador contar
  // dois fatos em vez de ler uma linha só.
  {id: 'semtaxa', frames: 42, texto: 'Sem mensalidade.\nSem taxa.', entrada: 'linhas'},
  {id: 'marca', frames: 84, convite: 'acesse', dominio: 'cash-b', sufixo: '.com'},
] as const;

export const DURACAO = CENAS.reduce((total, cena) => total + cena.frames, 0);

/** Gancho alternativo: "Vai comprar na Shopee? Espera."
 *
 * Escolhido entre três ângulos (identificação, quebra de padrão, curiosidade com
 * número). É o que mais para o dedo nos dois primeiros segundos, e "espera" é a
 * instrução real do produto: o cashback só vale se o link for gerado ANTES da compra.
 *
 * Desemboca em "Comprando pela cash-b," sem repetir a promessa - por isso o gancho não
 * fala de cashback: a cena 3 é quem paga isso.
 *
 * É mais curto que o gancho original (3 linhas de até 11 caracteres, contra 4 de até
 * 18), então o texto cresce de 114 para 168px e a cena perde 6 frames de leitura. */
export const GANCHO_ESPERA = {
  id: 'compra',
  frames: 66,
  texto: 'Vai comprar\nna Shopee?\n*Espera.*',
  corpo: 168,
  entrada: 'sobe',
  // A pergunta entra branca; "Espera." é pintada logo depois, como interrupção.
  destaque: {tipo: 'pintura', inicio: 26},
} as const;

/** A versão calma com o gancho novo. As demais cenas são as mesmas de CENAS, então
 * corrigir uma frase corrige nas duas versões. */
export const CENAS_ESPERA = [GANCHO_ESPERA, ...CENAS.slice(1)] as const;

export const DURACAO_ESPERA = CENAS_ESPERA.reduce((total, cena) => total + cena.frames, 0);
