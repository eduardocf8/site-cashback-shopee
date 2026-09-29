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

/** As três primeiras cenas são UMA frase cortada em três. A ordem importa: a condição
 * ("comprando pela cash-b") vem antes da promessa ("parte do dinheiro volta"). Invertida
 * ou separada, a última cena sozinha viraria uma afirmação falsa. */
export const CENAS = [
  // O \u00A0 é espaço que não quebra. Sem ele "Shopee" e "mais" caem sozinhos numa
  // linha, e palavra órfã em corpo de cartaz lê como erro de diagramação.
  {id: 'compra', frames: 54, texto: 'Você já compra na\u00A0Shopee'},
  {id: 'condicao', frames: 42, texto: 'Comprando pela cash-b,'},
  {id: 'promessa', frames: 54, texto: 'parte do dinheiro volta'},
  {
    id: 'minimo',
    frames: 66,
    numero: '1%',
    apoio: 'no mínimo, em toda compra',
  },
  {id: 'mais', frames: 48, texto: 'Muitas vezes,\u00A0bem\u00A0mais'},
  {
    id: 'saque',
    frames: 66,
    numero: 'R$ 20',
    apoio: 'saque a partir de, no Pix',
  },
  {id: 'semtaxa', frames: 48, texto: 'Sem mensalidade.\nSem taxa.'},
  {id: 'marca', frames: 72, endereco: 'cash-b.com'},
] as const;

export const DURACAO = CENAS.reduce((total, cena) => total + cena.frames, 0);
