/** Tema 3: Resultados e metas (inclusos em todos os planos). Duas versões:
 * - ResultadosQuantoFalta: quanto falta pra faixa do bônus da Shopee, na tela de Metas e na Lia.
 * - ResultadosQualGrupo: qual Sub ID vende mais, em que horário e de onde veio cada venda.
 * Números fictícios da conta "Achadinhos da Bia". As regras são as do painel: a meta conta o
 * faturamento (painel/telas.py), as faixas são 100%, 125% e 150%, e a origem das vendas vem de
 * painel/origens.py. */
import React from 'react';
import {AbsoluteFill, Easing, Sequence, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {C, FONTE} from '../appfiliado/marca';
import {Apoio, Celular, Cena, Chapeu, Conta, Cortina, Etiqueta, Final, Fundo, Titulo, mola, s, vai} from './comum';
import {CTA} from './textos';

const ESCURO_AMARELO = '#8A6A00';
const brl = (v: number) => 'R$ ' + v.toLocaleString('pt-BR', {minimumFractionDigits: 2, maximumFractionDigits: 2});
const brl0 = (v: number) => 'R$ ' + Math.round(v).toLocaleString('pt-BR');

const Cartao: React.FC<{children: React.ReactNode; style?: React.CSSProperties}> = ({children, style}) => (
  <div style={{background: C.branco, color: C.tinta, border: `3px solid ${C.borda}`, borderRadius: 36, padding: 40, boxShadow: '0 24px 50px rgba(23,48,31,.10)', ...style}}>
    {children}
  </div>
);

// --- Resultados-QuantoFalta ------------------------------------------------------------------------

const GanchoMeta: React.FC = () => {
  const f = useCurrentFrame();
  // "R$ ?.???" que procura o número (dígitos girando, sem acaso: saem do frame)
  const digito = (k: number) => String((Math.floor(f / 3) * (k * 3 + 7) + k * 5) % 10);
  const procura = f < 30 ? '?.???' : `${digito(1)}.${digito(2)}${digito(3)}${digito(4)}`;
  const t = vai(f, 26, 40);
  return (
    <AbsoluteFill style={{fontFamily: FONTE, color: C.creme}}>
      <Fundo tom="escuro" />
      <div style={{position: 'absolute', left: 90, right: 90, top: 380}}>
        <Chapeu texto="Metas da Shopee" cor={C.amarelo} />
        <Titulo texto={'Quanto falta\npro seu *bônus*\neste mês?'} inicio={4} tamanho={110} cor={C.creme} style={{marginTop: 30}} />
      </div>
      <div style={{position: 'absolute', left: 90, right: 90, top: 1060, opacity: t, transform: `translateY(${(1 - t) * 30}px)`}}>
        <div style={{display: 'inline-flex', alignItems: 'baseline', gap: 18, border: '4px dashed rgba(246,243,234,.35)', borderRadius: 34, padding: '26px 40px'}}>
          <span style={{fontSize: 60, fontWeight: 800, color: C.suave}}>faltam</span>
          <span style={{fontSize: 110, fontWeight: 800, letterSpacing: '-.04em', color: C.amarelo, fontVariantNumeric: 'tabular-nums'}}>R$ {procura}</span>
        </div>
        <Apoio texto="Sem planilha e sem conta de cabeça." inicio={44} cor={C.suave} tamanho={42} style={{marginTop: 40}} />
      </div>
    </AbsoluteFill>
  );
};

const FAIXAS = [
  {nome: '100%', meta: 52000, bonus: 300},
  {nome: '125%', meta: 65000, bonus: 500},
  {nome: '150%', meta: 78000, bonus: 800},
];
const ATE_ONTEM = 41380;
const DIA_28 = 53240;

const TelaMetas: React.FC = () => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const primeiro = vai(f, 24, 88, 0, ATE_ONTEM, Easing.out(Easing.cubic));
  const depois = vai(f, 168, 218, ATE_ONTEM, DIA_28, Easing.inOut(Easing.cubic));
  const faturamento = f < 168 ? primeiro : depois;
  const largura = (faturamento / 78000) * 100;
  const batida = f >= 214;
  const festa = mola(f, 214, fps, 10);
  const dia = f < 158 ? 'Dia 20 · prévia' : 'Dia 28 · prévia';
  const trocaDia = mola(f, 158, fps, 14);
  return (
    <AbsoluteFill style={{fontFamily: FONTE, color: C.tinta}}>
      <Fundo tom="creme" />
      <div style={{position: 'absolute', left: 90, right: 90, top: 330}}>
        <Chapeu texto="Resultados e metas" />
        <Titulo texto={'Agora você *sabe.*'} inicio={4} tamanho={100} destaque={ESCURO_AMARELO} style={{marginTop: 26}} />
      </div>
      <Cartao style={{position: 'absolute', left: 70, right: 70, top: 600, opacity: vai(f, 10, 24), transform: `translateY(${(1 - vai(f, 10, 24)) * 50}px)`}}>
        <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
          <div style={{fontSize: 40, fontWeight: 800}}>Meta de Novembro</div>
          <div style={{fontSize: 26, fontWeight: 800, background: '#FBF1CF', color: '#7A5B00', borderRadius: 999, padding: '10px 20px',
            transform: f >= 158 ? `scale(${0.85 + 0.15 * trocaDia})` : undefined}}>{dia}</div>
        </div>
        <div style={{fontSize: 28, color: C.cinza, marginTop: 26}}>Faturamento até ontem</div>
        <div style={{fontSize: 92, fontWeight: 800, letterSpacing: '-.04em', fontVariantNumeric: 'tabular-nums', color: batida ? C.ok : C.tinta}}>{brl(faturamento)}</div>
        {/* barra com as três faixas */}
        <div style={{position: 'relative', marginTop: 34, height: 116}}>
          <div style={{position: 'absolute', left: 0, right: 0, top: 0, height: 42, borderRadius: 999, background: '#EDE8D9', overflow: 'hidden'}}>
            <div style={{height: '100%', width: `${largura}%`, borderRadius: 999, background: batida ? C.ok : C.verde}} />
          </div>
          {FAIXAS.map((x) => {
            const pos = (x.meta / 78000) * 100;
            const ok = faturamento >= x.meta;
            return (
              <div key={x.nome} style={{position: 'absolute', left: `${pos}%`, top: -10, transform: 'translateX(-100%)', textAlign: 'right'}}>
                <div style={{width: 6, height: 62, background: ok ? C.ok : C.tinta, marginLeft: 'auto', borderRadius: 3, opacity: 0.8}} />
                <div style={{fontSize: 26, fontWeight: 800, marginTop: 8, color: ok ? C.ok : C.tinta, whiteSpace: 'nowrap'}}>{x.nome}</div>
              </div>
            );
          })}
        </div>
        <div style={{display: 'grid', gap: 16, marginTop: 20}}>
          {FAIXAS.map((x, i) => {
            const ok = faturamento >= x.meta;
            const aparece = vai(f, 92 + i * 8, 106 + i * 8);
            const pulo = ok && i === 0 ? 1 + 0.05 * Math.sin(Math.min(1, festa) * Math.PI) : 1;
            return (
              <div key={x.nome} style={{display: 'flex', alignItems: 'center', gap: 20, fontSize: 32, opacity: aparece, transform: `translateX(${(1 - aparece) * -30}px) scale(${pulo})`,
                transformOrigin: 'left center', background: ok ? '#E3F1E7' : '#F6F3EA', borderRadius: 22, padding: '18px 22px'}}>
                <span style={{width: 44, height: 44, borderRadius: '50%', display: 'grid', placeItems: 'center', flex: 'none', fontSize: 26, fontWeight: 800,
                  background: ok ? C.ok : C.branco, color: C.branco, border: ok ? 'none' : `3px solid ${C.borda}`}}>{ok ? '✓' : ''}</span>
                <span style={{fontWeight: 800}}>{x.nome}</span>
                <span style={{color: C.cinza}}>bônus {brl0(x.bonus)}</span>
                <span style={{marginLeft: 'auto', fontWeight: 800, color: ok ? C.ok : C.tinta, fontVariantNumeric: 'tabular-nums'}}>
                  {ok ? 'batida' : `faltam ${brl0(x.meta - faturamento)}`}
                </span>
              </div>
            );
          })}
        </div>
      </Cartao>
      <div style={{position: 'absolute', left: 70, top: 1400}}>
        {f < 158 ? (
          <Etiqueta inicio={120} tom="escuro" texto="📅 R$ 1.062 por dia nos 10 dias que faltam" />
        ) : (
          <Etiqueta inicio={222} tom="amarelo" texto="🎉 Faixa 100% batida: bônus de R$ 300" />
        )}
      </div>
    </AbsoluteFill>
  );
};

