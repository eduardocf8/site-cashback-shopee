/** Paleta e fontes da marca. Espelha static/css/brand.css - ver BRAND.md.
 *
 * Os valores estão repetidos aqui porque o Remotion não lê o CSS do Django. Trocar uma
 * cor significa trocar nos dois lugares; o brand.css é quem manda. */
export const CORES = {
  ink: '#111827',
  muted: '#6b7280',
  brand: '#6d28d9',
  brandStrong: '#4c1d95',
  highlight: '#f59e0b',
  success: '#059669',
  paper: '#f8fafc',
} as const;

export const FONTE = {
  texto: 'Familjen',
  numero: 'JB Mono',
} as const;

/** Faixa que sobrevive ao recorte 4:5 do feed do Instagram: o corte tira 285px de cada
 * ponta do quadro 9:16. Nada legível pode ficar fora daqui. O player ainda escreve nome
 * e legenda sobre os ~300px de baixo, então o conteúdo respira mais embaixo. */
export const SEGURO = {topo: 380, base: 420, lateral: 90} as const;
