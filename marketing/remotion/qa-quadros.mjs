// Revisão: monta o projeto uma vez e salva quadros de várias composições em PNG (escala 0,5).
// Uso: node qa-quadros.mjs <pasta> <id>:<frame>,<frame>... [<id>:...]
import {bundle} from '@remotion/bundler';
import {renderStill, selectComposition} from '@remotion/renderer';
import path from 'node:path';

const [pasta, ...pedidos] = process.argv.slice(2);
const browserExecutable = '/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell';
const serveUrl = await bundle({entryPoint: path.resolve('src/index.ts')});
for (const pedido of pedidos) {
  const [id, lista] = pedido.split(':');
  const composition = await selectComposition({serveUrl, id, browserExecutable});
  const frames = lista === 'todos'
    ? Array.from({length: Math.ceil(composition.durationInFrames / 30)}, (_, i) => i * 30 + 20)
    : lista.split(',').map(Number);
  for (const frame of frames) {
    if (frame >= composition.durationInFrames) continue;
    await renderStill({composition, serveUrl, frame, output: `${pasta}/${id}-${String(frame).padStart(4, '0')}.png`, scale: 0.5, browserExecutable});
  }
  console.log(id, composition.durationInFrames, 'frames');
}
