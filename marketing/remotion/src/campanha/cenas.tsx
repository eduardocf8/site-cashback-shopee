import React from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame} from 'remotion';
import {CORES, FONTE} from '../marca';
import {CX, H, W, prog, saida, suave} from '../animada/util';
import dados from './dados.json';
import {CREME, Casa, Serrilha, TINTA_ESCURA, Tracejado, sequencia} from './pecas';

/** As cinco cenas do reel da campanha 10.10 (18 s, 30 fps).
 *
 * Todo número e todo texto de campanha vem de `dados.json`, gerado por
 * `exportar_dados_campanha.py` a partir das mesmas constantes do banner do e-mail, dos
 * stories e do carrossel. */

const EXTRA = `${dados.percentualExtra}%`;

/** Linha de texto que sobe de dentro de uma máscara. Mais limpo que fade, e é a mesma
 * assinatura em todas as cenas. */
const LinhaSobe: React.FC<{
  inicio: number;
  tam: number;
  cor?: string;
  children: React.ReactNode;
  peso?: number;
  fonte?: string;
}> = ({inicio, tam, cor = '#fff', children, peso = 700, fonte = FONTE.texto}) => {
  const frame = useCurrentFrame();
  const p = prog(frame, inicio, inicio + 16, saida);
  return (
    <div style={{overflow: 'hidden', paddingBottom: tam * 0.12, marginBottom: -tam * 0.12}}>
      <div
        style={{
          transform: `translateY(${(1 - p) * 115}%)`,
          fontFamily: fonte,
          fontWeight: peso,
          fontSize: tam,
          lineHeight: 1.04,
          letterSpacing: '-0.03em',
          color: cor,
          whiteSpace: 'nowrap',
          textAlign: 'center',
        }}
      >
        {children}
      </div>
    </div>
  );
};

// ----------------------------------------------------------------------------- 1. calendário

const DIAS_SEMANA = ['D', 'S', 'T', 'Q', 'Q', 'S', 'S'];
// 1º de outubro de 2026 cai numa quinta-feira (índice 4, com domingo = 0).
const PRIMEIRO_DIA = 4;
const DIAS_NO_MES = 31;
const GX = 90;
const GW = 900;
const COL = GW / 7;
const LIN = 112;
const GY = 870;

