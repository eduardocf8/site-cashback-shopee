/** Peças dos vídeos de divulgação (9:16, 1080 x 1920, 30 fps): fundo, título que entra palavra por
 * palavra, celular, conversa de grupo do WhatsApp, etiquetas, toque na tela, transição de cortina e
 * o encerramento. Os vídeos (um arquivo por tema) só montam essas peças com o texto e o tempo de cada um.
 *
 * Regras do projeto (README da pasta remotion): animação só com o frame (interpolate e spring), nada
 * aleatório, e nada legível fora da faixa y 300–1620, que é o que sobra no recorte 4:5 do feed. */
import React from 'react';
import {AbsoluteFill, Easing, Img, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {C, FONTE} from '../appfiliado/marca';
import {Icone, Logo, entra, mola, produto} from '../appfiliado/ui';
import type {Oferta} from './textos';
import {SITE} from './textos';

export const FPS = 30;
export const LARGURA = 1080;
export const ALTURA = 1920;
export const FAIXA = {topo: 300, base: 1620};

/** Onde fica cada coisa nas cenas com celular, de cima pra baixo: o chapéu e o título (2 linhas), o
 * celular no centro e a legenda (um balão por vez) embaixo dele. Tudo dentro da FAIXA. */
export const POS = {titulo: 330, celular: 640, legenda: 1500};
export const ESCALA_CELULAR = 0.72; // 640 + 1152 x 0,72 = 1469: o celular termina antes da legenda

export const s = (segundos: number) => Math.round(segundos * FPS);

const suave = Easing.bezier(0.22, 1, 0.36, 1);
export const vai = (f: number, de: number, ate: number, a = 0, b = 1, easing = suave) =>
  interpolate(f, [de, ate], [a, b], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing});

// --- fundo ----------------------------------------------------------------------------------------

export type Tom = 'escuro' | 'creme' | 'amarelo';

export const Fundo: React.FC<{tom?: Tom; zoom?: boolean}> = ({tom = 'creme', zoom = true}) => {
  const f = useCurrentFrame();
  const escala = zoom ? 1 + f * 0.00035 : 1;
  const base =
    tom === 'escuro'
      ? `radial-gradient(110% 80% at 85% 8%, ${C.verde2} 0%, ${C.verde} 48%, ${C.verde3} 100%)`
      : tom === 'amarelo'
        ? `radial-gradient(110% 80% at 15% 10%, #F7D560 0%, ${C.amarelo} 55%, #E2B21F 100%)`
        : C.creme;
  const pontos = tom === 'escuro' ? 'rgba(246,243,234,.05)' : 'rgba(31,58,46,.06)';
  return (
    <AbsoluteFill style={{background: base, overflow: 'hidden'}}>
      <AbsoluteFill style={{transform: `scale(${escala})`, backgroundImage: `radial-gradient(${pontos} 2.5px, transparent 2.5px)`, backgroundSize: '44px 44px'}} />
    </AbsoluteFill>
  );
};

// --- texto -----------------------------------------------------------------------------------------

/** Título que entra palavra por palavra, subindo de trás de uma máscara. Trechos entre *asteriscos*
 * saem na cor de destaque. `\n` quebra a linha. */
