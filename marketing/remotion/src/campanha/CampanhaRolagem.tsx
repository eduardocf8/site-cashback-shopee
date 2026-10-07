import React from 'react';
import {AbsoluteFill, Easing, Img, interpolate, staticFile, useCurrentFrame} from 'remotion';
import {CORES, FONTE} from '../marca';
import {CX, H, W, prog, saida} from '../animada/util';
import dados from './dados.json';

/** Reel da campanha 10.10, versão B: "gravação de tela".
 *
 * A versão A (Campanha1010) é feita de objetos sobre fundos de cor chapada: calendário,
 * letreiro, recibo, relógio. Esta é o oposto na linguagem: um app. Fundo claro de
 * interface, cartões brancos com sombra, um dedo que toca, e UMA rolagem contínua que liga
 * as telas em vez de cortes ou transições: cada cena é um trecho de uma página comprida e a
 * câmera desce por ela, com o borrão de movimento de quem desliza o dedo.
 *
 * 18 s, 30 fps. Cinco telas de 1920px empilhadas; a rolagem para em cada uma, e é nas
 * paradas que as coisas acontecem. As coordenadas de cada tela são locais: com a tela
 * parada, são as mesmas coordenadas do quadro. */

const EXTRA = `${dados.percentualExtra}%`;
export const DURACAO_ROLAGEM = 540;
// Versão para anúncio: o mesmo vídeo com o fecho prolongado e um botão "Cadastre-se grátis".
export const DURACAO_ROLAGEM_ANUNCIO = 600;

// Rolagens entre as telas: [quadro em que começa, quadro em que termina].
const ROLAGENS: [number, number][] = [
  [96, 122],
  [246, 272],
  [366, 392],
  [474, 500],
];
const curva = Easing.bezier(0.7, 0, 0.2, 1);

const rolagemEm = (frame: number): number => {
  let y = 0;
  for (const [de, ate] of ROLAGENS) {
    y += H * interpolate(frame, [de, ate], [0, 1], {
      extrapolateLeft: 'clamp',
      extrapolateRight: 'clamp',
      easing: curva,
    });
  }
  return y;
};

// ------------------------------------------------------------------------------ peças de UI

const LAV = '#f1eefb';
const BORDA = '#e0dcef';

const Cartao: React.FC<{style?: React.CSSProperties; children: React.ReactNode}> = ({
  style,
  children,
}) => (
  <div
    style={{
      background: '#fff',
      borderRadius: 44,
      boxShadow: '0 30px 70px rgba(76,29,149,0.16), 0 4px 14px rgba(76,29,149,0.08)',
      border: `2px solid ${BORDA}`,
      ...style,
    }}
  >
    {children}
  </div>
);

/** Linha de texto que sobe de uma máscara, no tempo local da tela. */
const Sobe: React.FC<{
  de: number;
  tam: number;
  cor?: string;
  align?: 'left' | 'center';
  children: React.ReactNode;
}> = ({de, tam, cor = CORES.ink, align = 'left', children}) => {
  const frame = useCurrentFrame();
  const p = prog(frame, de, de + 16, saida);
  return (
    <div style={{overflow: 'hidden', paddingBottom: tam * 0.14, marginBottom: -tam * 0.14}}>
      <div
        style={{
          transform: `translateY(${(1 - p) * 118}%)`,
          fontFamily: FONTE.texto,
          fontWeight: 700,
          fontSize: tam,
          lineHeight: 1.04,
          letterSpacing: '-0.03em',
          color: cor,
          whiteSpace: 'nowrap',
          textAlign: align,
        }}
      >
        {children}
      </div>
    </div>
  );
};

const virgula = (n: number, casas = 2) => n.toFixed(casas).replace('.', ',');

// ------------------------------------------------------------------------------ o dedo

type Ponto = {f: number; x: number; y: number};
// O dedo anda entre pontos, aperta nos quadros de `toques` e some depois do último.
const TRAJETOS: {pontos: Ponto[]; toque: number}[] = [
  {pontos: [{f: 66, x: 790, y: 1380}, {f: 84, x: 912, y: 1077}], toque: 86},
  {pontos: [{f: 150, x: 640, y: 1250}, {f: 168, x: 700, y: 478}], toque: 170},
];