/** Conversa com a Lia: a pessoa manda "metas" e a Lia responde com os números (mesmo texto de
 * atendimento/comandos.py, resumido ao mês atual). */
const LINHAS_LIA = [
  {b: true, t: '🎯 Metas da Shopee'},
  {b: true, t: '🟡 Novembro: prévia'},
  {b: false, t: 'Faturamento até ontem (estimado): R$ 41.380,00'},
  {b: false, t: '⬜ 100% (R$ 52.000,00, bônus de R$ 300,00): faltam R$ 10.620,00'},
  {b: false, t: 'Para a próxima faixa: R$ 1.062,00 por dia nos 10 dias que faltam.'},
];

const ConversaLia: React.FC = () => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const minha = mola(f, 18, fps, 15);
  const digitando = f >= 32 && f < 52;
  const resposta = mola(f, 52, fps, 15);
  return (
    <div style={{position: 'absolute', inset: 0, background: C.zap, display: 'flex', flexDirection: 'column', fontFamily: FONTE}}>
      <div style={{height: 150, background: C.verde, color: C.creme, display: 'flex', alignItems: 'center', gap: 18, padding: '56px 26px 0', flex: 'none'}}>
        <span style={{fontSize: 34, opacity: 0.8}}>‹</span>
        <div style={{width: 64, height: 64, borderRadius: '50%', background: C.amarelo, color: C.verde, display: 'grid', placeItems: 'center', fontSize: 30, fontWeight: 800}}>L</div>
        <div>
          <div style={{fontSize: 28, fontWeight: 800}}>Lia · Appfiliado</div>
          <div style={{fontSize: 20, color: C.suave}}>{digitando ? 'digitando…' : 'online'}</div>
        </div>
      </div>
      <div style={{flex: 1, padding: '24px 22px', display: 'flex', flexDirection: 'column', gap: 18, color: C.tinta}}>
        {f >= 18 && (
          <div style={{alignSelf: 'flex-end', background: '#D9FDD3', borderRadius: '24px 8px 24px 24px', padding: '12px 20px', fontSize: 30, fontWeight: 500,
            opacity: Math.min(1, minha * 1.5), transform: `scale(${0.9 + 0.1 * minha})`, transformOrigin: 'right top'}}>
            metas <span style={{fontSize: 18, color: '#8C978F'}}>20:14 <span style={{color: '#4FA3E0'}}>✓✓</span></span>
          </div>
        )}
        {digitando && (
          <div style={{alignSelf: 'flex-start', background: C.balao, borderRadius: '8px 24px 24px 24px', padding: '16px 24px', fontSize: 30, letterSpacing: 4, color: C.cinza}}>
            {'•••'.slice(0, 1 + (Math.floor(f / 5) % 3))}
          </div>
        )}
        {f >= 52 && (
          <div style={{alignSelf: 'flex-start', background: C.balao, borderRadius: '8px 24px 24px 24px', padding: '18px 22px', width: 500, fontSize: 27, lineHeight: 1.36,
            boxShadow: '0 4px 10px rgba(0,0,0,.07)', opacity: Math.min(1, resposta * 1.5), transform: `scale(${0.92 + 0.08 * resposta})`, transformOrigin: 'left top'}}>
            {LINHAS_LIA.map((l, i) => (
              <div key={i} style={{fontWeight: l.b ? 800 : 500, marginTop: i === 2 ? 8 : i > 2 ? 6 : 0, opacity: vai(f, 54 + i * 4, 62 + i * 4)}}>{l.t}</div>
            ))}
            <div style={{textAlign: 'right', fontSize: 17, color: '#8C978F', marginTop: 4}}>20:14</div>
          </div>
        )}
      </div>
    </div>
  );
};