export const Titulo: React.FC<{
  texto: string; inicio?: number; tamanho?: number; cor?: string; destaque?: string; alinhar?: 'left' | 'center';
  intervalo?: number; style?: React.CSSProperties; peso?: number;
}> = ({texto, inicio = 0, tamanho = 88, cor = C.tinta, destaque = C.amarelo, alinhar = 'left', intervalo = 3, style, peso = 800}) => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  let marcado = false;
  let n = 0;
  const linhas = texto.split('\n').map((linha) =>
    linha.split(' ').filter(Boolean).map((palavra) => {
      const abre = palavra.startsWith('*');
      const fecha = palavra.endsWith('*');
      if (abre) marcado = true;
      const limpa = palavra.replace(/\*/g, '');
      const item = {palavra: limpa, destaque: marcado, i: n++};
      if (fecha) marcado = false;
      return item;
    }),
  );
  return (
    <div style={{fontFamily: FONTE, fontSize: tamanho, fontWeight: peso, lineHeight: 1.06, letterSpacing: '-.035em', color: cor, textAlign: alinhar, ...style}}>
      {linhas.map((linha, l) => (
        <div key={l} style={{display: 'flex', flexWrap: 'wrap', justifyContent: alinhar === 'center' ? 'center' : 'flex-start', columnGap: '.24em'}}>
          {linha.map((p) => {
            const t = mola(f, inicio + p.i * intervalo, fps, 16);
            return (
              <span key={p.i} style={{display: 'inline-block', overflow: 'hidden', paddingBottom: '.08em', marginBottom: '-.08em'}}>
                <span style={{display: 'inline-block', transform: `translateY(${(1 - t) * 105}%)`, color: p.destaque ? destaque : undefined}}>{p.palavra}</span>
              </span>
            );
          })}
        </div>
      ))}
    </div>
  );
};

/** Linha de apoio que aparece suave. */
export const Apoio: React.FC<{texto: React.ReactNode; inicio?: number; tamanho?: number; cor?: string; alinhar?: 'left' | 'center'; style?: React.CSSProperties}> = ({
  texto, inicio = 0, tamanho = 38, cor = C.cinza, alinhar = 'left', style,
}) => {
  const f = useCurrentFrame();
  const t = vai(f, inicio, inicio + 16);
  // a opacidade de `style` multiplica a da entrada (senão a linha apareceria desde o primeiro quadro)
  const opacidade = typeof style?.opacity === 'number' ? style.opacity : 1;
  return <div style={{fontFamily: FONTE, fontSize: tamanho, fontWeight: 500, color: cor, lineHeight: 1.3, textAlign: alinhar, ...style, opacity: t * opacidade, transform: `translateY(${(1 - t) * 18}px)`}}>{texto}</div>;
};

/** Chapéu: o nome do módulo em caixa alta, com um ícone opcional. */
export const Chapeu: React.FC<{texto: string; inicio?: number; cor?: string; style?: React.CSSProperties}> = ({texto, inicio = 0, cor = '#8A6A00', style}) => {
  const f = useCurrentFrame();
  const t = vai(f, inicio, inicio + 14);
  return (
    <div style={{fontFamily: FONTE, fontSize: 30, fontWeight: 800, letterSpacing: '.14em', textTransform: 'uppercase', color: cor, opacity: t,
      transform: `translateX(${(1 - t) * -24}px)`, display: 'flex', alignItems: 'center', gap: 14, ...style}}>
      <span style={{width: 34, height: 6, borderRadius: 3, background: 'currentColor'}} />
      {texto}
    </div>
  );
};

/** Etiqueta (pílula) que entra com mola. */
export const Etiqueta: React.FC<{texto: React.ReactNode; inicio: number; tom?: 'claro' | 'escuro' | 'amarelo'; tamanho?: number; style?: React.CSSProperties}> = ({
  texto, inicio, tom = 'claro', tamanho = 30, style,
}) => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  if (f < inicio) return null;
  const t = mola(f, inicio, fps, 13);
  const cores = tom === 'escuro' ? {bg: C.verde, fg: C.creme, borda: C.verde} : tom === 'amarelo' ? {bg: C.amarelo, fg: C.verde, borda: C.amarelo} : {bg: C.branco, fg: C.tinta, borda: C.borda};
  return (
    <div style={{fontFamily: FONTE, display: 'inline-flex', alignItems: 'center', gap: 12, background: cores.bg, color: cores.fg, border: `3px solid ${cores.borda}`,
      borderRadius: 999, padding: '14px 26px', fontSize: tamanho, fontWeight: 800, whiteSpace: 'nowrap', boxShadow: '0 14px 30px rgba(23,48,31,.14)',
      opacity: Math.min(1, t * 1.4), transform: `translateY(${(1 - t) * 30}px) scale(${0.85 + 0.15 * t})`, ...style}}>
      {texto}
    </div>
  );
};