const Dedo: React.FC = () => {
  const frame = useCurrentFrame();
  const t = TRAJETOS.find(
    (tr) => frame >= tr.pontos[0].f - 8 && frame <= tr.toque + 14,
  );
  if (!t) return null;
  const [a, b] = t.pontos;
  const p = prog(frame, a.f, b.f, curva);
  const x = interpolate(p, [0, 1], [a.x, b.x]);
  const y = interpolate(p, [0, 1], [a.y, b.y]);
  const aperta = prog(frame, t.toque - 2, t.toque + 2) - prog(frame, t.toque + 4, t.toque + 9);
  const onda = prog(frame, t.toque, t.toque + 14);
  const aparece = prog(frame, a.f - 8, a.f) * (1 - prog(frame, t.toque + 8, t.toque + 14));
  return (
    <>
      <div
        style={{
          position: 'absolute',
          left: x - 80 * onda,
          top: y - 80 * onda,
          width: 160 * onda,
          height: 160 * onda,
          borderRadius: '50%',
          border: `5px solid ${CORES.brand}`,
          opacity: onda > 0 ? (1 - onda) * 0.8 : 0,
          zIndex: 50,
        }}
      />
      <div
        style={{
          position: 'absolute',
          left: x - 40,
          top: y - 40,
          width: 80,
          height: 80,
          borderRadius: '50%',
          background: 'rgba(17,24,39,0.42)',
          border: '5px solid rgba(255,255,255,0.95)',
          boxShadow: '0 8px 24px rgba(17,24,39,0.3)',
          transform: `scale(${1 - 0.28 * aperta})`,
          opacity: aparece,
          zIndex: 51,
        }}
      />
    </>
  );
};

// ------------------------------------------------------------------------------ as telas

/** Tela 1: a pergunta e a busca. */
const Tela1: React.FC = () => {
  const frame = useCurrentFrame();
  const texto = 'kit peseira para cama';
  const digitado = Math.floor(prog(frame, 34, 72) * texto.length);
  const caret = Math.floor(frame / 8) % 2 === 0 || digitado < texto.length;
  const chip = prog(frame, 26, 40, saida);
  const enviado = prog(frame, 86, 92);
  return (
    <AbsoluteFill style={{background: LAV}}>
      <div
        style={{
          position: 'absolute',
          left: 90,
          top: 410,
          fontFamily: FONTE.texto,
          fontWeight: 700,
          fontSize: 54,
          letterSpacing: '-0.03em',
          color: CORES.brand,
          opacity: prog(frame, 0, 10),
        }}
      >
        cash-b
      </div>
      <div style={{position: 'absolute', left: 90, top: 520}}>
        <Sobe de={4} tam={104}>
          O que você vai
        </Sobe>
        <Sobe de={10} tam={104}>
          comprar no <span style={{color: CORES.brand}}>{dados.data}</span>
        </Sobe>
        <Sobe de={16} tam={104}>
          na Shopee?
        </Sobe>
      </div>
      <div
        style={{
          position: 'absolute',
          left: 90,
          top: 905,
          opacity: chip,
          transform: `translateY(${(1 - chip) * 24}px)`,
        }}
      >
        <div
          style={{
            display: 'inline-block',
            background: CORES.highlight,
            color: CORES.ink,
            fontFamily: FONTE.texto,
            fontWeight: 700,
            fontSize: 38,
            padding: '12px 30px',
            borderRadius: 999,
          }}
        >
          {EXTRA} a mais de cashback
        </div>
      </div>
      <Cartao
        style={{
          position: 'absolute',
          left: 90,
          top: 1015,
          width: 900,
          height: 124,
          borderRadius: 62,
          display: 'flex',
          alignItems: 'center',
          opacity: prog(frame, 26, 38),
        }}
      >
        <svg width="46" height="46" viewBox="0 0 24 24" style={{marginLeft: 44}} fill="none">
          <circle cx="11" cy="11" r="7" stroke={CORES.muted} strokeWidth="2.4" />
          <path d="M16.5 16.5L21 21" stroke={CORES.muted} strokeWidth="2.4" strokeLinecap="round" />
        </svg>
        <div
          style={{
            marginLeft: 26,
            fontFamily: FONTE.texto,
            fontSize: 46,
            color: CORES.ink,
            whiteSpace: 'nowrap',
          }}
        >
          {texto.slice(0, digitado)}
          <span style={{opacity: caret ? 1 : 0, color: CORES.brand}}>|</span>
        </div>
        <div
          style={{
            position: 'absolute',
            right: 22,
            top: 22,
            width: 80,
            height: 80,
            borderRadius: '50%',
            background: CORES.brand,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            transform: `scale(${1 - 0.1 * enviado})`,
          }}
        >
          <svg width="40" height="40" viewBox="0 0 24 24" fill="none">
            <path
              d="M5 12h14M13 6l6 6-6 6"
              stroke="#fff"
              strokeWidth="2.6"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </div>
      </Cartao>
    </AbsoluteFill>
  );
};

