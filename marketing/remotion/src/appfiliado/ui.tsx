/** Peças de interface reaproveitadas pelas cenas: o visual do painel do Appfiliado recriado em React,
 * o cursor que "usa" a ferramenta e os números que contam. Tudo desenhado numa área lógica de
 * 900 x 1000 (ver Cena em Video.tsx, que escala pro formato do vídeo). */
import React, {createContext, useCallback, useContext, useLayoutEffect, useRef, useState} from 'react';
import {Easing, Img, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {C, FONTE, ICONES} from './marca';

export const LARGURA_DEMO = 900;
export const ALTURA_DEMO = 1000;

export const entra = (frame: number, inicio: number, duracao = 14) =>
  interpolate(frame, [inicio, inicio + duracao], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.out(Easing.cubic),
  });

export const mola = (frame: number, inicio: number, fps: number, amortecimento = 14) =>
  spring({frame: frame - inicio, fps, config: {damping: amortecimento, stiffness: 140}});

export const produto = (nome: string) => staticFile(`appfiliado/produtos/${nome}.jpg`);

export const Logo: React.FC<{tamanho?: number; fundo?: string; cor?: string}> = ({tamanho = 64, fundo = C.amarelo, cor = C.verde}) => (
  <div style={{width: tamanho, height: tamanho, borderRadius: tamanho * 0.28, background: fundo, display: 'grid', placeItems: 'center', flex: 'none'}}>
    <svg viewBox="3 8.25 36 36" width={tamanho * 0.72} height={tamanho * 0.72}>
      <g fill="none" stroke={cor} strokeWidth={5} strokeLinecap="round">
        <circle cx={21} cy={26} r={9.5} />
        <path d="M30.5 16.5V36" />
      </g>
      <circle cx={21} cy={26} r={3.6} fill={cor} />
    </svg>
  </div>
);

export const Icone: React.FC<{nome: string; tamanho?: number; cor?: string; espessura?: number}> = ({nome, tamanho = 40, cor = C.amarelo, espessura = 1.9}) => (
  <svg viewBox="0 0 24 24" width={tamanho} height={tamanho} fill="none" stroke={cor} strokeWidth={espessura} strokeLinecap="round" strokeLinejoin="round">
    <path d={ICONES[nome]} />
  </svg>
);

export const Card: React.FC<{style?: React.CSSProperties; children: React.ReactNode}> = ({style, children}) => (
  <div style={{background: C.branco, border: `2px solid ${C.borda}`, borderRadius: 28, padding: 28, boxShadow: '0 18px 40px rgba(23,48,31,.08)', ...style}}>
    {children}
  </div>
);

export const Botao: React.FC<{texto: string; tipo?: 'principal' | 'escuro' | 'claro'; apertado?: number; style?: React.CSSProperties}> = ({
  texto, tipo = 'escuro', apertado = 0, style,
}) => {
  const fundo = tipo === 'principal' ? C.amarelo : tipo === 'escuro' ? C.verde : C.branco;
  const cor = tipo === 'escuro' ? C.creme : C.verde;
  return (
    <div style={{display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 10, background: fundo, color: cor, fontWeight: 800,
      fontSize: 28, borderRadius: 999, padding: '18px 32px', border: tipo === 'claro' ? `2px solid ${C.borda}` : 'none',
      transform: `scale(${1 - 0.06 * apertado})`, ...style}}>
      {texto}
    </div>
  );
};

export const Chip: React.FC<{texto: string; ativo?: boolean}> = ({texto, ativo}) => (
  <div style={{display: 'inline-flex', padding: '12px 22px', borderRadius: 999, fontSize: 24, fontWeight: 800,
    background: ativo ? C.verde : C.branco, color: ativo ? C.creme : C.tinta, border: `2px solid ${ativo ? C.verde : C.borda}`}}>
    {texto}
  </div>
);

