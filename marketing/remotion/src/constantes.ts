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
    texto: 'Você já compra\nna Shopee\ne ainda não recebe\ncashback?',
    // É o gancho: continua sendo a tela mais longa do vídeo e a que fica mais tempo.
    corpo: 114,
    // Entra inteira e calma. É a pergunta que monta o problema; quatro linhas
    // entrando uma a uma aqui atrasariam a leitura logo no primeiro segundo.
    entrada: 'sobe',
  },
  // As duas entram deslizando do mesmo lado: é o que mantém a frase inteira. Ver o
  // comentário do tipo Entrada, em Base.tsx.
  {id: 'condicao', frames: 36, texto: 'Comprando pela cash-b,', entrada: 'desliza'},
  {id: 'promessa', frames: 48, texto: 'parte do dinheiro volta', entrada: 'desliza'},
  // `otico` corrige a folga do desenho do "1" e do "%" - ver o comentário em Numero,
  // em Base.tsx. Valor medido na tinta do quadro renderizado, não chutado.
  {
    id: 'minimo',
    frames: 66,
    numero: '1%',
    otico: -13,
    abaixo: 'no mínimo, em toda compra',
    entrada: 'cresce',
  },
  {id: 'mais', frames: 42, texto: 'Muitas vezes, bem mais', entrada: 'sobe'},
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
  {id: 'marca', frames: 96, convite: 'acesse', dominio: 'cash-b', sufixo: '.com'},
] as const;

export const DURACAO = CENAS.reduce((total, cena) => total + cena.frames, 0);