/** Tela 2: a vitrine. O mesmo card do site, antes e depois de tocar em "10.10". */
const Tela2: React.FC<{t0: number}> = ({t0}) => {
  const frame = useCurrentFrame();
  const chega = prog(frame, t0, t0 + 20, saida);
  const troca = prog(frame, 170, 186, saida);
  const marca = prog(frame, 184, 196, saida);
  const sel = troca;
  const CARD_W = 540;
  const CARD_H = (CARD_W * 1570) / 1080;
  return (
    <AbsoluteFill style={{background: '#fff'}}>
      {/* seletor: dia normal | 10.10 */}
      <div
        style={{
          position: 'absolute',
          left: 220,
          top: 430,
          width: 640,
          height: 90,
          borderRadius: 45,
          background: LAV,
          border: `2px solid ${BORDA}`,
          opacity: chega,
        }}
      >
        <div
          style={{
            position: 'absolute',
            top: 7,
            left: 7 + sel * 313,
            width: 313,
            height: 76,
            borderRadius: 38,
            background: sel < 0.5 ? '#fff' : CORES.highlight,
            boxShadow: '0 6px 16px rgba(17,24,39,0.15)',
          }}
        />
        {['dia normal', dados.data].map((rot, i) => (
          <div
            key={rot}
            style={{
              position: 'absolute',
              top: 0,
              left: i * 320,
              width: 320,
              height: 90,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontFamily: FONTE.texto,
              fontWeight: 700,
              fontSize: 38,
              color: CORES.ink,
              opacity: i === (sel < 0.5 ? 0 : 1) ? 1 : 0.5,
            }}
          >
            {rot}
          </div>
        ))}
      </div>

      <div
        style={{
          position: 'absolute',
          left: CX - CARD_W / 2,
          top: 560,
          width: CARD_W,
          height: CARD_H,
          opacity: chega,
          transform: `translateY(${(1 - chega) * 80}px)`,
        }}
      >
        <Img
          src={staticFile('campanha/card-antes.png')}
          style={{
            position: 'absolute',
            inset: 0,
            width: '100%',
            opacity: 1 - troca,
            transform: `scale(${1 - 0.04 * troca})`,
            filter: 'drop-shadow(0 24px 40px rgba(76,29,149,0.22))',
          }}
        />
        <Img
          src={staticFile('campanha/card-agora.png')}
          style={{
            position: 'absolute',
            inset: 0,
            width: '100%',
            opacity: troca,
            transform: `scale(${0.96 + 0.04 * troca})`,
            filter: 'drop-shadow(0 24px 40px rgba(76,29,149,0.22))',
          }}
        />
      </div>

      {/* o selo que pula do canto do card depois da troca */}
      <div
        style={{
          position: 'absolute',
          left: 780,
          top: 560,
          opacity: marca,
          transform: `rotate(9deg) scale(${interpolate(marca, [0, 1], [0.2, 1])})`,
        }}
      >
        <div
          style={{
            background: CORES.highlight,
            color: CORES.ink,
            fontFamily: FONTE.texto,
            fontWeight: 700,
            fontSize: 44,
            lineHeight: 1,
            padding: '16px 26px',
            borderRadius: 22,
            textAlign: 'center',
            boxShadow: '0 14px 30px rgba(245,158,11,0.45)',
          }}
        >
          {EXTRA}
          <div style={{fontSize: 26, marginTop: 4}}>a mais</div>
        </div>
      </div>

      {/* o valor, em letra grande, trocando junto com o card */}
      <div
        style={{
          position: 'absolute',
          left: 0,
          right: 0,
          top: 1392,
          textAlign: 'center',
          fontFamily: FONTE.numero,
          fontWeight: 700,
          fontSize: 66,
          letterSpacing: '-0.04em',
          color: CORES.success,
          opacity: chega,
          whiteSpace: 'nowrap',
        }}
      >
        <span style={{opacity: 1 - troca, display: troca > 0.5 ? 'none' : 'inline'}}>
          {dados.produto.valorAntes}
        </span>
        <span style={{opacity: troca, display: troca > 0.5 ? 'inline' : 'none'}}>
          {dados.produto.valorAgora}
        </span>
        <span style={{fontFamily: FONTE.texto, fontSize: 40, color: CORES.muted}}> de cashback</span>
      </div>
    </AbsoluteFill>
  );
};

