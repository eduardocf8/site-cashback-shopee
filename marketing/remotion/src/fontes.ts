/** Carrega as fontes da marca a partir de public/.
 *
 * delayRender segura o render até a fonte estar pronta: sem isso os primeiros quadros
 * saem com a fonte de sistema e o vídeo começa com a tipografia errada. */
import {continueRender, delayRender, staticFile} from 'remotion';

const espera = delayRender('carregando as fontes da marca');

const face = (familia: string, arquivo: string) =>
  new FontFace(familia, `url(${staticFile(arquivo)}) format('woff2')`, {weight: '400 700'}).load();

Promise.all([
  face('Familjen', 'familjen-grotesk.woff2'),
  face('JB Mono', 'jetbrains-mono.woff2'),
])
  .then((carregadas) => {
    carregadas.forEach((f) => document.fonts.add(f));
    continueRender(espera);
  })
  .catch(() => continueRender(espera));