const PergunteALia: React.FC = () => (
  <AbsoluteFill style={{fontFamily: FONTE, color: C.creme}}>
    <Fundo tom="escuro" />
    <div style={{position: 'absolute', left: 90, right: 90, top: 330}}>
      <Chapeu texto="Lia no WhatsApp" cor={C.amarelo} />
      <Titulo texto={'Ou mande *metas*\npra Lia.'} inicio={2} tamanho={92} cor={C.creme} style={{marginTop: 24}} />
    </div>
    <div style={{position: 'absolute', left: 0, right: 0, top: 620, display: 'flex', justifyContent: 'center'}}>
      <Celular escala={0.95} hora="20:14">
        <ConversaLia />
      </Celular>
    </div>
  </AbsoluteFill>
);

const QF = {gancho: s(3), metas: s(8.5), lia: s(5), final: s(3.5)};
export const DURACAO_RESULTADOS_FALTA = QF.gancho + QF.metas + QF.lia + QF.final;

export const ResultadosQuantoFalta: React.FC = () => {
  const lia = QF.gancho + QF.metas;
  const fim = lia + QF.lia;
  return (
    <AbsoluteFill style={{background: C.verde}}>
      <Sequence durationInFrames={QF.gancho}><Cena duracao={QF.gancho} entrada={false} saida={false}><GanchoMeta /></Cena></Sequence>
      <Sequence from={QF.gancho} durationInFrames={QF.metas}><Cena duracao={QF.metas} entrada={false} saida={false}><TelaMetas /></Cena></Sequence>
      <Sequence from={lia} durationInFrames={QF.lia}><Cena duracao={QF.lia} entrada={false} saida={false}><PergunteALia /></Cena></Sequence>
      <Sequence from={fim} durationInFrames={QF.final}><Cena duracao={QF.final} entrada={false} saida={false}><Final frase={'Saiba quanto falta\n*pro bônus.*'} linha={CTA.incluso} /></Cena></Sequence>
      <Sequence from={QF.gancho - 9} durationInFrames={18}><Cortina /></Sequence>
      <Sequence from={lia - 9} durationInFrames={18}><Cortina cor={C.verde} /></Sequence>
      <Sequence from={fim - 9} durationInFrames={18}><Cortina /></Sequence>
    </AbsoluteFill>
  );
};