/** Chapéu e título no lugar padrão (POS.titulo), alinhados à esquerda. */
export const Cabecalho: React.FC<{chapeu: string; titulo: string; inicio?: number; escuro?: boolean; amarelo?: boolean; tamanho?: number}> = ({
  chapeu, titulo, inicio = 0, escuro, amarelo, tamanho = 88,
}) => (
  <div style={{position: 'absolute', left: 90, right: 90, top: POS.titulo}}>
    <Chapeu texto={chapeu} inicio={inicio - 8} cor={escuro ? C.amarelo : amarelo ? C.verde : '#8A6A00'} />
    <Titulo texto={titulo} inicio={inicio} tamanho={tamanho} cor={escuro ? C.creme : amarelo ? C.verde : C.tinta}
      destaque={escuro ? C.amarelo : amarelo ? C.branco : '#8A6A00'} style={{marginTop: 22}} />
  </div>
);

/** O celular centralizado no lugar padrão (POS.celular), entrando de baixo. */
export const CelularNaCena: React.FC<{children: React.ReactNode; inicio?: number; hora?: string; fundoTela?: string; barraClara?: boolean; escala?: number; top?: number}> = ({
  children, inicio = 0, hora, fundoTela, barraClara, escala = ESCALA_CELULAR, top = POS.celular,
}) => {
  const f = useCurrentFrame();
  const t = vai(f, inicio, inicio + 18);
  return (
    <div style={{position: 'absolute', left: 0, right: 0, top, display: 'flex', justifyContent: 'center', opacity: Math.min(1, t * 1.6), transform: `translateY(${(1 - t) * 120}px)`}}>
      <Celular escala={escala} hora={hora} fundoTela={fundoTela} barraClara={barraClara}>{children}</Celular>
    </div>
  );
};

// --- legenda: um balão por vez, no centro ---------------------------------------------------------

export type Fala = {f: number; texto: React.ReactNode; icone?: string; tom?: 'claro' | 'escuro' | 'amarelo'};

export const Balao: React.FC<{texto: React.ReactNode; icone?: string; tom?: 'claro' | 'escuro' | 'amarelo'; tamanho?: number}> = ({texto, icone, tom = 'claro', tamanho = 40}) => {
  // o círculo do ícone nunca é amarelo: emoji amarelo (✨ ⚡ ⚠️ 🔔) sumiria dentro dele
  const cores = tom === 'escuro' ? {bg: C.verde, fg: C.creme, bola: C.creme, bolaFg: C.verde}
    : tom === 'amarelo' ? {bg: C.amarelo, fg: C.verde, bola: C.verde, bolaFg: C.amarelo}
      : {bg: C.branco, fg: C.tinta, bola: C.verde, bolaFg: C.amarelo};
  return (
    <div style={{fontFamily: FONTE, display: 'inline-flex', alignItems: 'center', gap: 20, background: cores.bg, color: cores.fg, borderRadius: 999,
      padding: icone ? '20px 40px 20px 20px' : '24px 44px', fontSize: tamanho, fontWeight: 800, letterSpacing: '-.01em', lineHeight: 1.15, maxWidth: 940,
      boxShadow: '0 22px 48px rgba(10,25,16,.24)', textAlign: 'left'}}>
      {icone && <span style={{width: 62, height: 62, borderRadius: '50%', background: cores.bola, color: cores.bolaFg, display: 'grid', placeItems: 'center',
        fontSize: 32, flex: 'none'}}>{icone}</span>}
      <span>{texto}</span>
    </div>
  );
};

