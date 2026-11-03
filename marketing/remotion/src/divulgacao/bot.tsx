/** Tema 1: Bot de WhatsApp. Três versões:
 * - BotAntesDepois: o passo a passo de postar na mão contra um botão que liga tudo.
 * - BotUmDia: das 8h às 22h, o grupo recebendo ofertas enquanto você vive o seu dia.
 * - BotCampanha: as datas da Shopee no modo campanha (ritmo, texto e cupom próprios). */
import React from 'react';
import {AbsoluteFill, Sequence, useCurrentFrame, useVideoConfig} from 'remotion';
import {C, FONTE} from '../appfiliado/marca';
import {Interruptor} from '../appfiliado/ui';
import {Apoio, Cabecalho, Celular, CelularNaCena, Cena, Chapeu, Conta, ConversaZap, Cortina, DURACAO_FINAL, Etiqueta, Final, Fundo, Legendas, type Mensagem, POS, Titulo, Toque, mola, s, vai} from './comum';
import {CTA, GRUPO, INCLUSOS, OFERTAS} from './textos';

const ESCURO_AMARELO = '#8A6A00';

// --- BotAntesDepois --------------------------------------------------------------------------------

const PASSOS = ['Achar o produto', 'Gerar o seu link de afiliado', 'Escrever a mensagem', 'Colar em cada grupo', 'Repetir o dia todo'];

const NaMao: React.FC = () => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const minutos = Math.round(vai(f, 30, 128, 0, 135));
  const risco = vai(f, 128, 146);
  return (
    <AbsoluteFill style={{fontFamily: FONTE, color: C.tinta}}>
      <Fundo tom="creme" />
      <div style={{position: 'absolute', left: 90, right: 90, top: 330}}>
        <Chapeu texto="Bot de WhatsApp" inicio={-14} />
        <Titulo texto={'Postar oferta\n*na mão* é assim:'} inicio={-12} tamanho={100} destaque={ESCURO_AMARELO} style={{marginTop: 26}} />
      </div>
      <div style={{position: 'absolute', left: 90, right: 90, top: 690, display: 'grid', gap: 22}}>
        {PASSOS.map((p, i) => {
          const t = mola(f, 30 + i * 18, fps, 14);
          return (
            <div key={p} style={{position: 'relative', display: 'flex', alignItems: 'center', gap: 26, background: C.branco, border: `3px solid ${C.borda}`, borderRadius: 30,
              padding: '26px 32px', opacity: Math.min(1, t * 1.4), transform: `translateX(${(1 - t) * -80}px)`}}>
              <div style={{width: 62, height: 62, borderRadius: '50%', background: C.verde, color: C.creme, display: 'grid', placeItems: 'center', fontSize: 30, fontWeight: 800, flex: 'none'}}>{i + 1}</div>
              <div style={{fontSize: 42, fontWeight: 800, flex: 1}}>{p}</div>
              <div style={{fontSize: 30, fontWeight: 800, color: '#B4472F'}}>{i === PASSOS.length - 1 ? '↻' : '+ min'}</div>
              <div style={{position: 'absolute', left: 28, top: '50%', height: 7, borderRadius: 4, background: '#B4472F', width: `${vai(f, 128 + i * 3, 140 + i * 3) * 92}%`, opacity: risco > 0 ? 1 : 0}} />
            </div>
          );
        })}
      </div>
      <div style={{position: 'absolute', left: 90, right: 90, top: 1390, display: 'flex', alignItems: 'center', gap: 24, opacity: vai(f, 30, 44)}}>
        <div style={{fontSize: 64}}>⏱️</div>
        <div>
          <div style={{fontSize: 30, color: C.cinza, fontWeight: 500}}>do seu dia, todo dia</div>
          <div style={{fontSize: 76, fontWeight: 800, letterSpacing: '-.03em', fontVariantNumeric: 'tabular-nums'}}>
            {Math.floor(minutos / 60)}h{String(minutos % 60).padStart(2, '0')}
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};

/** "08:00" + minutos -> "09:15". */
export const horario = (inicio: number, minutos: number) => {
  const t = inicio * 60 + minutos;
  return `${String(Math.floor(t / 60) % 24).padStart(2, '0')}:${String(t % 60).padStart(2, '0')}`;
};

