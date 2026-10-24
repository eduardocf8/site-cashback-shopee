/** Uma demonstração por ferramenta, na área lógica de 900 x 1000 (ver ui.tsx). O frame é o da cena
 * (cada uma começa no 0). Os dados são os da conta fictícia "Achadinhos da Bia", os mesmos dos
 * prints do site. */
import React from 'react';
import {interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {C} from './marca';
import {Alvo, AreaDeAlvos, Aviso, Botao, Card, Chip, Contador, Cursor, Digitando, Foto, Interruptor, entra, mola, produto} from './ui';


// --- Bot de WhatsApp --------------------------------------------------------------------------------

const OFERTAS = [
  {foto: 'fone', nome: 'Fone Bluetooth TWS com cancelamento de ruído', de: 'R$ 199,90', por: 'R$ 79,90', link: 's.shopee.com.br/8Kz1aQ'},
  {foto: 'airfryer', nome: 'Air Fryer 4L com timer e painel touch', de: 'R$ 459,90', por: 'R$ 329,90', link: 's.shopee.com.br/4Lp9Xw'},
  {foto: 'garrafa', nome: 'Garrafa térmica 1L inox parede dupla', de: 'R$ 89,90', por: 'R$ 49,90', link: 's.shopee.com.br/2Vb7Tr'},
];

export const CenaBot: React.FC = () => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const ligado = interpolate(f, [44, 52], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const chegadas = [80, 150, 220];
  return (
    <AreaDeAlvos>
      <Card style={{position: 'absolute', left: 0, right: 0, top: 0, height: 170, display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 40px'}}>
        <div>
          <div style={{fontSize: 22, fontWeight: 800, letterSpacing: '.12em', color: '#8A6A00', textTransform: 'uppercase'}}>Automação</div>
          <div style={{fontSize: 40, fontWeight: 800, marginTop: 6}}>{ligado > 0.5 ? 'Ofertas ligadas' : 'Ofertas desligadas'}</div>
          <div style={{fontSize: 24, color: C.cinza, marginTop: 4}}>Uma oferta a cada 5 min · 8h às 22h</div>
        </div>
        <div style={{transform: 'scale(1.4)', transformOrigin: 'right center'}}><Alvo nome="ligar"><Interruptor ligado={ligado} /></Alvo></div>
      </Card>
      <div style={{position: 'absolute', left: 0, right: 0, top: 200, bottom: 0, borderRadius: 32, overflow: 'hidden', background: C.zap, border: `2px solid ${C.borda}`}}>
        <div style={{height: 104, background: '#1F3A2E', color: C.creme, display: 'flex', alignItems: 'center', gap: 20, padding: '0 30px', position: 'relative', zIndex: 2}}>
          <div style={{width: 64, height: 64, borderRadius: '50%', background: C.amarelo, display: 'grid', placeItems: 'center', fontSize: 34}}>🛍️</div>
          <div>
            <div style={{fontSize: 30, fontWeight: 800}}>Achadinhos da Bia</div>
            <div style={{fontSize: 22, color: C.suave}}>1.248 participantes</div>
          </div>
        </div>
        <div style={{position: 'absolute', left: 26, right: 26, top: 130, }}>
          {OFERTAS.map((o, i) => {
            const s = mola(f, chegadas[i], fps);
            if (f < chegadas[i]) return null;
            return (
              <div key={o.nome} style={{background: C.balao, borderRadius: '8px 26px 26px 26px', padding: 18, marginBottom: 22, width: 640, display: 'flex', gap: 18,
                boxShadow: '0 6px 14px rgba(0,0,0,.08)', opacity: s, transform: `translateY(${(1 - s) * 80}px) scale(${0.9 + 0.1 * s})`, transformOrigin: 'left top'}}>
                <Foto nome={o.foto} tamanho={150} />
                <div style={{fontSize: 24, lineHeight: 1.35}}>
                  <div style={{fontWeight: 800}}>🔥 {o.nome}</div>
                  <div style={{color: C.cinza, textDecoration: 'line-through', marginTop: 6}}>De {o.de}</div>
                  <div style={{fontWeight: 800, fontSize: 30, color: C.ok}}>Por {o.por}</div>
                  <div style={{color: '#2F6FD8', marginTop: 4}}>👉 {o.link}</div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
      <Cursor pontos={[[10, 520, 600], [40, 'ligar'], [70, 'ligar'], [90, 900, 300]]} cliques={[44]} />
    </AreaDeAlvos>
  );
};

// --- Radar de ofertas ------------------------------------------------------------------------------

const RADAR = [
  {foto: 'relogio', nome: 'Smartwatch D20 Ultra', preco: 'R$ 89,90', com: 10, extra: 0},
  {foto: 'mochila', nome: 'Mochila notebook impermeável', preco: 'R$ 119,90', com: 14, extra: 6},
  {foto: 'fone', nome: 'Fone Bluetooth TWS Pro', preco: 'R$ 79,90', com: 12, extra: 4},
  {foto: 'secador', nome: 'Escova secadora 3 em 1', preco: 'R$ 149,90', com: 7, extra: 0},
];

export const CenaRadar: React.FC = () => {
  const f = useCurrentFrame();
  const ordenado = f >= 96;
  const lista = ordenado ? [...RADAR].sort((a, b) => b.com + b.extra - (a.com + a.extra)) : RADAR;
  const troca = entra(f, 96, 18);
  return (
    <AreaDeAlvos>
      <Card style={{padding: 24, display: 'flex', alignItems: 'center', gap: 18}}>
        <div style={{fontSize: 34}}>🔎</div>
        <div style={{fontSize: 32, fontWeight: 500, flex: 1}}>{f < 18 ? <span style={{color: '#A8A08A'}}>Ex.: fone, air fryer, vestido</span> : <Digitando texto="mais vendidos em eletrônicos" inicio={18} fim={58} />}</div>
      </Card>
      <div style={{display: 'flex', gap: 12, marginTop: 20, flexWrap: 'wrap'}}>
        <Chip texto="Mais vendidos" ativo={!ordenado} />
        <Alvo nome="ordem"><Chip texto="Maior comissão" ativo={ordenado} /></Alvo>
        <Chip texto="Maior desconto" />
      </div>
      <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginTop: 26, opacity: ordenado ? troca : 1}}>
        {lista.map((p, i) => (
          <Card key={p.nome} style={{padding: 18, transform: ordenado ? `translateY(${(1 - troca) * 40}px)` : undefined}}>
            <div style={{position: 'relative'}}>
              <img src={produto(p.foto)} style={{width: '100%', height: 250, objectFit: 'cover', borderRadius: 20, display: 'block'}} />
              <div style={{position: 'absolute', top: 12, left: 12, background: C.amarelo, color: C.verde, fontWeight: 800, fontSize: 24, padding: '6px 14px', borderRadius: 999}}>
                {p.com + p.extra}% comissão
              </div>
            </div>
            <div style={{fontSize: 24, fontWeight: 800, marginTop: 12, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis'}}>{p.nome}</div>
            <div style={{fontSize: 28, fontWeight: 800, marginTop: 4}}>{p.preco}</div>
            <Alvo nome={`copiar-${i}`} bloco><div style={{marginTop: 10, background: i === 0 && f > 160 && f < 175 ? C.amarelo : C.verde, color: i === 0 && f > 160 && f < 175 ? C.verde : C.creme,
              borderRadius: 14, textAlign: 'center', fontWeight: 800, fontSize: 22, padding: '12px 0'}}>Copiar meu link</div></Alvo>
          </Card>
        ))}
      </div>
      <Aviso texto="Seu link de afiliado foi copiado" inicio={168} duracao={60} />
      <Cursor pontos={[[10, 450, 60], [60, 450, 60], [86, 'ordem'], [110, 'ordem'], [150, 'copiar-0'], [190, 'copiar-0']]} cliques={[96, 162]} />
    </AreaDeAlvos>
  );
};

// --- Conversor de links ----------------------------------------------------------------------------

const LINHAS = [
  {texto: '🔥 OFERTAS DO DIA 🔥', link: null},
  {texto: 'Fone Bluetooth com cancelamento de ruído', link: ['shopee.com.br/Fone-Bluetooth-i.123.4567', 's.shopee.com.br/8Kz1aQ']},
  {texto: 'Air Fryer Digital 4L', link: ['s.shopee.com.br/outroAfiliado9', 's.shopee.com.br/4Lp9Xw']},
  {texto: 'Garrafa Térmica 1L Inox', link: ['shope.ee/A1b2C3d4', 's.shopee.com.br/2Vb7Tr']},
] as const;

export const CenaConversor: React.FC = () => {
  const f = useCurrentFrame();
  const convertido = f >= 84;
  return (
    <AreaDeAlvos>
      <Card style={{padding: 34}}>
        <div style={{fontSize: 24, fontWeight: 800, color: C.cinza, marginBottom: 14}}>{convertido ? 'Pronto pra encaminhar' : 'Cole o texto ou os links'}</div>
        <div style={{background: '#FBF9F3', border: `2px solid ${C.borda}`, borderRadius: 20, padding: 28, fontSize: 28, lineHeight: 1.5, minHeight: 540}}>
          {LINHAS.map((l, i) => {
            const aparece = entra(f, 6 + i * 8, 10);
            return (
              <div key={l.texto} style={{opacity: aparece, marginBottom: 14}}>
                <div style={{fontWeight: i === 0 ? 800 : 500}}>{l.texto}</div>
                {l.link && <Link antigo={l.link[0]} novo={l.link[1]} inicio={84 + i * 12} />}
              </div>
            );
          })}
        </div>
        <div style={{display: 'flex', gap: 14, marginTop: 24, alignItems: 'center'}}>
          <Chip texto="Manter o texto e trocar os links" ativo />
          <div style={{flex: 1}} />
          {/* o mesmo botão vira "Copiar texto" depois de converter */}
          <Alvo nome="botao">{convertido
            ? <Botao texto="Copiar texto" tipo="escuro" apertado={f >= 188 && f < 196 ? 1 : 0} />
            : <Botao texto="Converter" tipo="principal" apertado={f >= 70 && f < 78 ? 1 : 0} />}</Alvo>
        </div>
      </Card>
      <div style={{marginTop: 26, display: 'flex', justifyContent: 'center', opacity: entra(f, 130), fontSize: 30, fontWeight: 800, color: C.verde}}>
        ✓ 3 links trocados pelo seu link de afiliado
      </div>
      <Aviso texto="Texto copiado" inicio={196} duracao={50} />
      <Cursor pontos={[[20, 300, 700], [60, 'botao'], [100, 'botao'], [170, 'botao'], [190, 'botao']]} cliques={[72, 190]} />
    </AreaDeAlvos>
  );
};

const Link: React.FC<{antigo: string; novo: string; inicio: number}> = ({antigo, novo, inicio}) => {
  const f = useCurrentFrame();
  const t = entra(f, inicio, 12);
  return (
    <div style={{position: 'relative', height: 42}}>
      <div style={{position: 'absolute', color: '#9A9282', opacity: 1 - t, textDecoration: t > 0 ? 'line-through' : 'none'}}>👉 https://{antigo}</div>
      <div style={{position: 'absolute', opacity: t, transform: `translateY(${(1 - t) * 14}px)`}}>
        👉 <span style={{background: `rgba(242,194,48,${0.55 * t})`, borderRadius: 8, padding: '0 6px', color: C.verde, fontWeight: 800}}>https://{novo}</span>
      </div>
    </div>
  );
};

// --- Gerador de carrosséis ------------------------------------------------------------------------

export const CenaCarrosseis: React.FC = () => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const pronto = f >= 120;
  const slideAtual = f < 170 ? 0 : f < 215 ? 1 : 2;
  const deslize = mola(f, slideAtual === 0 ? 120 : slideAtual === 1 ? 170 : 215, fps, 18);
  return (
    <AreaDeAlvos>
      <Card style={{padding: 24, display: 'flex', gap: 16, alignItems: 'center'}}>
        <div style={{fontSize: 28, flex: 1, whiteSpace: 'nowrap', overflow: 'hidden'}}><Digitando texto="https://s.shopee.com.br/8Kz1aQ" inicio={8} fim={30} /></div>
        <Alvo nome="gerar"><Botao texto="Gerar carrossel" tipo="escuro" apertado={f >= 44 && f < 52 ? 1 : 0} style={{fontSize: 24, padding: '14px 24px'}} /></Alvo>
      </Card>
      {!pronto && f >= 50 && (
        <div style={{marginTop: 40, display: 'grid', gap: 18}}>
          <div style={{fontSize: 30, fontWeight: 800, color: C.verde}}>✨ A IA está escrevendo o roteiro{'.'.repeat(1 + (Math.floor(f / 8) % 3))}</div>
          {[0, 1, 2].map((i) => (
            <div key={i} style={{height: 44, borderRadius: 14, width: `${90 - i * 18}%`,
              background: `linear-gradient(90deg, ${C.borda} 0%, #FFF 50%, ${C.borda} 100%)`, backgroundSize: '200% 100%', backgroundPosition: `${(f * 6) % 200}% 0`}} />
          ))}
        </div>
      )}
      {pronto && (
        <div style={{marginTop: 34, position: 'relative', height: 760, overflow: 'hidden', opacity: entra(f, 120, 10)}}>
          <div style={{display: 'flex', gap: 30, transform: `translateX(${-(slideAtual === 0 ? 0 : slideAtual - 1 + deslize) * 638}px)`, paddingLeft: 116}}>
            <Slide><div style={{fontSize: 20, fontWeight: 800, letterSpacing: '.14em', color: '#8A6A00'}}>ACHADO DA SEMANA</div>
              <div style={{fontSize: 56, fontWeight: 800, lineHeight: 1.05, marginTop: 14}}>Fone <span style={{background: C.amarelo, padding: '0 8px', borderRadius: 8}}>sem fio</span> com 45% off</div>
              <div style={{marginTop: 26, display: 'flex', justifyContent: 'center'}}><Foto nome="fone" tamanho={380} raio={30} /></div></Slide>
            <Slide><div style={{fontSize: 46, fontWeight: 800, lineHeight: 1.1}}>Por que vale a pena</div>
              {['Cancelamento de ruído', 'Bateria pra 30 horas', 'Nota 4,8 com 15 mil vendas'].map((t) => (
                <div key={t} style={{display: 'flex', gap: 16, alignItems: 'center', fontSize: 32, marginTop: 30}}>
                  <span style={{width: 44, height: 44, borderRadius: '50%', background: C.verde, color: C.amarelo, display: 'grid', placeItems: 'center', fontSize: 24}}>✓</span>{t}</div>
              ))}</Slide>
            <Slide fundo={C.verde}><div style={{color: C.creme, fontSize: 30}}>De <s>R$ 199,90</s> por</div>
              <div style={{color: C.amarelo, fontSize: 96, fontWeight: 800, marginTop: 8}}>R$ 79,90</div>
              <div style={{marginTop: 40, background: C.amarelo, color: C.verde, fontWeight: 800, fontSize: 32, borderRadius: 999, padding: '20px 32px', display: 'inline-block'}}>Link na bio 👆</div></Slide>
          </div>
          <div style={{position: 'absolute', bottom: 0, left: 0, right: 0, display: 'flex', justifyContent: 'center', gap: 14}}>
            <Chip texto="Legenda pronta" ativo />
            <Chip texto="#hashtags" />
            <Chip texto="Baixar PNG" />
          </div>
        </div>
      )}
      <Cursor pontos={[[24, 600, 300], [40, 'gerar'], [60, 'gerar'], [80, 860, 500]]} cliques={[46]} />
    </AreaDeAlvos>
  );
};

const Slide: React.FC<{children: React.ReactNode; fundo?: string}> = ({children, fundo = C.branco}) => (
  <div style={{flex: 'none', width: 608, height: 680, borderRadius: 30, background: fundo, border: `2px solid ${C.borda}`, padding: 46,
    boxShadow: '0 18px 40px rgba(23,48,31,.12)'}}>{children}</div>
);

// --- Meu site -----------------------------------------------------------------------------------------

const BOTOES = ['💬 Grupo VIP de ofertas', '📣 Canal de ofertas no WhatsApp', '🎟️ Cupons do dia'];

export const CenaSite: React.FC = () => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const cor = f >= 150 ? C.verde : '#D6336C';
  const vitrine = interpolate(f, [175, 240], [0, -300], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return (
    <AreaDeAlvos style={{display: 'flex', gap: 36, alignItems: 'flex-start', justifyContent: 'center'}}>
      <div style={{width: 520, height: 1000, borderRadius: 70, background: '#101a14', padding: 18, flex: 'none', position: 'relative'}}>
        <div style={{height: '100%', borderRadius: 54, overflow: 'hidden', background: cor, padding: '70px 34px', color: C.branco, textAlign: 'center'}}>
          <div style={{transform: `scale(${mola(f, 6, fps)})`, width: 150, height: 150, margin: '0 auto', borderRadius: '50%', overflow: 'hidden', border: '6px solid rgba(255,255,255,.6)'}}>
            <Foto nome="bolsa" tamanho={150} raio={0} />
          </div>
          <div style={{fontSize: 38, fontWeight: 800, marginTop: 18}}><Digitando texto="Achadinhos da Bia" inicio={14} fim={40} cursor={false} /></div>
          <div style={{fontSize: 22, opacity: entra(f, 40) * 0.9, marginTop: 6}}>As melhores ofertas da Shopee, todo dia ✨</div>
          <div style={{marginTop: 26, display: 'grid', gap: 14}}>
            {BOTOES.map((b, i) => {
              const s = mola(f, 50 + i * 16, fps);
              return <div key={b} style={{background: C.branco, color: C.tinta, fontWeight: 800, fontSize: 22, borderRadius: 18, padding: '18px 10px',
                opacity: s, transform: `translateY(${(1 - s) * 30}px)`}}>{b}</div>;
            })}
          </div>
          <div style={{marginTop: 26, fontSize: 22, fontWeight: 800, textAlign: 'left', opacity: entra(f, 110)}}>Ofertas de hoje</div>
          <div style={{marginTop: 12, overflow: 'hidden', opacity: entra(f, 110)}}>
            <div style={{display: 'flex', gap: 14, transform: `translateX(${vitrine}px)`}}>
              {['fone', 'airfryer', 'relogio', 'garrafa', 'tenis', 'copo'].map((p) => (
                <div key={p} style={{flex: 'none', width: 150, background: C.branco, borderRadius: 16, padding: 8, color: C.tinta}}>
                  <Foto nome={p} tamanho={134} raio={10} />
                  <div style={{fontSize: 18, fontWeight: 800, marginTop: 6}}>Ver oferta</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
      <div style={{display: 'grid', gap: 18, marginTop: 120, width: 300}}>
        <Card style={{padding: 22}}>
          <div style={{fontSize: 20, color: C.cinza, fontWeight: 800}}>Seu endereço</div>
          <div style={{fontSize: 22, fontWeight: 800, marginTop: 6, color: C.verde}}>achadinhosdabia<br />.appfiliado.com.br</div>
        </Card>
        <Card style={{padding: 22, opacity: entra(f, 120)}}>
          <div style={{fontSize: 20, color: C.cinza, fontWeight: 800}}>Cor do site</div>
          <div style={{display: 'flex', gap: 10, marginTop: 12}}>
            {['#D6336C', C.verde, '#2F6FD8', '#E8590C'].map((c) => (
              <Alvo key={c} nome={`cor-${c}`}><div style={{width: 46, height: 46, borderRadius: '50%', background: c, outline: c === cor ? `4px solid ${C.amarelo}` : 'none', outlineOffset: 3}} /></Alvo>
            ))}
          </div>
        </Card>
        <Card style={{padding: 22, opacity: entra(f, 190)}}>
          <div style={{fontSize: 20, color: C.cinza, fontWeight: 800}}>Cliques em 30 dias</div>
          <div style={{fontSize: 44, fontWeight: 800}}><Contador valor={1389} inicio={190} duracao={40} /></div>
        </Card>
      </div>
      <Cursor pontos={[[100, 700, 500], [140, `cor-${C.verde}`], [160, `cor-${C.verde}`], [190, 760, 600]]} cliques={[148]} />
    </AreaDeAlvos>
  );
};

// --- Resultados e metas ------------------------------------------------------------------------------

const BARRAS = [42, 58, 35, 27, 49, 51, 33, 38, 18, 100, 30, 26, 34, 39, 46, 41, 47, 50, 33, 20, 44];

export const CenaResultados: React.FC = () => {
  const f = useCurrentFrame();
  const meta = interpolate(f, [120, 200], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return (
    <AreaDeAlvos>
      <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 18}}>
        {[['Faturamento', 51693.46, true], ['Comissão estimada', 4393.94, true], ['Comissão validada', 1554.97, true], ['Pedidos', 1348, false]].map(([r, v, reais], i) => (
          <Card key={r as string} style={{padding: 26, opacity: entra(f, i * 6)}}>
            <div style={{fontSize: 22, color: C.cinza}}>{r as string}</div>
            <div style={{fontSize: 44, fontWeight: 800, marginTop: 6}}><Contador valor={v as number} inicio={6 + i * 6} reais={reais as boolean} /></div>
          </Card>
        ))}
      </div>
      <Card style={{marginTop: 20, padding: 26}}>
        <div style={{fontSize: 26, fontWeight: 800}}>Faturamento por dia</div>
        <div style={{display: 'flex', alignItems: 'flex-end', gap: 8, height: 220, marginTop: 18}}>
          {BARRAS.map((b, i) => (
            <div key={i} style={{flex: 1, borderRadius: 8, background: i === BARRAS.length - 1 ? C.amarelo : C.verde,
              height: `${b * entra(f, 30 + i * 2, 16)}%`}} />
          ))}
        </div>
      </Card>
      <Card style={{marginTop: 20, padding: 26}}>
        <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'baseline'}}>
          <div style={{fontSize: 26, fontWeight: 800}}>Meta de Outubro</div>
          <div style={{fontSize: 24, color: C.cinza}}>faixa 100%: R$ 52.000</div>
        </div>
        <div style={{height: 30, borderRadius: 999, background: C.borda, marginTop: 18, overflow: 'hidden'}}>
          <div style={{height: '100%', width: `${meta * 100}%`, borderRadius: 999, background: meta >= 1 ? C.ok : C.verde}} />
        </div>
        <div style={{marginTop: 16, fontSize: 28, fontWeight: 800, color: meta >= 1 ? C.ok : C.tinta}}>
          {meta >= 1 ? '🎉 Faixa 100% batida: bônus de R$ 300' : `Faltam R$ ${Math.round(52000 * (1 - meta) * 0.12).toLocaleString('pt-BR')} pra faixa 100%`}
        </div>
      </Card>
    </AreaDeAlvos>
  );
};

// --- Emissor NFS-e ------------------------------------------------------------------------------------

const LOJAS = ['Utilidades BR 1 Ltda', 'Tech Plus Oficial Ltda', 'Beauty Box 1 Ltda', 'Casa & Cozinha Ltda', 'Moda Center Ltda'];

export const CenaNotas: React.FC = () => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const arquivo = mola(f, 8, fps);
  const notas = Math.round(interpolate(f, [60, 170], [0, 86], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}));
  const emails = Math.round(interpolate(f, [150, 230], [0, 83], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}));
  return (
    <AreaDeAlvos>
      <Card style={{display: 'flex', gap: 22, alignItems: 'center', transform: `translateY(${(1 - arquivo) * -120}px)`, opacity: arquivo}}>
        <div style={{width: 80, height: 80, borderRadius: 20, background: C.creme, display: 'grid', placeItems: 'center', fontSize: 40}}>📄</div>
        <div style={{flex: 1}}>
          <div style={{fontSize: 30, fontWeight: 800}}>MonthlyReport_202609.csv</div>
          <div style={{fontSize: 22, color: C.cinza}}>Relatório Mensal da Shopee · 86 lojas</div>
        </div>
        <Alvo nome="emitir"><Botao texto={f >= 50 ? 'Emitindo…' : 'Emitir 86 notas'} tipo="principal" apertado={f >= 40 && f < 48 ? 1 : 0} style={{fontSize: 24, padding: '14px 22px'}} /></Alvo>
      </Card>
      <Card style={{marginTop: 20}}>
        <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'baseline'}}>
          <div style={{fontSize: 28, fontWeight: 800}}>Notas fiscais</div>
          <div style={{fontSize: 40, fontWeight: 800}}>{notas} <span style={{fontSize: 24, color: C.cinza}}>de 86 autorizadas</span></div>
        </div>
        <div style={{height: 22, borderRadius: 999, background: C.borda, marginTop: 14, overflow: 'hidden'}}>
          <div style={{height: '100%', width: `${(notas / 86) * 100}%`, background: C.ok, borderRadius: 999}} />
        </div>
        <div style={{marginTop: 16}}>
          {LOJAS.map((l, i) => {
            const ok = notas >= (i + 1) * 15;
            return (
              <div key={l} style={{display: 'flex', alignItems: 'center', gap: 16, padding: '14px 0', borderTop: `2px solid ${C.borda}`, fontSize: 26}}>
                <span style={{width: 40, height: 40, borderRadius: '50%', display: 'grid', placeItems: 'center', fontSize: 22, background: ok ? C.ok : C.borda, color: C.branco}}>{ok ? '✓' : ''}</span>
                <span style={{flex: 1, fontWeight: 800}}>{l}</span>
                <span style={{color: ok ? C.ok : C.cinza, fontWeight: 800, fontSize: 22}}>{ok ? 'Autorizada' : 'Na fila'}</span>
              </div>
            );
          })}
        </div>
      </Card>
      <Card style={{marginTop: 20, display: 'flex', alignItems: 'center', gap: 20, opacity: entra(f, 150)}}>
        <div style={{fontSize: 40}}>✉️</div>
        <div style={{flex: 1, fontSize: 26}}><b>{emails} de 83</b> vendedores receberam o PDF e o XML</div>
      </Card>
      <Cursor pontos={[[20, 500, 400], [36, 'emitir'], [56, 'emitir'], [80, 860, 400]]} cliques={[42]} />
    </AreaDeAlvos>
  );
};