// --- Resultados-QualGrupoVende -------------------------------------------------------------------

/** Comissão por Sub ID ao longo do mês: [valor no dia 5, 12, 20, 30]. As posições trocam no caminho. */
const SUB_IDS = [
  {nome: 'grupovip', rotulo: 'Grupo VIP', v: [180, 520, 910, 1284.6]},
  {nome: 'grupo2', rotulo: 'Achadinhos #2', v: [260, 610, 820, 912.3]},
  {nome: 'site', rotulo: 'Meu site', v: [90, 240, 410, 538.9]},
  {nome: 'casa', rotulo: 'Casa e cozinha', v: [140, 300, 380, 486.2]},
  {nome: 'beleza', rotulo: 'Beleza', v: [110, 190, 250, 301.7]},
];
const DIAS_DA_CORRIDA = [5, 12, 20, 30];

const Corrida: React.FC = () => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const marcos = [40, 70, 100, 130];
  const valor = (v: number[]) => interpolate(f, marcos, v, {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.inOut(Easing.quad)});
  const valores = SUB_IDS.map((x) => valor(x.v));
  const maior = Math.max(...valores, 1);
  const dia = Math.round(interpolate(f, marcos, DIAS_DA_CORRIDA, {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}));
  // posição contínua: cada barra desce uma "casa" por barra maior que ela (suave quando elas se cruzam)
  const posicao = valores.map((v, i) => valores.reduce((p, w, j) => (j === i ? p : p + 1 / (1 + Math.exp(-(w - v) / 18))), 0));
  const lider = valores.indexOf(maior);
  const ALT = 118;
  const entrada = vai(f, 12, 30);
  return (
    <AbsoluteFill style={{fontFamily: FONTE, color: C.tinta}}>
      <Fundo tom="creme" />
      <div style={{position: 'absolute', left: 90, right: 90, top: 330}}>
        <Chapeu texto="Resultados e metas" />
        <Titulo texto={'Qual dos seus\ngrupos *vende mais?*'} inicio={4} tamanho={86} destaque={ESCURO_AMARELO} style={{marginTop: 26}} />
      </div>
      <Cartao style={{position: 'absolute', left: 70, right: 70, top: 650, opacity: entrada, transform: `translateY(${(1 - entrada) * 50}px)`}}>
        <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'baseline'}}>
          <div style={{fontSize: 36, fontWeight: 800}}>Comissão por Sub ID</div>
          <div style={{fontSize: 28, color: C.cinza, fontVariantNumeric: 'tabular-nums'}}>Novembro · dia {dia}</div>
        </div>
        <div style={{position: 'relative', height: ALT * SUB_IDS.length, marginTop: 24}}>
          {SUB_IDS.map((x, i) => {
            const v = valores[i];
            const frente = i === lider && f >= 128;
            return (
              <div key={x.nome} style={{position: 'absolute', left: 0, right: 0, top: posicao[i] * ALT, height: ALT - 18, display: 'flex', alignItems: 'center', gap: 20}}>
                <div style={{width: 230, flex: 'none'}}>
                  <div style={{fontSize: 30, fontWeight: 800, whiteSpace: 'nowrap'}}>{x.rotulo}</div>
                  <div style={{fontSize: 22, color: C.cinza}}>{x.nome}</div>
                </div>
                <div style={{flex: 1, position: 'relative', height: 58}}>
                  <div style={{position: 'absolute', left: 0, top: 0, bottom: 0, width: `${(v / maior) * 74}%`, borderRadius: 16,
                    background: frente ? C.amarelo : i === 2 ? '#E8A317' : C.verde}} />
                  <div style={{position: 'absolute', left: `calc(${(v / maior) * 74}% + 14px)`, top: '50%', transform: 'translateY(-50%)', fontSize: 28, fontWeight: 800,
                    whiteSpace: 'nowrap', fontVariantNumeric: 'tabular-nums'}}>{brl(v)}</div>
                </div>
              </div>
            );
          })}
        </div>
      </Cartao>
      <div style={{position: 'absolute', left: 70, top: 1430}}>
        <Etiqueta inicio={138} tom="amarelo" texto={<span>🏆 Grupo VIP na frente</span>} />
      </div>
      <div style={{position: 'absolute', left: 70, top: 1530, opacity: mola(f, 150, fps) > 0.01 ? 1 : 0}}>
        <Etiqueta inicio={150} texto="Cada grupo com o seu Sub ID" />
      </div>
    </AbsoluteFill>
  );
};