const NO_AUTOMATICO: Mensagem[] = OFERTAS.slice(0, 6).map((o, i) => ({...o, tipo: 'oferta', f: 70 + i * 34, hora: horario(8, i * 15)}));

const NoAutomatico: React.FC<{duracao: number}> = ({duracao}) => {
  const f = useCurrentFrame();
  const ligado = vai(f, 44, 52);
  return (
    <AbsoluteFill style={{fontFamily: FONTE, color: C.creme}}>
      <Fundo tom="escuro" />
      <Cabecalho chapeu="Com o Appfiliado" titulo={'Um botão\ne *pronto.*'} inicio={4} escuro tamanho={96} />
      <div style={{position: 'absolute', right: 90, top: POS.titulo + 70, width: 330, background: C.branco, color: C.tinta, borderRadius: 30, padding: '22px 26px',
        boxShadow: '0 24px 50px rgba(0,0,0,.25)', opacity: vai(f, 14, 28), transform: `translateY(${(1 - vai(f, 14, 28)) * 30}px)`}}>
        <div style={{fontSize: 22, fontWeight: 800, letterSpacing: '.1em', color: ESCURO_AMARELO, textTransform: 'uppercase'}}>Automação</div>
        <div style={{display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 10}}>
          <div style={{fontSize: 32, fontWeight: 800}}>{ligado > 0.5 ? 'Ligada' : 'Desligada'}</div>
          <div style={{transform: 'scale(1.15)', transformOrigin: 'right center'}}><Interruptor ligado={ligado} /></div>
        </div>
        <Toque x={260} y={76} f={46} />
      </div>
      <CelularNaCena hora="8:00" inicio={6}>
        <ConversaZap nome={GRUPO.nome} membros={GRUPO.membros} mensagens={NO_AUTOMATICO} />
      </CelularNaCena>
      <Legendas falas={[
        {f: 70, texto: 'Ofertas chegando no grupo', icone: '📲'},
        {f: 130, texto: 'Com o seu link de afiliado', icone: '🔗', tom: 'amarelo'},
        {f: 200, texto: <span><Conta de={8} ate={24} inicio={205} duracao={duracao - 215} /> ofertas hoje, no automático</span>, icone: '📤'},
      ]} />
    </AbsoluteFill>
  );
};

const AD = {naMao: s(5.5), automatico: s(10), final: DURACAO_FINAL.comInclusos};
export const DURACAO_BOT_ANTES_DEPOIS = AD.naMao + AD.automatico + AD.final;

export const BotAntesDepois: React.FC = () => (
  <AbsoluteFill style={{background: C.verde}}>
    <Sequence durationInFrames={AD.naMao}><Cena duracao={AD.naMao} entrada={false} saida={false}><NaMao /></Cena></Sequence>
    <Sequence from={AD.naMao} durationInFrames={AD.automatico}><Cena duracao={AD.automatico} entrada={false} saida={false}><NoAutomatico duracao={AD.automatico} /></Cena></Sequence>
    <Sequence from={AD.naMao - 9} durationInFrames={18}><Cortina /></Sequence>
    <Sequence from={AD.naMao + AD.automatico} durationInFrames={AD.final}><Final frase={'Seus grupos\n*no automático.*'} linha={CTA.bot} inclusos={INCLUSOS} /></Sequence>
    <Sequence from={AD.naMao + AD.automatico - 9} durationInFrames={18}><Cortina /></Sequence>
  </AbsoluteFill>
);


// --- BotUmDia ---------------------------------------------------------------------------------------

// O relógio vai das 8h às 22h; sai uma oferta a cada 15 min (o menor intervalo do Standard), 57 no dia.
const UM_DIA = {cena: s(16), final: s(4)};
const RELOGIO = {de: 20, ate: UM_DIA.cena - 24, inicio: 8 * 60, fim: 22 * 60};
const minutoNoFrame = (f: number) => vai(f, RELOGIO.de, RELOGIO.ate, RELOGIO.inicio, RELOGIO.fim, (t) => t);
const frameNoMinuto = (m: number) => RELOGIO.de + ((m - RELOGIO.inicio) / (RELOGIO.fim - RELOGIO.inicio)) * (RELOGIO.ate - RELOGIO.de);
const hhmm = (m: number) => `${String(Math.floor(m / 60)).padStart(2, '0')}:${String(Math.floor(m % 60)).padStart(2, '0')}`;