/** Uma linha de "o mínimo sobe": rótulo, barra com a parte que já existia e a que cresceu. */
const BarraMinimo: React.FC<{
  rotulo: string;
  antes: string;
  agora: string;
  y: number;
  de: number;
}> = ({rotulo, antes, agora, y, de}) => {
  const frame = useCurrentFrame();
  const num = (s: string) => parseFloat(s.replace('%', '').replace(',', '.'));
  const a = num(antes);
  const b = num(agora);
  const MAX = 2.4;
  const larg = 760;
  const entra = prog(frame, de - 8, de + 4, saida);
  const base = prog(frame, de, de + 12, saida);
  const extra = prog(frame, de + 14, de + 40, curva);
  const valor = a + (b - a) * extra;
  return (
    <Cartao
      style={{
        position: 'absolute',
        left: 90,
        top: y,
        width: 900,
        height: 360,
        padding: '40px 52px',
        opacity: entra,
        transform: `translateY(${(1 - entra) * 60}px)`,
      }}
    >
      <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start'}}>
        <div>
          <div style={{fontFamily: FONTE.texto, fontWeight: 700, fontSize: 46, color: CORES.ink}}>
            {rotulo}
          </div>
          <div style={{fontFamily: FONTE.texto, fontSize: 30, color: CORES.muted, marginTop: 4}}>
            cashback mínimo
          </div>
        </div>
        <div
          style={{
            fontFamily: FONTE.numero,
            fontWeight: 700,
            fontSize: 84,
            letterSpacing: '-0.05em',
            color: extra > 0.02 ? CORES.success : CORES.ink,
            whiteSpace: 'nowrap',
            lineHeight: 1,
          }}
        >
          {virgula(valor, 1).replace(/,0$/, '')}%
        </div>
      </div>
      <div
        style={{
          marginTop: 46,
          width: larg,
          height: 40,
          borderRadius: 20,
          background: LAV,
          overflow: 'hidden',
          position: 'relative',
        }}
      >
        <div
          style={{
            position: 'absolute',
            left: 0,
            top: 0,
            height: '100%',
            width: (a / MAX) * larg * base,
            background: CORES.brand,
            borderRadius: 20,
          }}
        />
        <div
          style={{
            position: 'absolute',
            left: (a / MAX) * larg - 20,
            top: 0,
            height: '100%',
            width: ((b - a) / MAX) * larg * extra + 20,
            background: CORES.success,
            borderRadius: 20,
          }}
        />
      </div>
      <div
        style={{
          marginTop: 18,
          display: 'flex',
          justifyContent: 'space-between',
          fontFamily: FONTE.texto,
          fontWeight: 700,
          fontSize: 30,
          color: CORES.muted,
          opacity: extra,
        }}
      >
        <span>antes: {antes}</span>
        <span style={{color: CORES.success}}>{EXTRA} a mais</span>
      </div>
    </Cartao>
  );
};