// Mapa de calor (pedidos por dia da semana x hora): noite forte, almoço médio, madrugada fraca.
const DIAS = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom'];
const intensidade = (d: number, h: number) => {
  const noite = Math.exp(-((h - 20.6) ** 2) / 5);
  const almoco = 0.45 * Math.exp(-((h - 12.5) ** 2) / 2.2);
  const manha = 0.2 * Math.exp(-((h - 9) ** 2) / 3);
  const fds = d >= 5 ? 0.75 + 0.25 * Math.exp(-((h - 15) ** 2) / 10) : 1;
  const segunda = d === 0 ? 1.18 : 1;
  return Math.min(1, (noite + almoco + manha) * fds * segunda * (0.85 + 0.15 * ((d * 7 + h * 3) % 5) / 4));
};
const NIVEIS = ['#EFEADB', '#CFE0D4', '#8FB8A0', '#4C7D63', C.verde];
const FORTES = new Set(['0-20', '0-21', '4-21']);

const Horarios: React.FC = () => {
  const f = useCurrentFrame();
  const entrada = vai(f, 8, 24);
  const CEL = 29;
  return (
    <AbsoluteFill style={{fontFamily: FONTE, color: C.creme}}>
      <Fundo tom="escuro" />
      <div style={{position: 'absolute', left: 90, right: 90, top: 330}}>
        <Titulo texto={'E em que\n*horário?*'} inicio={2} tamanho={104} cor={C.creme} />
      </div>
      <Cartao style={{position: 'absolute', left: 70, right: 70, top: 630, padding: '34px 34px 30px', opacity: entrada, transform: `translateY(${(1 - entrada) * 50}px)`}}>
        <div style={{fontSize: 34, fontWeight: 800}}>Quando suas vendas acontecem</div>
        <div style={{fontSize: 24, color: C.cinza, marginTop: 4}}>pedidos por dia da semana e hora</div>
        <div style={{marginTop: 22, display: 'grid', gap: 5}}>
          {DIAS.map((d, i) => (
            <div key={d} style={{display: 'flex', alignItems: 'center', gap: 4}}>
              <div style={{width: 62, fontSize: 24, fontWeight: 800, color: C.cinza}}>{d}</div>
              {Array.from({length: 24}, (_, h) => {
                const nivel = Math.min(4, Math.floor(intensidade(i, h) * 5));
                const aparece = vai(f, 16 + h * 1.6 + i * 0.6, 26 + h * 1.6 + i * 0.6);
                const forte = FORTES.has(`${i}-${h}`) && f >= 70;
                return (
                  <div key={h} style={{width: CEL, height: CEL + 14, borderRadius: 7, background: NIVEIS[nivel], opacity: aparece,
                    boxShadow: forte ? `0 0 0 4px ${C.amarelo}` : 'none', transform: forte ? `scale(${1 + 0.12 * vai(f, 70, 80) - 0.12 * vai(f, 80, 92)})` : undefined}} />
                );
              })}
            </div>
          ))}
          <div style={{display: 'flex', gap: 4, marginLeft: 66, fontSize: 19, color: C.cinza, fontWeight: 800}}>
            {Array.from({length: 24}, (_, h) => <div key={h} style={{width: CEL, textAlign: 'left'}}>{h % 6 === 0 ? `${h}h` : ''}</div>)}
          </div>
        </div>
        <div style={{fontSize: 26, fontWeight: 800, color: '#7A5B00', marginTop: 24, opacity: vai(f, 80, 94)}}>Horários mais fortes</div>
        <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginTop: 12}}>
          {[['Segunda, 20h–22h', '9,8% da semana em 2 horas'], ['Todo dia, 21h–22h', 'a hora que mais vende (11,4%)']].map(([t, x], k) => {
            const a = vai(f, 88 + k * 8, 102 + k * 8);
            return (
              <div key={t} style={{background: '#F6F3EA', borderRadius: 20, padding: '16px 18px', opacity: a, transform: `translateY(${(1 - a) * 20}px)`}}>
                <div style={{fontSize: 27, fontWeight: 800}}>{t}</div>
                <div style={{fontSize: 21, color: C.cinza, marginTop: 2}}>{x}</div>
              </div>
            );
          })}
        </div>
      </Cartao>
      <div style={{position: 'absolute', left: 70, right: 70, top: 1380}}>
        <Etiqueta inicio={122} tom="amarelo" tamanho={27} texto="💡 Seu bot para às 20h, antes do horário mais forte" />
      </div>
    </AbsoluteFill>
  );
};

