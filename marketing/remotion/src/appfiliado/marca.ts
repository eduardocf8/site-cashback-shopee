/** Cores e fonte do Appfiliado (iguais às do painel: painel/static/painel/painel.css). */
import {continueRender, delayRender, staticFile} from 'remotion';

export const C = {
  verde: '#1F3A2E',
  verde2: '#2D4B3D',
  verde3: '#17301F',
  creme: '#F6F3EA',
  amarelo: '#F2C230',
  tinta: '#1D2A23',
  suave: '#AFC1B5',
  cinza: '#5B675F',
  borda: '#E6DFC9',
  branco: '#FFFFFF',
  ok: '#2E9E5B',
  zap: '#E9E2D3',
  balao: '#FFFFFF',
} as const;

export const FONTE = 'DM Appfiliado';

const espera = delayRender('carregando a DM Sans');
const face = (peso: string, arquivo: string) =>
  new FontFace(FONTE, `url(${staticFile(arquivo)}) format('truetype')`, {weight: peso}).load();

Promise.all([face('500', 'appfiliado/dmsans-500.ttf'), face('800', 'appfiliado/dmsans-800.ttf')])
  .then((fontes) => {
    fontes.forEach((f) => document.fonts.add(f));
    continueRender(espera);
  })
  .catch(() => continueRender(espera));

export const SIMBOLO_PATH = {
  circulo: {cx: 21, cy: 26, r: 9.5},
  haste: 'M30.5 16.5V36',
};

export const ICONES: Record<string, string> = {
  bot: 'M21 12a8 8 0 0 1-11.6 7.1L4 21l1.9-5.4A8 8 0 1 1 21 12z',
  site: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18',
  carrosseis: 'M7 5h10v14H7zM3 7v10M21 7v10',
  notas: 'M6 3h9l4 4v14H6zM14 3v5h5M9 12h7M9 16h7',
  radar: 'M12 3a9 9 0 1 0 9 9M12 7a5 5 0 1 0 5 5M12 12l6-6M17 3v4h4',
  conversor: 'M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1',
  resultados: 'M4 20V10M10 20V4M16 20v-7M22 20H2',
};