export const CenaCalendario: React.FC<{dur: number}> = ({dur}) => {
  const frame = useCurrentFrame();
  const DIA = 10;
  const idx = PRIMEIRO_DIA + DIA - 1;
  const linha = Math.floor(idx / 7);
  const col = idx % 7;
  const cx = GX + col * COL;
  const cy = GY + linha * LIN;

  // a inundação: a casa do dia 10 cresce até cobrir o quadro, na cor do fundo da cena 2
  const fp = prog(frame, 76, dur, suave);
  const caixa = {
    left: interpolate(fp, [0, 1], [cx + 5, 0]),
    top: interpolate(fp, [0, 1], [cy + 5, 0]),
    width: interpolate(fp, [0, 1], [COL - 10, W]),
    height: interpolate(fp, [0, 1], [LIN - 10, H]),
    raio: interpolate(fp, [0, 1], [16, 0]),
  };
  const acende = prog(frame, 44, 56, saida);
  const pulo = interpolate(acende, [0, 0.5, 1], [0, 1.18, 1]);
  // Só entra quando a inundação já cobre o quadro: tinta escura sobre o fundo escuro some.
  const slam = prog(frame, 106, 118, saida);
  const sumirTitulo = 1 - prog(frame, 70, 84, suave);

  return (
    <AbsoluteFill style={{background: TINTA_ESCURA}}>
      <AbsoluteFill
        style={{
          background:
            'radial-gradient(900px 700px at 80% 40%, rgba(109,40,217,0.35), transparent 70%)',
        }}
      />

      <div style={{position: 'absolute', left: 0, right: 0, top: 410, opacity: sumirTitulo}}>
        <LinhaSobe inicio={6} tam={128}>
          Tem dia
        </LinhaSobe>
        <LinhaSobe inicio={14} tam={128}>
          que vale <span style={{color: CORES.highlight}}>mais.</span>
        </LinhaSobe>
      </div>

      <div
        style={{
          position: 'absolute',
          left: GX,
          top: GY - 150,
          fontFamily: FONTE.numero,
          fontSize: 34,
          fontWeight: 700,
          letterSpacing: 6,
          color: CORES.highlight,
          opacity: prog(frame, 6, 18) * sumirTitulo,
        }}
      >
        OUTUBRO 2026
      </div>

      {DIAS_SEMANA.map((d, i) => (
        <div
          key={`h${i}`}
          style={{
            position: 'absolute',
            left: GX + i * COL,
            top: GY - 64,
            width: COL,
            textAlign: 'center',
            fontFamily: FONTE.numero,
            fontWeight: 700,
            fontSize: 30,
            color: 'rgba(255,255,255,0.4)',
            opacity: prog(frame, 8, 20) * sumirTitulo,
          }}
        >
          {d}
        </div>
      ))}

      {Array.from({length: DIAS_NO_MES}, (_, i) => i + 1).map((d) => {
        const k = PRIMEIRO_DIA + d - 1;
        const r = Math.floor(k / 7);
        const c = k % 7;
        const p = prog(frame, 10 + (r + c) * 2, 22 + (r + c) * 2, saida);
        const eh = d === DIA;
        return (
          <div
            key={d}
            style={{
              position: 'absolute',
              left: GX + c * COL,
              top: GY + r * LIN,
              width: COL,
              height: LIN,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontFamily: FONTE.numero,
              fontWeight: 700,
              fontSize: 46,
              color: eh && acende > 0.5 ? TINTA_ESCURA : 'rgba(255,255,255,0.5)',
              opacity: p * (eh ? 1 : 1 - fp),
              transform: `scale(${0.6 + 0.4 * p})`,
            }}
          >
            {eh && acende > 0 ? null : d}
          </div>
        );
      })}

      {/* o dia 10: acende em âmbar, dá um pulo e vira a tela inteira */}
      <div
        style={{
          position: 'absolute',
          left: caixa.left,
          top: caixa.top,
          width: caixa.width,
          height: caixa.height,
          borderRadius: caixa.raio,
          background: CORES.highlight,
          transform: fp === 0 ? `scale(${pulo})` : undefined,
          opacity: acende,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontFamily: FONTE.numero,
          fontWeight: 700,
          fontSize: 56,
          color: TINTA_ESCURA,
        }}
      >
        <span style={{opacity: 1 - prog(frame, 76, 92)}}>{DIA}</span>
      </div>

      {/* chegada do título da cena seguinte, no mesmo lugar em que ela o desenha */}
      <TituloData opacidade={slam} escala={interpolate(slam, [0, 1], [1.35, 1])} />
    </AbsoluteFill>
  );
};

/** "10.10" do alto da cena 2. Existe nas duas cenas, no mesmo pixel, para a passagem de uma
 * para a outra não ter emenda. */
export const TituloData: React.FC<{opacidade?: number; escala?: number}> = ({
  opacidade = 1,
  escala = 1,
}) => (
  <div
    style={{
      position: 'absolute',
      left: 0,
      right: 0,
      top: 400,
      textAlign: 'center',
      fontFamily: FONTE.texto,
      fontWeight: 700,
      fontSize: 250,
      lineHeight: 1,
      letterSpacing: '-0.05em',
      color: TINTA_ESCURA,
      opacity: opacidade,
      transform: `scale(${escala})`,
      whiteSpace: 'nowrap',
    }}
  >
    {dados.data}
  </div>
);

// ----------------------------------------------------------------------------- 2. letreiro

const Linha: React.FC<{
  rotulo: string;
  de: string[];
  para: string[];
  y: number;
  entra: number;
  gira: number;
  chave: number;
}> = ({rotulo, de, para, y, entra, gira, chave}) => {
  const frame = useCurrentFrame();
  const p = prog(frame, entra, entra + 14, saida);
  return (
    <div style={{position: 'absolute', left: 0, right: 0, top: y, opacity: p}}>
      <div
        style={{
          textAlign: 'center',
          fontFamily: FONTE.texto,
          fontWeight: 700,
          fontSize: 42,
          color: TINTA_ESCURA,
          marginBottom: 18,
          transform: `translateY(${(1 - p) * 30}px)`,
        }}
      >
        {rotulo}
      </div>
      <div style={{display: 'flex', justifyContent: 'center', gap: 12}}>
        {de.map((c, i) => (
          <Casa
            key={i}
            seq={sequencia(c, para[i], chave + i)}
            inicio={gira + i * 4}
            largura={para[i] === ',' ? 96 : undefined}
          />
        ))}
      </div>
    </div>
  );
};