const ORIGENS = [
  {nome: 'Bot de WhatsApp', cor: C.verde, valor: 1842.1},
  {nome: 'Meu site', cor: '#E8A317', valor: 682.4},
  {nome: 'Conversor de links', cor: '#5B8C74', valor: 512.3},
  {nome: 'Fora do Appfiliado', cor: '#CFC6B8', valor: 375.2},
];
const TOTAL_ORIGENS = ORIGENS.reduce((a, o) => a + o.valor, 0);

const Origens: React.FC = () => {
  const f = useCurrentFrame();
  const entrada = vai(f, 8, 24);
  return (
    <AbsoluteFill style={{fontFamily: FONTE, color: C.tinta}}>
      <Fundo tom="creme" />
      <div style={{position: 'absolute', left: 90, right: 90, top: 330}}>
        <Titulo texto={'E de onde veio\n*cada venda.*'} inicio={2} tamanho={100} destaque={ESCURO_AMARELO} />
      </div>
      <Cartao style={{position: 'absolute', left: 70, right: 70, top: 650, opacity: entrada, transform: `translateY(${(1 - entrada) * 50}px)`}}>
        <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'baseline'}}>
          <div style={{fontSize: 36, fontWeight: 800}}>De onde vieram as vendas</div>
          <div style={{fontSize: 26, color: C.cinza}}>comissão do mês</div>
        </div>
        <div style={{display: 'flex', height: 64, borderRadius: 20, overflow: 'hidden', marginTop: 26, background: '#EFEADB'}}>
          {ORIGENS.map((o, i) => {
            const cresce = vai(f, 22 + i * 10, 44 + i * 10);
            return <div key={o.nome} style={{width: `${(o.valor / TOTAL_ORIGENS) * 100 * cresce}%`, background: o.cor}} />;
          })}
        </div>
        <div style={{display: 'grid', gap: 6, marginTop: 24}}>
          {ORIGENS.map((o, i) => {
            const a = vai(f, 26 + i * 10, 40 + i * 10);
            const pct = Math.round((o.valor / TOTAL_ORIGENS) * 100);
            return (
              <div key={o.nome} style={{display: 'flex', alignItems: 'center', gap: 20, fontSize: 34, padding: '16px 0', borderTop: i ? `2px solid ${C.borda}` : 'none',
                opacity: a, transform: `translateX(${(1 - a) * -30}px)`}}>
                <span style={{width: 30, height: 30, borderRadius: 9, background: o.cor, flex: 'none'}} />
                <span style={{fontWeight: 800, flex: 1}}>{o.nome}</span>
                <span style={{fontWeight: 800, fontVariantNumeric: 'tabular-nums'}}><Conta ate={o.valor} inicio={26 + i * 10} duracao={30} reais /></span>
                <span style={{width: 86, textAlign: 'right', color: C.cinza, fontVariantNumeric: 'tabular-nums'}}>{pct}%</span>
              </div>
            );
          })}
        </div>
      </Cartao>
      <div style={{position: 'absolute', left: 70, top: 1330}}>
        <Etiqueta inicio={84} tom="escuro" texto="Filtre a aba Resultados por origem" />
      </div>
    </AbsoluteFill>
  );
};