const MOMENTOS = [
  {desde: 8 * 60, emoji: '🚌', texto: 'você indo pro trabalho'},
  {desde: 12 * 60, emoji: '🍽️', texto: 'você no almoço'},
  {desde: 14 * 60, emoji: '💼', texto: 'você em reunião'},
  {desde: 18 * 60, emoji: '🏃', texto: 'você na academia'},
  {desde: 20 * 60, emoji: '🍿', texto: 'você vendo série'},
];

// as ofertas que aparecem no celular (uma a cada ~1h45 de relógio, para dar tempo de ler)
const DO_DIA: Mensagem[] = [
  {tipo: 'texto', f: 26, hora: '08:00', texto: 'Bom dia! ☀️ As ofertas de hoje começam agora.'} as Mensagem,
  ...[8 * 60 + 15, 10 * 60, 11 * 60 + 45, 13 * 60 + 30, 15 * 60 + 15, 17 * 60, 18 * 60 + 45, 20 * 60 + 30].map((m, i) => ({
  ...OFERTAS[i % OFERTAS.length], tipo: 'oferta', f: Math.round(frameNoMinuto(m)), hora: hhmm(m),
}) as Mensagem),
];

const UmDia: React.FC = () => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const minuto = minutoNoFrame(f);
  const noite = vai(minuto, 17 * 60, 20 * 60);
  const atual = [...MOMENTOS].reverse().find((m) => minuto >= m.desde) ?? MOMENTOS[0];
  const troca = mola(f, Math.round(frameNoMinuto(atual.desde)), fps, 14);
  const ofertas = Math.min(57, Math.floor((minuto - RELOGIO.inicio) / 15) + 1);
  return (
    <AbsoluteFill style={{fontFamily: FONTE, color: C.tinta}}>
      <Fundo tom="creme" />
      <AbsoluteFill style={{opacity: noite}}><Fundo tom="escuro" /></AbsoluteFill>
      <div style={{position: 'absolute', left: 80, right: 80, top: 320, background: C.branco, borderRadius: 44, padding: '34px 40px', display: 'flex', alignItems: 'center', gap: 34,
        boxShadow: '0 24px 50px rgba(23,48,31,.14)', opacity: vai(f, -8, 6), transform: `translateY(${(1 - vai(f, -8, 6)) * 30}px)`}}>
        <div style={{flex: 'none'}}>
          <div style={{fontSize: 26, fontWeight: 800, letterSpacing: '.12em', color: ESCURO_AMARELO, textTransform: 'uppercase'}}>{noite > 0.5 ? '🌙 Hoje' : '☀️ Hoje'}</div>
          <div style={{fontSize: 150, fontWeight: 800, letterSpacing: '-.05em', lineHeight: 1, fontVariantNumeric: 'tabular-nums', marginTop: 6}}>{hhmm(minuto)}</div>
        </div>
        <div style={{flex: 1, borderLeft: `3px solid ${C.borda}`, paddingLeft: 30, minHeight: 170, display: 'flex', flexDirection: 'column', justifyContent: 'center'}}>
          <div style={{fontSize: 56, transform: `scale(${0.6 + 0.4 * troca})`, transformOrigin: 'left center'}}>{atual.emoji}</div>
          <div style={{fontSize: 38, fontWeight: 800, lineHeight: 1.12, marginTop: 6, opacity: troca, transform: `translateY(${(1 - troca) * 20}px)`}}>{atual.texto}</div>
        </div>
      </div>
      <div style={{position: 'absolute', left: 0, right: 0, top: 690, display: 'flex', justifyContent: 'center'}}>
        <Celular escala={0.78} hora={hhmm(minuto).replace(/^0/, '')}>
          <ConversaZap nome={GRUPO.nome} membros={GRUPO.membros} mensagens={DO_DIA} />
        </Celular>
      </div>
      <div style={{position: 'absolute', right: 56, top: 820}}><Etiqueta texto="🔗 Seu link em todas" inicio={70} tom="amarelo" /></div>
      <div style={{position: 'absolute', right: 40, top: 1440}}>
        <Etiqueta inicio={30} texto={<span>📤 <span style={{fontVariantNumeric: 'tabular-nums'}}>{ofertas}</span> ofertas hoje</span>} />
      </div>
    </AbsoluteFill>
  );
};