export const CenaLetreiro: React.FC = () => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{background: CORES.highlight}}>
      <TituloData />
      <div
        style={{
          position: 'absolute',
          left: 0,
          right: 0,
          top: 690,
          opacity: prog(frame, 20, 34),
        }}
      >
        <LinhaSobe inicio={22} tam={58} cor={TINTA_ESCURA}>
          {EXTRA} a mais de cashback
        </LinhaSobe>
      </div>
      <Linha
        rotulo="por link ou vitrine"
        de={dados.direta.antes.split('')}
        para={dados.direta.agora.split('')}
        y={860}
        entra={30}
        gira={56}
        chave={1}
      />
      <Linha
        rotulo="botão “Ir pra Shopee”"
        // O 1% antigo tem uma casa a menos que o 1,5% novo: as casas que faltam à esquerda
        // ficam vazias e "viram" dígito, como num letreiro de verdade.
        de={dados.indireta.antes.padStart(dados.indireta.agora.length, ' ').split('')}
        para={dados.indireta.agora.split('')}
        y={1190}
        entra={38}
        gira={88}
        chave={5}
      />
      <div
        style={{
          position: 'absolute',
          left: 0,
          right: 0,
          top: 786,
          textAlign: 'center',
          fontFamily: FONTE.numero,
          fontWeight: 700,
          fontSize: 28,
          letterSpacing: 5,
          color: TINTA_ESCURA,
          opacity: 0.7 * prog(frame, 34, 48),
        }}
      >
        CASHBACK MÍNIMO
      </div>
    </AbsoluteFill>
  );
};

// ----------------------------------------------------------------------------- 3. recibo

const PAPEL_W = 700;
const RANHURA_Y = 450;