/** Tela 3: o mínimo sobe junto. */
const Tela3: React.FC<{t0: number}> = ({t0}) => (
  <AbsoluteFill style={{background: CORES.brandStrong}}>
    <div style={{position: 'absolute', left: 90, top: 410}}>
      <Sobe de={t0} tam={86} cor="#fff">
        O mínimo
      </Sobe>
      <Sobe de={t0 + 5} tam={86} cor={CORES.highlight}>
        também sobe.
      </Sobe>
    </div>
    <BarraMinimo
      rotulo="Por link ou vitrine"
      antes={dados.direta.antes}
      agora={dados.direta.agora}
      y={700}
      de={t0 + 20}
    />
    <BarraMinimo
      rotulo="Botão “Ir pra Shopee”"
      antes={dados.indireta.antes}
      agora={dados.indireta.agora}
      y={1100}
      de={t0 + 46}
    />
  </AbsoluteFill>
);

/** Tela 4: o cashback do exemplo chegando na conta, rumo ao saque. */
const Tela4: React.FC<{t0: number}> = ({t0}) => {
  const frame = useCurrentFrame();
  const entra = prog(frame, t0, t0 + 18, saida);
  const conta = prog(frame, t0 + 18, t0 + 50, curva);
  const alvo = parseFloat(dados.produto.valorAgora.replace('R$ ', '').replace(',', '.'));
  const barra = prog(frame, t0 + 40, t0 + 70, curva);
  const SAQUE = 20;
  return (
    <AbsoluteFill style={{background: LAV}}>
      <div style={{position: 'absolute', left: 90, top: 410}}>
        <Sobe de={t0} tam={86}>
          Depois é só
        </Sobe>
        <Sobe de={t0 + 5} tam={86} cor={CORES.brand}>
          juntar e sacar.
        </Sobe>
      </div>
      <Cartao
        style={{
          position: 'absolute',
          left: 90,
          top: 700,
          width: 900,
          padding: '52px 56px 56px',
          opacity: entra,
          transform: `translateY(${(1 - entra) * 70}px)`,
        }}
      >
        <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
          <div style={{fontFamily: FONTE.texto, fontWeight: 700, fontSize: 40, color: CORES.muted}}>
            seu cashback
          </div>
          <div
            style={{
              fontFamily: FONTE.texto,
              fontWeight: 700,
              fontSize: 28,
              background: 'rgba(245,158,11,0.18)',
              color: '#92400e',
              padding: '8px 20px',
              borderRadius: 999,
            }}
          >
            pendente
          </div>
        </div>
        <div
          style={{
            fontFamily: FONTE.numero,
            fontWeight: 700,
            fontSize: 150,
            letterSpacing: '-0.06em',
            color: CORES.success,
            marginTop: 18,
            whiteSpace: 'nowrap',
          }}
        >
          R$ {virgula(alvo * conta)}
        </div>
        <div style={{fontFamily: FONTE.texto, fontSize: 32, color: CORES.muted, marginTop: 4}}>
          até a Shopee validar a compra
        </div>
        <div
          style={{
            marginTop: 52,
            height: 34,
            borderRadius: 17,
            background: LAV,
            overflow: 'hidden',
          }}
        >
          <div
            style={{
              width: `${(alvo / SAQUE) * 100 * barra}%`,
              height: '100%',
              background: CORES.brand,
              borderRadius: 17,
            }}
          />
        </div>
        <div
          style={{
            marginTop: 16,
            display: 'flex',
            justifyContent: 'space-between',
            fontFamily: FONTE.numero,
            fontWeight: 700,
            fontSize: 30,
            color: CORES.muted,
          }}
        >
          <span>R$ 0</span>
          <span style={{color: CORES.brand}}>saque via Pix: R$ {SAQUE}</span>
        </div>
      </Cartao>
    </AbsoluteFill>
  );
};