/** Interruptor (liga/desliga) que anima entre os dois estados a partir de `quando`. */
export const Interruptor: React.FC<{ligado: number}> = ({ligado}) => (
  <div style={{width: 96, height: 54, borderRadius: 999, background: interpolateCor(ligado), position: 'relative'}}>
    <div style={{position: 'absolute', top: 6, left: 6 + 42 * ligado, width: 42, height: 42, borderRadius: '50%', background: C.branco, boxShadow: '0 4px 10px rgba(0,0,0,.2)'}} />
  </div>
);

const interpolateCor = (t: number) => (t > 0.5 ? C.ok : '#C9C2AE');

type Ponto = {x: number; y: number};
type Alvos = {alvos: Record<string, Ponto>; raiz: React.RefObject<HTMLDivElement | null>; marcar: (nome: string, p: Ponto) => void};
const AlvosCtx = createContext<Alvos | null>(null);

/** Área da demonstração: guarda onde está o centro de cada <Alvo>, medido na própria tela a cada quadro,
 * pra o cursor clicar exatamente no botão (mesmo quando ele muda de lugar ou de tamanho). */
export const AreaDeAlvos: React.FC<{children: React.ReactNode; style?: React.CSSProperties}> = ({children, style}) => {
  const raiz = useRef<HTMLDivElement>(null);
  const [alvos, setAlvos] = useState<Record<string, Ponto>>({});
  const marcar = useCallback((nome: string, p: Ponto) => {
    setAlvos((a) => (a[nome] && Math.abs(a[nome].x - p.x) < 0.5 && Math.abs(a[nome].y - p.y) < 0.5 ? a : {...a, [nome]: p}));
  }, []);
  return (
    <AlvosCtx.Provider value={{alvos, raiz, marcar}}>
      <div ref={raiz} data-area-alvos="" style={{position: 'absolute', inset: 0, ...style}}>{children}</div>
    </AlvosCtx.Provider>
  );
};

/** Marca um elemento como alvo do cursor (o cursor mira no centro dele). */
export const Alvo: React.FC<{nome: string; children: React.ReactNode; bloco?: boolean}> = ({nome, children, bloco}) => {
  const ctx = useContext(AlvosCtx);
  const ref = useRef<HTMLDivElement>(null);
  useLayoutEffect(() => {
    const el = ref.current;
    // o ref da área ainda não está ligado quando o efeito do filho roda: acha a área pelo DOM
    const raiz = el?.closest('[data-area-alvos]') as HTMLDivElement | null;
    if (!el || !raiz || !ctx) return;
    const r = el.getBoundingClientRect();
    const base = raiz.getBoundingClientRect();
    const escala = base.width / raiz.offsetWidth || 1; // a demonstração é escalada pro formato do vídeo
    ctx.marcar(nome, {x: (r.left + r.width / 2 - base.left) / escala, y: (r.top + r.height / 2 - base.top) / escala});
  });
  return <div ref={ref} style={{display: bloco ? 'block' : 'inline-block'}}>{children}</div>;
};

/** Cursor de mouse que percorre pontos [frame, x, y] ou [frame, nome do alvo] e "clica" nos frames
 * indicados. A ponta da seta fica exatamente no ponto. */