/** Legendas da cena: um balão por vez, centralizado em `y`. Cada um entra no seu frame e sai (subindo
 * e sumindo) quando o próximo entra; o último fica até `ate` (ou até o fim da cena). */
const SAIDA_DA_FALA = 8;

export const Legendas: React.FC<{falas: Fala[]; y?: number; ate?: number; tamanho?: number}> = ({falas, y = POS.legenda, ate, tamanho = 40}) => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  return (
    <div style={{position: 'absolute', left: 0, right: 0, top: y, zIndex: 70}}>
      {falas.map((fala, i) => {
        const proxima = i + 1 < falas.length ? falas[i + 1].f : ate;
        const comeca = fala.f + (i > 0 ? SAIDA_DA_FALA : 0); // só entra depois que o anterior saiu: nunca dois balões juntos
        if (f < comeca || (proxima !== undefined && f > proxima + SAIDA_DA_FALA)) return null;
        const entra_ = mola(f, comeca, fps, 14);
        const sai = proxima === undefined ? 0 : vai(f, proxima, proxima + SAIDA_DA_FALA, 0, 1, Easing.in(Easing.cubic));
        return (
          <div key={i} style={{position: 'absolute', left: 0, right: 0, top: 0, display: 'flex', justifyContent: 'center',
            opacity: Math.min(1, entra_ * 1.4) * (1 - sai), transform: `translateY(${(1 - entra_) * 46 - sai * 34}px) scale(${0.9 + 0.1 * entra_ - 0.05 * sai})`}}>
            <Balao texto={fala.texto} icone={fala.icone} tom={fala.tom} tamanho={tamanho} />
          </div>
        );
      })}
    </div>
  );
};

// --- movimento entre cenas ----------------------------------------------------------------------

/** Entrada e saída de uma cena: sobe e aparece no começo, some no fim. */
export const Cena: React.FC<{duracao: number; children: React.ReactNode; entrada?: boolean; saida?: boolean}> = ({duracao, children, entrada = true, saida = true}) => {
  const f = useCurrentFrame();
  const dentro = entrada ? vai(f, 0, 14) : 1;
  const fora = saida ? vai(f, duracao - 10, duracao, 1, 0, Easing.in(Easing.cubic)) : 1;
  return <AbsoluteFill style={{opacity: Math.min(dentro, fora), transform: `translateY(${(1 - dentro) * 40}px)`}}>{children}</AbsoluteFill>;
};

/** Cortina que cruza a tela de baixo pra cima, cobrindo a troca de cena. Use numa <Sequence> de 18
 * frames centrada no corte (a tela fica coberta no frame 9). */
export const Cortina: React.FC<{cor?: string; texto?: string; corTexto?: string}> = ({cor = C.amarelo, texto, corTexto = C.verde}) => {
  const f = useCurrentFrame();
  const entra_ = vai(f, 0, 9, 100, 0, Easing.inOut(Easing.cubic));
  const sai = vai(f, 9, 18, 0, -100, Easing.inOut(Easing.cubic));
  const y = f < 9 ? entra_ : sai;
  return (
    <AbsoluteFill style={{transform: `translateY(${y}%)`, background: cor, zIndex: 100, alignItems: 'center', justifyContent: 'center'}}>
      {texto && <div style={{fontFamily: FONTE, fontSize: 120, fontWeight: 800, letterSpacing: '-.04em', color: corTexto}}>{texto}</div>}
    </AbsoluteFill>
  );
};

// --- celular e WhatsApp -------------------------------------------------------------------------

/** Celular: moldura escura com a tela dentro. O conteúdo é desenhado em 560 x 1120 e escalado por `escala`. */
export const TELA = {largura: 560, altura: 1120};