/** Tela 5: o fecho. */
const Tela5: React.FC<{t0: number; anuncio?: boolean}> = ({t0, anuncio}) => {
  const frame = useCurrentFrame();
  const marca = prog(frame, t0, t0 + 20, saida);
  const pilula = prog(frame, t0 + 26, t0 + 40, saida);
  // no anúncio o botão respira de leve depois de aparecer, para chamar o olho sem piscar
  const pulso = anuncio ? 1 + 0.025 * Math.sin(Math.max(0, frame - (t0 + 44)) / 5) : 1;
  const rodape = prog(frame, t0 + 44, t0 + 56, saida);
  return (
    <AbsoluteFill
      style={{background: `linear-gradient(165deg, ${CORES.brandStrong} 0%, ${CORES.brand} 60%, #a78bfa 100%)`}}
    >
      <div
        style={{
          position: 'absolute',
          left: 0,
          right: 0,
          top: 540,
          textAlign: 'center',
          fontFamily: FONTE.texto,
          fontWeight: 700,
          fontSize: 230,
          letterSpacing: '-0.05em',
          color: '#fff',
          whiteSpace: 'nowrap',
          opacity: marca,
          transform: `translateY(${(1 - marca) * 60}px)`,
        }}
      >
        cash-b
      </div>
      <div style={{position: 'absolute', left: 0, right: 0, top: 850}}>
        <Sobe de={t0 + 12} tam={72} cor={CORES.highlight} align="center">
          {EXTRA} a mais de cashback
        </Sobe>
        <Sobe de={t0 + 18} tam={72} cor="#fff" align="center">
          no dia {dados.diaMes}
        </Sobe>
      </div>
      <div
        style={{
          position: 'absolute',
          left: 0,
          right: 0,
          top: 1160,
          display: 'flex',
          justifyContent: 'center',
          opacity: pilula,
          transform: `scale(${interpolate(pilula, [0, 1], [0.7, 1]) * pulso})`,
        }}
      >
        <div
          style={{
            background: '#fff',
            color: CORES.brandStrong,
            fontFamily: anuncio ? FONTE.texto : FONTE.numero,
            fontWeight: 700,
            fontSize: anuncio ? 62 : 54,
            letterSpacing: anuncio ? '-0.02em' : undefined,
            padding: anuncio ? '26px 64px' : '22px 58px',
            borderRadius: 999,
            boxShadow: '0 20px 50px rgba(17,10,50,0.35)',
            whiteSpace: 'nowrap',
          }}
        >
          {anuncio ? 'Cadastre-se grátis →' : 'cash-b.com'}
        </div>
      </div>
      {anuncio ? (
        <div
          style={{
            position: 'absolute',
            left: 0,
            right: 0,
            top: 1340,
            textAlign: 'center',
            fontFamily: FONTE.numero,
            fontWeight: 700,
            fontSize: 38,
            color: 'rgba(255,255,255,0.88)',
            opacity: rodape,
          }}
        >
          cash-b.com
          <div style={{fontFamily: FONTE.texto, fontWeight: 400, fontSize: 34, marginTop: 10, opacity: 0.85}}>
            Sem mensalidade. Sem taxa.
          </div>
        </div>
      ) : null}
    </AbsoluteFill>
  );
};

// ------------------------------------------------------------------------------ a montagem

export const CampanhaRolagem: React.FC<{anuncio?: boolean}> = ({anuncio}) => {
  const frame = useCurrentFrame();
  const y = rolagemEm(frame);
  // borrão de movimento vertical, proporcional à velocidade da rolagem
  const v = Math.abs(rolagemEm(frame + 1) - rolagemEm(frame - 1)) / 2;
  const borrao = Math.min(v / 38, 22);

  return (
    <AbsoluteFill style={{background: LAV, overflow: 'hidden'}}>
      <svg width={0} height={0} style={{position: 'absolute'}}>
        <filter id="rolagem" x="-5%" y="-5%" width="110%" height="110%">
          <feGaussianBlur stdDeviation={`0 ${borrao}`} />
        </filter>
      </svg>
      <div
        style={{
          position: 'absolute',
          left: 0,
          top: 0,
          width: W,
          height: H * 5,
          transform: `translateY(${-y}px)`,
          filter: borrao > 0.4 ? 'url(#rolagem)' : undefined,
        }}
      >
        {[<Tela1 key={1} />, <Tela2 key={2} t0={ROLAGENS[0][0] + 6} />, <Tela3 key={3} t0={ROLAGENS[1][0] + 6} />, <Tela4 key={4} t0={ROLAGENS[2][0] + 6} />, <Tela5 key={5} t0={ROLAGENS[3][0] + 6} anuncio={anuncio} />].map(
          (tela, i) => (
            <div key={i} style={{position: 'absolute', left: 0, top: i * H, width: W, height: H}}>
              {tela}
            </div>
          ),
        )}
      </div>
      {/* o dedo fica no quadro, não na página: acompanha o que está parado na tela */}
      <Dedo />
    </AbsoluteFill>
  );
};