export const CenaRecibo: React.FC = () => {
  const frame = useCurrentFrame();
  // o papel sai da ranhura aos trancos, como impressora térmica: o avanço é quantizado
  const imprime = prog(frame, 4, 70);
  const degrau = Math.floor(imprime * 34) / 34;
  const altura = 860;
  const desce = (1 - degrau) * -altura;

  const risco = prog(frame, 78, 90, suave);
  const conta = prog(frame, 84, 108, suave);
  const [vAntes, vAgora] = [4.05, 6.08];
  const valor = vAntes + (vAgora - vAntes) * conta;
  const textoValor = `R$ ${valor.toFixed(2).replace('.', ',')}`;
  const final = conta >= 1 ? dados.produto.valorAgora : textoValor;
  const slam = prog(frame, 112, 122, saida);
  const anel = prog(frame, 112, 132);

  return (
    <AbsoluteFill style={{background: TINTA_ESCURA}}>
      <AbsoluteFill
        style={{
          background:
            'radial-gradient(800px 800px at 20% 80%, rgba(109,40,217,0.35), transparent 70%)',
        }}
      />

      {/* a ranhura da impressora */}
      <div
        style={{
          position: 'absolute',
          left: CX - PAPEL_W / 2 - 40,
          width: PAPEL_W + 80,
          top: RANHURA_Y - 34,
          height: 34,
          background: '#2a2840',
          borderRadius: '17px 17px 0 0',
          zIndex: 5,
          boxShadow: `0 0 40px ${CORES.highlight}55`,
        }}
      >
        <div
          style={{
            position: 'absolute',
            left: 30,
            right: 30,
            bottom: 0,
            height: 6,
            borderRadius: 3,
            background: CORES.highlight,
          }}
        />
      </div>

      {/* só se vê o papel abaixo da ranhura */}
      <div
        style={{
          position: 'absolute',
          left: CX - PAPEL_W / 2,
          width: PAPEL_W,
          top: RANHURA_Y,
          height: H - RANHURA_Y,
          overflow: 'hidden',
        }}
      >
        <div style={{transform: `translateY(${desce}px)`}}>
          <div
            style={{
              background: CREME,
              padding: '44px 48px 20px',
              fontFamily: FONTE.numero,
              color: CORES.ink,
              height: altura,
              position: 'relative',
            }}
          >
            <div
              style={{
                textAlign: 'center',
                fontFamily: FONTE.texto,
                fontWeight: 700,
                fontSize: 66,
                letterSpacing: '-0.03em',
                whiteSpace: 'nowrap',
              }}
            >
              cash-b
            </div>
            <div
              style={{
                textAlign: 'center',
                fontSize: 24,
                letterSpacing: 4,
                color: CORES.muted,
                marginTop: 4,
              }}
            >
              RECIBO DE EXEMPLO
            </div>
            <Tracejado />

            <div style={{fontFamily: FONTE.texto, fontWeight: 700, fontSize: 40}}>
              {dados.produto.nome}
            </div>
            <div style={{display: 'flex', justifyContent: 'space-between', fontSize: 34, marginTop: 10}}>
              <span style={{color: CORES.muted}}>preço base</span>
              <span style={{fontWeight: 700}}>{dados.produto.preco}</span>
            </div>
            <Tracejado />

            <div style={{display: 'flex', justifyContent: 'space-between', fontSize: 34}}>
              <span style={{color: CORES.muted}}>cashback normal</span>
              <span style={{position: 'relative', fontWeight: 700}}>
                {dados.produto.valorAntes}
                <span
                  style={{
                    position: 'absolute',
                    left: -6,
                    top: '52%',
                    height: 5,
                    width: `${risco * 112}%`,
                    background: CORES.highlight,
                    borderRadius: 3,
                  }}
                />
              </span>
            </div>

            <div style={{marginTop: 34, opacity: prog(frame, 80, 90)}}>
              <div
                style={{
                  display: 'inline-block',
                  fontSize: 26,
                  fontWeight: 700,
                  letterSpacing: 3,
                  background: CORES.highlight,
                  color: TINTA_ESCURA,
                  padding: '6px 16px',
                  borderRadius: 8,
                }}
              >
                {dados.data} · {EXTRA} A MAIS
              </div>
              <div
                style={{
                  fontWeight: 700,
                  fontSize: 108,
                  letterSpacing: '-0.04em',
                  color: CORES.success,
                  marginTop: 8,
                  whiteSpace: 'nowrap',
                }}
              >
                {final}
              </div>
              <div style={{fontSize: 28, color: CORES.muted}}>de cashback</div>
            </div>
            <Tracejado />
            <div style={{textAlign: 'center', fontSize: 24, color: CORES.muted, letterSpacing: 2}}>
              PEDIDO FEITO NO DIA {dados.diaMes}
            </div>
          </div>
          <Serrilha cor={CREME} />
        </div>
      </div>

      {/* o carimbo */}
      <div
        style={{
          position: 'absolute',
          left: CX + 110,
          top: 1090,
          zIndex: 6,
          opacity: slam,
          transform: `rotate(-13deg) scale(${interpolate(slam, [0, 1], [2.4, 1])})`,
        }}
      >
        <div
          style={{
            border: `10px solid ${CORES.highlight}`,
            borderRadius: 24,
            padding: '8px 30px 6px',
            color: CORES.highlight,
            fontFamily: FONTE.texto,
            fontWeight: 700,
            textAlign: 'center',
            background: 'rgba(15,13,28,0.88)',
            lineHeight: 1,
          }}
        >
          <div style={{fontSize: 118, letterSpacing: '-0.04em'}}>{dados.data}</div>
          <div style={{fontSize: 34, letterSpacing: 3, marginTop: 4}}>{EXTRA} A MAIS</div>
        </div>
      </div>
      <div
        style={{
          position: 'absolute',
          left: CX + 110 + 150 - 260 * anel,
          top: 1090 + 100 - 260 * anel,
          width: 520 * anel,
          height: 520 * anel,
          borderRadius: '50%',
          border: `6px solid ${CORES.highlight}`,
          opacity: (1 - anel) * (anel > 0 ? 0.7 : 0),
          zIndex: 4,
        }}
      />
    </AbsoluteFill>
  );
};

// ----------------------------------------------------------------------------- 4. as 24 horas