export const Celular: React.FC<{children: React.ReactNode; escala?: number; style?: React.CSSProperties; hora?: string; fundoTela?: string; barraClara?: boolean}> = ({
  children, escala = 1, style, hora = '9:41', fundoTela = C.creme, barraClara = false,
}) => (
  <div style={{width: TELA.largura + 32, height: TELA.altura + 32, borderRadius: 82, background: '#0E1712', padding: 16, boxShadow: '0 40px 80px rgba(10,25,16,.35)',
    transform: `scale(${escala})`, transformOrigin: 'top center', flex: 'none', ...style}}>
    <div style={{width: TELA.largura, height: TELA.altura, borderRadius: 66, overflow: 'hidden', position: 'relative', background: fundoTela, fontFamily: FONTE}}>
      <div style={{position: 'absolute', top: 0, left: 0, right: 0, height: 56, zIndex: 20, display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 44px', fontSize: 22, fontWeight: 800, color: barraClara ? C.creme : C.tinta}}>
        <span>{hora}</span>
        <span style={{width: 130, height: 34, borderRadius: 20, background: '#0E1712', position: 'absolute', left: '50%', top: 12, transform: 'translateX(-50%)'}} />
        <span style={{letterSpacing: 2}}>●●● ▮</span>
      </div>
      {children}
    </div>
  </div>
);

export type Mensagem =
  | ({f: number; tipo: 'oferta'; hora: string; campanha?: string} & Oferta)
  | {f: number; tipo: 'texto'; hora: string; texto: string; autor?: string};

/** Conversa de grupo do WhatsApp. As mensagens chegam no frame `f` de cada uma; as mais novas ficam
 * embaixo e empurram as de cima (a altura de cada uma cresce com mola, então a rolagem é suave). */
export const ConversaZap: React.FC<{nome: string; membros: string; mensagens: Mensagem[]; emoji?: string}> = ({nome, membros, mensagens, emoji = '🛍️'}) => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  return (
    <div style={{position: 'absolute', inset: 0, background: C.zap, display: 'flex', flexDirection: 'column'}}>
      <div style={{height: 150, paddingTop: 56, background: C.verde, color: C.creme, display: 'flex', alignItems: 'center', gap: 18, padding: '56px 26px 0', flex: 'none', zIndex: 2}}>
        <span style={{fontSize: 34, opacity: 0.8}}>‹</span>
        <div style={{width: 64, height: 64, borderRadius: '50%', background: C.amarelo, display: 'grid', placeItems: 'center', fontSize: 34}}>{emoji}</div>
        <div>
          <div style={{fontSize: 28, fontWeight: 800}}>{nome}</div>
          <div style={{fontSize: 20, color: C.suave}}>{membros}</div>
        </div>
      </div>
      <div style={{flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'flex-end', padding: '0 22px 24px', overflow: 'hidden'}}>
        {mensagens.map((m, i) => {
          if (f < m.f) return null;
          const t = mola(f, m.f, fps, 15);
          return (
            <div key={i} style={{maxHeight: 640 * t, overflow: 'visible', flex: 'none'}}>
              <div style={{paddingTop: 18, opacity: Math.min(1, t * 1.5), transform: `scale(${0.92 + 0.08 * t})`, transformOrigin: 'left bottom'}}>
                {m.tipo === 'oferta' ? <BalaoOferta m={m} /> : <BalaoTexto texto={m.texto} hora={m.hora} autor={m.autor} />}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

const Hora: React.FC<{hora: string}> = ({hora}) => (
  <div style={{textAlign: 'right', fontSize: 17, color: '#8C978F', marginTop: 4}}>{hora} <span style={{color: '#4FA3E0'}}>✓✓</span></div>
);

export const BalaoOferta: React.FC<{m: Oferta & {hora: string; campanha?: string}}> = ({m}) => (
  <div style={{background: C.balao, color: C.tinta, borderRadius: '8px 24px 24px 24px', padding: 12, width: 440, boxShadow: '0 4px 10px rgba(0,0,0,.07)'}}>
    <Img src={produto(m.foto)} style={{width: 416, height: 230, objectFit: 'cover', borderRadius: 16, display: 'block'}} />
    <div style={{fontSize: 21, lineHeight: 1.36, padding: '10px 6px 0'}}>
      {m.campanha && <div style={{fontWeight: 800, color: '#B2470F'}}>{m.campanha}</div>}
      <div style={{fontWeight: 800}}>🔥 {m.nome}</div>
      <div><span style={{color: C.cinza, textDecoration: 'line-through'}}>{m.de}</span> <span style={{fontWeight: 800, color: C.ok, fontSize: 25}}>{m.por}</span></div>
      {m.cupom && <div style={{fontWeight: 800}}>🎟️ Cupom: {m.cupom}</div>}
      <div style={{color: '#2F6FD8'}}>👉 {m.link}</div>
      <Hora hora={m.hora} />
    </div>
  </div>
);

export const BalaoTexto: React.FC<{texto: string; hora: string; autor?: string}> = ({texto, hora, autor}) => (
  <div style={{background: C.balao, color: C.tinta, borderRadius: '8px 24px 24px 24px', padding: '12px 18px', maxWidth: 440, boxShadow: '0 4px 10px rgba(0,0,0,.07)', fontSize: 22, lineHeight: 1.36}}>
    {autor && <div style={{fontWeight: 800, color: '#2F8F6A', fontSize: 19}}>{autor}</div>}
    {texto}
    <Hora hora={hora} />
  </div>
);

/** Toque na tela: um círculo que aperta e se abre, no ponto (x, y) da tela, no frame `f`. */
export const Toque: React.FC<{x: number; y: number; f: number}> = ({x, y, f: quando}) => {
  const f = useCurrentFrame();
  const d = f - quando;
  if (d < -8 || d > 22) return null;
  const chega = vai(f, quando - 8, quando, 0, 1);
  const abre = vai(f, quando, quando + 20, 0, 1);
  return (
    <div style={{position: 'absolute', left: x, top: y, zIndex: 60, pointerEvents: 'none'}}>
      <div style={{position: 'absolute', left: -34, top: -34, width: 68, height: 68, borderRadius: '50%', background: 'rgba(255,255,255,.55)', border: '3px solid rgba(31,58,46,.35)',
        opacity: chega * (1 - abre), transform: `scale(${d < 0 ? 1.2 - 0.2 * chega : 1 - 0.15 * Math.min(1, d / 4)})`}} />
      <div style={{position: 'absolute', left: -60, top: -60, width: 120, height: 120, borderRadius: '50%', border: `5px solid ${C.amarelo}`,
        opacity: d >= 0 ? 1 - abre : 0, transform: `scale(${0.3 + abre})`}} />
    </div>
  );
};

/** Número que conta entre dois valores (inteiro ou reais). */
export const Conta: React.FC<{de?: number; ate: number; inicio: number; duracao?: number; reais?: boolean; prefixo?: string}> = ({de = 0, ate, inicio, duracao = 40, reais, prefixo = ''}) => {
  const f = useCurrentFrame();
  const v = interpolate(f, [inicio, inicio + duracao], [de, ate], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic)});
  const texto = reais ? 'R$ ' + v.toLocaleString('pt-BR', {minimumFractionDigits: 2, maximumFractionDigits: 2}) : Math.round(v).toLocaleString('pt-BR');
  return <span style={{fontVariantNumeric: 'tabular-nums'}}>{prefixo}{texto}</span>;
};

// --- encerramento --------------------------------------------------------------------------------

export type Incluso = {icone: string; nome: string};

/** Encerramento: a marca, a frase do vídeo, o preço (ou "incluso") e, se vier `inclusos`, as ferramentas
 * que já vêm em todos os planos, uma a uma, antes do endereço. `destaque` marca a ferramenta do vídeo. */
export const Final: React.FC<{frase: string; linha: string; tom?: 'escuro' | 'creme'; inclusos?: Incluso[]; rotulo?: string; destaque?: string}> = ({
  frase, linha, tom = 'escuro', inclusos, rotulo = 'Incluso em todos os planos:', destaque,
}) => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const escuro = tom === 'escuro';
  const logo = mola(f, 0, fps, 11);
  const lista = inclusos ?? [];
  const chipsDe = 38;
  const urlEm = lista.length ? chipsDe + lista.length * 6 + 10 : 30;
  const url = mola(f, urlEm, fps, 13);
  return (
    <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center', textAlign: 'center', padding: '0 80px', fontFamily: FONTE}}>
      <Fundo tom={escuro ? 'escuro' : 'creme'} />
      <div style={{display: 'flex', alignItems: 'center', gap: 22, transform: `scale(${0.6 + 0.4 * logo})`, opacity: logo}}>
        <Logo tamanho={lista.length ? 100 : 116} fundo={C.amarelo} cor={C.verde} />
        <div style={{fontSize: lista.length ? 66 : 76, fontWeight: 800, letterSpacing: '-.03em', color: escuro ? C.creme : C.verde}}>Appfiliado</div>
      </div>
      <Titulo texto={frase} inicio={8} tamanho={lista.length ? 80 : 92} alinhar="center" cor={escuro ? C.creme : C.tinta} destaque={escuro ? C.amarelo : '#8A6A00'}
        style={{marginTop: lista.length ? 48 : 70}} />
      <Apoio texto={linha} inicio={22} alinhar="center" cor={escuro ? C.creme : C.tinta} tamanho={38} style={{marginTop: 26, fontWeight: 800}} />
      {lista.length > 0 && (
        <>
          <Apoio texto={rotulo} inicio={chipsDe - 6} alinhar="center" cor={escuro ? C.suave : C.cinza} tamanho={30} style={{marginTop: 44}} />
          <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginTop: 18, width: 920}}>
            {lista.map((item, k) => {
              const t = mola(f, chipsDe + k * 6, fps, 13);
              const atual = item.nome === destaque;
              return (
                <div key={item.nome} style={{display: 'flex', alignItems: 'center', gap: 16, padding: '16px 20px', borderRadius: 24, textAlign: 'left',
                  background: atual ? C.amarelo : escuro ? 'rgba(246,243,234,.09)' : C.branco, border: `2px solid ${atual ? C.amarelo : escuro ? 'rgba(246,243,234,.16)' : C.borda}`,
                  color: atual ? C.verde : escuro ? C.creme : C.tinta, opacity: Math.min(1, t * 1.4), transform: `translateY(${(1 - t) * 26}px) scale(${0.9 + 0.1 * t})`}}>
                  <span style={{width: 54, height: 54, borderRadius: 16, background: atual ? C.verde : escuro ? C.verde3 : C.verde, display: 'grid', placeItems: 'center', flex: 'none'}}>
                    <Icone nome={item.icone} tamanho={32} />
                  </span>
                  <span style={{fontSize: 29, fontWeight: 800, lineHeight: 1.1}}>{item.nome}</span>
                </div>
              );
            })}
          </div>
        </>
      )}
      <div style={{marginTop: lista.length ? 44 : 64, background: C.amarelo, color: C.verde, fontSize: lista.length ? 48 : 52, fontWeight: 800, borderRadius: 999, padding: '24px 54px',
        transform: `translateY(${(1 - url) * 40}px) scale(${0.9 + 0.1 * url})`, opacity: Math.min(1, url * 1.4), boxShadow: '0 24px 50px rgba(0,0,0,.25)'}}>
        {SITE}
      </div>
    </AbsoluteFill>
  );
};

/** Duração do encerramento: mais tempo quando ele lista as ferramentas inclusas. */
export const DURACAO_FINAL = {simples: 114, comInclusos: 156};

export {entra, mola};