const QG = {corrida: s(6.2), horarios: s(6), origens: s(4.6), final: s(3.5)};
export const DURACAO_RESULTADOS_GRUPO = QG.corrida + QG.horarios + QG.origens + QG.final;

export const ResultadosQualGrupo: React.FC = () => {
  const origens = QG.corrida + QG.horarios;
  const fim = origens + QG.origens;
  return (
    <AbsoluteFill style={{background: C.verde}}>
      <Sequence durationInFrames={QG.corrida}><Cena duracao={QG.corrida} entrada={false} saida={false}><Corrida /></Cena></Sequence>
      <Sequence from={QG.corrida} durationInFrames={QG.horarios}><Cena duracao={QG.horarios} entrada={false} saida={false}><Horarios /></Cena></Sequence>
      <Sequence from={origens} durationInFrames={QG.origens}><Cena duracao={QG.origens} entrada={false} saida={false}><Origens /></Cena></Sequence>
      <Sequence from={fim} durationInFrames={QG.final}><Cena duracao={QG.final} entrada={false} saida={false}><Final frase={'Saiba *o que vende*\ne quando vende.'} linha={CTA.incluso} /></Cena></Sequence>
      <Sequence from={QG.corrida - 9} durationInFrames={18}><Cortina /></Sequence>
      <Sequence from={origens - 9} durationInFrames={18}><Cortina cor={C.verde} /></Sequence>
      <Sequence from={fim - 9} durationInFrames={18}><Cortina /></Sequence>
    </AbsoluteFill>
  );
};