export const CenaDia: React.FC = () => {
  const frame = useCurrentFrame();
  const t = prog(frame, 10, 66, suave);
  const minutos = Math.round(t * (24 * 60 - 1));
  const hh = String(Math.floor(minutos / 60)).padStart(2, '0');
  const mm = String(minutos % 60).padStart(2, '0');
  const fim = prog(frame, 66, 74, saida);

  return (
    <AbsoluteFill
      style={{background: 'linear-gradient(170deg, #047857 0%, #064e3b 100%)'}}
    >
      <div style={{position: 'absolute', left: 0, right: 0, top: 430}}>
        <LinhaSobe inicio={2} tam={70}>
          No dia {dados.diaMes},
        </LinhaSobe>
      </div>

      <div
        style={{
          position: 'absolute',
          left: 0,
          right: 0,
          top: 600,
          textAlign: 'center',
          fontFamily: FONTE.numero,
          fontWeight: 700,
          fontSize: 270,
          letterSpacing: '-0.06em',
          color: '#fff',
          transform: `scale(${interpolate(fim, [0, 1], [1, 1.06])})`,
        }}
      >
        {hh}:{mm}
      </div>

      <div style={{position: 'absolute', left: GX, top: 960, width: GW}}>
        <div
          style={{
            height: 30,
            borderRadius: 15,
            background: 'rgba(255,255,255,0.18)',
            overflow: 'hidden',
          }}
        >
          <div
            style={{
              width: `${t * 100}%`,
              height: '100%',
              background: CREME,
              borderRadius: 15,
            }}
          />
        </div>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            marginTop: 16,
            fontFamily: FONTE.numero,
            fontWeight: 700,
            fontSize: 32,
            color: 'rgba(255,255,255,0.7)',
          }}
        >
          <span>0h</span>
          <span>23h59</span>
        </div>
      </div>

      <div style={{position: 'absolute', left: 0, right: 0, top: 1130}}>
        <LinhaSobe inicio={68} tam={84}>
          todo pedido vale
        </LinhaSobe>
        <LinhaSobe inicio={74} tam={110} cor={CORES.highlight}>
          {EXTRA} a mais
        </LinhaSobe>
      </div>
    </AbsoluteFill>
  );
};

// ----------------------------------------------------------------------------- 5. fecho

export const CenaFecho: React.FC = () => {
  const frame = useCurrentFrame();
  const marca = prog(frame, 4, 22, saida);
  const barra = prog(frame, 14, 32, saida);
  const carimbo = prog(frame, 30, 42, saida);

  return (
    <AbsoluteFill style={{background: CREME}}>
      <div
        style={{
          position: 'absolute',
          left: 0,
          right: 0,
          top: 560,
          textAlign: 'center',
          fontFamily: FONTE.texto,
          fontWeight: 700,
          fontSize: 230,
          letterSpacing: '-0.05em',
          color: CORES.ink,
          whiteSpace: 'nowrap',
          opacity: marca,
          transform: `translateY(${(1 - marca) * 60}px)`,
        }}
      >
        cash-b
      </div>
      <div
        style={{
          position: 'absolute',
          left: CX - 160,
          top: 830,
          width: 320 * barra,
          height: 14,
          marginLeft: 160 * (1 - barra),
          borderRadius: 7,
          background: CORES.highlight,
        }}
      />
      <div style={{position: 'absolute', left: 0, right: 0, top: 900}}>
        <LinhaSobe inicio={18} tam={66} cor={CORES.ink}>
          {EXTRA} a mais de cashback
        </LinhaSobe>
        <LinhaSobe inicio={24} tam={66} cor={CORES.brand}>
          no dia {dados.diaMes}
        </LinhaSobe>
      </div>
      <div
        style={{
          position: 'absolute',
          left: 0,
          right: 0,
          top: 1180,
          display: 'flex',
          justifyContent: 'center',
          opacity: carimbo,
          transform: `scale(${interpolate(carimbo, [0, 1], [1.4, 1])})`,
        }}
      >
        <div
          style={{
            background: CORES.ink,
            color: CREME,
            fontFamily: FONTE.numero,
            fontWeight: 700,
            fontSize: 54,
            letterSpacing: 2,
            padding: '20px 54px',
            borderRadius: 999,
          }}
        >
          cash-b.com
        </div>
      </div>
    </AbsoluteFill>
  );
};