export const DURACAO_BOT_UM_DIA = UM_DIA.cena + UM_DIA.final;

export const BotUmDia: React.FC = () => (
  <AbsoluteFill style={{background: C.verde}}>
    <Sequence durationInFrames={UM_DIA.cena}><UmDia /></Sequence>
    <Sequence from={UM_DIA.cena} durationInFrames={UM_DIA.final}><Final frase={'Você vive o seu dia.\n*O bot trabalha.*'} linha={CTA.bot} /></Sequence>
    <Sequence from={UM_DIA.cena - 9} durationInFrames={18}><Cortina /></Sequence>
  </AbsoluteFill>
);

// --- BotCampanha -----------------------------------------------------------------------------------

const DATAS = ['9.9', '10.10', '11.11', 'Black Friday', '12.12'];

const Datas: React.FC = () => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  return (
    <AbsoluteFill style={{fontFamily: FONTE, color: C.verde}}>
      <Fundo tom="amarelo" />
      <div style={{position: 'absolute', left: 90, right: 90, top: 330}}>
        <Chapeu texto="Modo campanha" cor={C.verde} inicio={-14} />
        <Titulo texto={'As datas da Shopee\nvêm *marcadas.*'} inicio={-12} tamanho={96} cor={C.verde} destaque={C.branco} style={{marginTop: 26}} />
      </div>
      <div style={{position: 'absolute', left: 90, right: 90, top: 700, display: 'flex', flexWrap: 'wrap', gap: 22}}>
        {DATAS.map((d, i) => {
          const t = mola(f, 26 + i * 9, fps, 12);
          const marcado = f >= 70 + i * 9;
          return (
            <div key={d} style={{display: 'flex', alignItems: 'center', gap: 18, background: C.verde, color: C.creme, borderRadius: 30, padding: '24px 34px',
              fontSize: 56, fontWeight: 800, letterSpacing: '-.02em', opacity: Math.min(1, t * 1.3),
              transform: `translateY(${(1 - t) * 60}px) rotate(${(1 - t) * (i % 2 ? 6 : -6)}deg)`}}>
              <span style={{width: 46, height: 46, borderRadius: 14, background: marcado ? C.amarelo : 'rgba(246,243,234,.18)', color: C.verde, display: 'grid',
                placeItems: 'center', fontSize: 32, transform: `scale(${marcado ? mola(f, 70 + i * 9, fps, 10) : 1})`}}>{marcado ? '✓' : ''}</span>
              {d}
            </div>
          );
        })}
      </div>
      <Apoio texto="E você ainda soma as suas datas, até 20." inicio={120} cor={C.verde} tamanho={40} style={{position: 'absolute', left: 90, right: 90, top: 1240, fontWeight: 800}} />
      <Apoio texto="O painel avisa 7 dias antes de cada uma." inicio={134} cor="rgba(31,58,46,.8)" tamanho={36} style={{position: 'absolute', left: 90, right: 90, top: 1310}} />
    </AbsoluteFill>
  );
};

const AJUSTES = [
  {nome: 'Intervalo', normal: 'a cada 30 min', campanha: 'a cada 15 min'},
  {nome: 'Ofertas no dia', normal: '28', campanha: '56'},
  {nome: 'Abertura', normal: '—', campanha: '📣 É hoje: 11.11!'},
  {nome: 'Cupom', normal: '—', campanha: 'ONZEONZE'},
];

/** Um valor que troca de baixo pra cima (como placa de aeroporto) no frame `quando`. */
const Troca: React.FC<{de: string; para: string; quando: number}> = ({de, para, quando}) => {
  const f = useCurrentFrame();
  const t = vai(f, quando, quando + 12);
  return (
    <span style={{display: 'inline-grid', overflow: 'hidden', verticalAlign: 'bottom'}}>
      <span style={{gridArea: '1/1', transform: `translateY(${-t * 100}%)`, opacity: 1 - t, color: C.cinza}}>{de}</span>
      <span style={{gridArea: '1/1', transform: `translateY(${(1 - t) * 100}%)`, opacity: t, color: C.verde}}>{para}</span>
    </span>
  );
};