export const Cursor: React.FC<{pontos: ([number, number, number] | [number, string])[]; cliques?: number[]}> = ({pontos, cliques = []}) => {
  const frame = useCurrentFrame();
  const ctx = useContext(AlvosCtx);
  const resolvidos = pontos.map((p) => (typeof p[1] === 'string' ? {f: p[0], ...(ctx?.alvos[p[1]] ?? {x: NaN, y: NaN})} : {f: p[0], x: p[1], y: p[2] as number}));
  if (resolvidos.some((p) => Number.isNaN(p.x))) return null; // alvos ainda não medidos neste quadro
  const fs = resolvidos.map((p) => p.f);
  const x = interpolate(frame, fs, resolvidos.map((p) => p.x), {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.inOut(Easing.cubic)});
  const y = interpolate(frame, fs, resolvidos.map((p) => p.y), {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.inOut(Easing.cubic)});
  const aparece = interpolate(frame, [fs[0], fs[0] + 8], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const clique = cliques.map((c) => frame - c).find((d) => d >= 0 && d < 14);
  return (
    <div style={{position: 'absolute', left: x, top: y, opacity: aparece, zIndex: 50, pointerEvents: 'none'}}>
      {clique !== undefined && (
        <div style={{position: 'absolute', left: -38, top: -38, width: 76, height: 76, borderRadius: '50%', border: `5px solid ${C.amarelo}`,
          opacity: 1 - clique / 14, transform: `scale(${0.4 + clique / 10})`}} />
      )}
      {/* a ponta da seta está em (4, 2) no desenho de 24 -> (9, 4,5) px no tamanho de 54 */}
      <svg width={54} height={54} viewBox="0 0 24 24" style={{position: 'absolute', left: -9, top: -4.5, transformOrigin: '9px 4.5px',
        transform: `scale(${clique !== undefined && clique < 5 ? 0.85 : 1})`, filter: 'drop-shadow(0 4px 6px rgba(0,0,0,.35))'}}>
        <path d="M4 2l15 9.5-6.6 1.4 3.8 7.4-3 1.5-3.8-7.4L4 19z" fill={C.tinta} stroke={C.branco} strokeWidth={1.4} strokeLinejoin="round" />
      </svg>
    </div>
  );
};

/** Texto digitado letra por letra entre dois frames. */
export const Digitando: React.FC<{texto: string; inicio: number; fim: number; cursor?: boolean}> = ({texto, inicio, fim, cursor = true}) => {
  const frame = useCurrentFrame();
  const n = Math.round(interpolate(frame, [inicio, fim], [0, texto.length], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}));
  const piscando = cursor && frame >= inicio && frame < fim + 20 && Math.floor(frame / 8) % 2 === 0;
  return (
    <span>
      {texto.slice(0, n)}
      <span style={{opacity: piscando ? 1 : 0, borderLeft: `3px solid ${C.tinta}`, marginLeft: 2}} />
    </span>
  );
};

/** Número que conta de 0 até `valor` (formatado em reais ou inteiro). */
export const Contador: React.FC<{valor: number; inicio: number; duracao?: number; reais?: boolean}> = ({valor, inicio, duracao = 45, reais}) => {
  const frame = useCurrentFrame();
  const t = interpolate(frame, [inicio, inicio + duracao], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic)});
  const v = valor * t;
  const texto = reais
    ? 'R$ ' + v.toLocaleString('pt-BR', {minimumFractionDigits: 2, maximumFractionDigits: 2})
    : Math.round(v).toLocaleString('pt-BR');
  return <span style={{fontVariantNumeric: 'tabular-nums'}}>{texto}</span>;
};

/** Aviso que aparece embaixo ("Link copiado!"). */
export const Aviso: React.FC<{texto: string; inicio: number; duracao?: number; style?: React.CSSProperties}> = ({texto, inicio, duracao = 60, style}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  if (frame < inicio || frame > inicio + duracao) return null;
  const s = mola(frame, inicio, fps);
  const sai = interpolate(frame, [inicio + duracao - 10, inicio + duracao], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return (
    <div style={{position: 'absolute', left: '50%', bottom: 40, transform: `translate(-50%, ${(1 - s) * 60}px)`, opacity: Math.min(s, sai), zIndex: 40,
      background: C.verde, color: C.creme, fontWeight: 800, fontSize: 28, padding: '22px 36px', borderRadius: 999, whiteSpace: 'nowrap',
      boxShadow: '0 18px 40px rgba(23,48,31,.3)', display: 'flex', gap: 14, alignItems: 'center', ...style}}>
      <span style={{width: 34, height: 34, borderRadius: '50%', background: C.amarelo, color: C.verde, display: 'grid', placeItems: 'center', fontSize: 22}}>✓</span>
      {texto}
    </div>
  );
};

export const Foto: React.FC<{nome: string; tamanho: number; raio?: number}> = ({nome, tamanho, raio = 18}) => (
  <Img src={produto(nome)} style={{width: tamanho, height: tamanho, borderRadius: raio, objectFit: 'cover', flex: 'none'}} />
);

export const texto: React.CSSProperties = {fontFamily: FONTE};