const NO_DIA: Mensagem[] = OFERTAS.slice(0, 4).map((o, i) => ({...o, tipo: 'oferta', f: 150 + i * 30, hora: horario(9, i * 15), campanha: '📣 É hoje: 11.11!', cupom: 'ONZEONZE'}));

const Campanha: React.FC = () => {
  const f = useCurrentFrame();
  const sobe = vai(f, 120, 150);
  return (
    <AbsoluteFill style={{fontFamily: FONTE, color: C.creme}}>
      <Fundo tom="escuro" />
      <div style={{position: 'absolute', left: 90, right: 90, top: 330, opacity: 1 - sobe, transform: `translateY(${-sobe * 60}px)`}}>
        <Chapeu texto="No dia, sozinho" cor={C.amarelo} />
        <Titulo texto={'O bot troca\no *ritmo* e o *texto.*'} inicio={4} tamanho={92} cor={C.creme} style={{marginTop: 26}} />
      </div>
      <div style={{position: 'absolute', left: 80, right: 80, top: 700 - sobe * 380, background: C.branco, color: C.tinta, borderRadius: 40, padding: '30px 38px',
        boxShadow: '0 30px 60px rgba(0,0,0,.3)', opacity: vai(f, 16, 30), transform: `scale(${1 - sobe * 0.12})`, transformOrigin: 'top center'}}>
        <div style={{display: 'flex', justifyContent: 'space-between', fontSize: 24, fontWeight: 800, letterSpacing: '.1em', textTransform: 'uppercase', color: ESCURO_AMARELO}}>
          <span>Campanha 11.11</span><span>{f >= 40 ? '● no ar' : 'amanhã'}</span>
        </div>
        {AJUSTES.map((a, i) => (
          <div key={a.nome} style={{display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 20, padding: '20px 0', borderTop: i ? `2px solid ${C.borda}` : 'none',
            marginTop: i ? 0 : 14, fontSize: 36}}>
            <span style={{color: C.cinza, fontWeight: 500}}>{a.nome}</span>
            <span style={{fontWeight: 800}}><Troca de={a.normal} para={a.campanha} quando={44 + i * 12} /></span>
          </div>
        ))}
      </div>
      <div style={{position: 'absolute', left: 0, right: 0, top: 770, display: 'flex', justifyContent: 'center', opacity: sobe, transform: `translateY(${(1 - sobe) * 300}px)`}}>
        <Celular escala={0.74} hora="9:00">
          <ConversaZap nome={GRUPO.nome} membros={GRUPO.membros} mensagens={NO_DIA} />
        </Celular>
      </div>
      <div style={{position: 'absolute', right: 36, top: 1200}}><Etiqueta texto="Amanhã, volta ao normal ↺" inicio={230} tom="amarelo" /></div>
    </AbsoluteFill>
  );
};

const CP = {datas: s(5.2), campanha: s(9.5), final: s(3.8)};
export const DURACAO_BOT_CAMPANHA = CP.datas + CP.campanha + CP.final;

export const BotCampanha: React.FC = () => (
  <AbsoluteFill style={{background: C.verde}}>
    <Sequence durationInFrames={CP.datas}><Cena duracao={CP.datas} entrada={false} saida={false}><Datas /></Cena></Sequence>
    <Sequence from={CP.datas} durationInFrames={CP.campanha}><Campanha /></Sequence>
    <Sequence from={CP.datas - 9} durationInFrames={18}><Cortina cor={C.verde} /></Sequence>
    <Sequence from={CP.datas + CP.campanha} durationInFrames={CP.final}><Final frase={'Configure uma vez,\n*vale todo ano.*'} linha={CTA.bot} /></Sequence>
    <Sequence from={CP.datas + CP.campanha - 9} durationInFrames={18}><Cortina /></Sequence>
  </AbsoluteFill>
);
