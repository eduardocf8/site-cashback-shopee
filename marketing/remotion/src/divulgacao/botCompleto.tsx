/** Bot de WhatsApp: o vídeo completo. Abertura, 13 capítulos (um recurso cada, com a barra de progresso no
 * topo, como nos stories) e o encerramento com o preço e as ferramentas inclusas. Os capítulos se empurram
 * de lado (o que sai e o que entra se cruzam), então nunca fica tela vazia entre eles.
 *
 * Tudo o que aparece está no produto (landing/recursos.py, bot()): limites do Standard em licencas/planos.py. */
import React from 'react';
import {AbsoluteFill, Easing, Img, Sequence, useCurrentFrame, useVideoConfig} from 'remotion';
import {C, FONTE} from '../appfiliado/marca';
import {Interruptor, produto} from '../appfiliado/ui';
import {CelularNaCena, ConversaZap, Cortina, DURACAO_FINAL, Final, Fundo, Legendas, type Fala, type Mensagem, Titulo, Toque, mola, vai} from './comum';
import {AMARELO_TEXTO, Centro, ConviteGrupo, FotoGrupo, GruposDoLink, Membros, PaginaEntrada, Painel, Rotulo, Selo} from './botTelas';
import {CTA, GRUPO, INCLUSOS, OFERTAS} from './textos';

const TOPO_TITULO = 346;

// --- peças -------------------------------------------------------------------------------------------

const Chip: React.FC<{texto: string; ativo?: boolean; tamanho?: number}> = ({texto, ativo, tamanho = 29}) => (
  <span style={{display: 'inline-flex', alignItems: 'center', padding: '12px 20px', borderRadius: 999, fontSize: tamanho, fontWeight: 800, whiteSpace: 'nowrap',
    background: ativo ? C.verde : '#FAF7EF', color: ativo ? C.creme : C.tinta, border: `2px solid ${ativo ? C.verde : C.borda}`}}>{texto}</span>
);

const Linha: React.FC<{nome: string; children: React.ReactNode; primeira?: boolean}> = ({nome, children, primeira}) => (
  <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 20, padding: '24px 0', borderTop: primeira ? 'none' : `2px solid ${C.borda}`, fontSize: 36}}>
    <span style={{color: C.cinza, fontWeight: 500}}>{nome}</span>
    <span style={{fontWeight: 800, textAlign: 'right'}}>{children}</span>
  </div>
);

/** Valor que troca de baixo pra cima no frame `quando`. */
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

/** QR Code de mentira (desenho fixo, sem sorteio) com a linha de leitura passando. */
const QrCode: React.FC<{tamanho: number; leitura: number; lido: number}> = ({tamanho, leitura, lido}) => {
  const n = 25;
  const m = tamanho / n;
  const olho = (i: number, j: number) => {
    const dentro = (a: number, b: number) => i >= a && i < a + 7 && j >= b && j < b + 7;
    for (const [a, b] of [[0, 0], [0, n - 7], [n - 7, 0]]) {
      if (dentro(a, b)) {
        const di = i - a;
        const dj = j - b;
        return di === 0 || di === 6 || dj === 0 || dj === 6 || (di >= 2 && di <= 4 && dj >= 2 && dj <= 4) ? 1 : 0;
      }
    }
    return -1;
  };
  const celulas: React.ReactNode[] = [];
  for (let i = 0; i < n; i++) {
    for (let j = 0; j < n; j++) {
      const o = olho(i, j);
      const cheio = o === -1 ? (i * 31 + j * 17 + ((i * j) % 7) * 5) % 9 < 4 : o === 1;
      if (cheio) celulas.push(<div key={`${i}-${j}`} style={{position: 'absolute', left: j * m, top: i * m, width: m + 0.5, height: m + 0.5, background: C.tinta}} />);
    }
  }
  return (
    <div style={{position: 'relative', width: tamanho, height: tamanho, flex: 'none'}}>
      {celulas}
      <div style={{position: 'absolute', left: -10, right: -10, top: leitura * tamanho, height: 6, borderRadius: 3, background: C.amarelo, boxShadow: `0 0 24px ${C.amarelo}`,
        opacity: lido > 0 ? 0 : 1}} />
      <div style={{position: 'absolute', inset: -12, background: 'rgba(255,255,255,.88)', borderRadius: 20, display: 'grid', placeItems: 'center', opacity: lido}}>
        <div style={{width: 150, height: 150, borderRadius: '50%', background: C.ok, color: C.branco, display: 'grid', placeItems: 'center', fontSize: 90, fontWeight: 800,
          transform: `scale(${0.6 + 0.4 * lido})`}}>✓</div>
      </div>
    </div>
  );
};

// --- os capítulos -------------------------------------------------------------------------------------

type Capitulo = {nome: string; titulo: string; duracao: number; falas: Fala[]; Tela: React.FC};

const Conexao: React.FC = () => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const lido = mola(f, 58, fps, 12);
  return (
    <Painel centro inicio={0}>
      <div style={{display: 'flex', gap: 34, alignItems: 'center'}}>
        <QrCode tamanho={360} leitura={vai(f, 8, 54, 0.05, 0.92, (t) => t)} lido={f >= 58 ? lido : 0} />
        <div style={{display: 'grid', gap: 22, fontSize: 30, fontWeight: 800}}>
          {['Abra o WhatsApp', 'Aparelhos conectados', 'Leia o QR Code'].map((p, i) => (
            <div key={p} style={{display: 'flex', gap: 14, alignItems: 'center', opacity: vai(f, 4 + i * 8, 16 + i * 8)}}>
              <span style={{width: 46, height: 46, borderRadius: '50%', background: C.verde, color: C.creme, display: 'grid', placeItems: 'center', fontSize: 24, flex: 'none'}}>{i + 1}</span>{p}
            </div>
          ))}
        </div>
      </div>
      <div style={{marginTop: 26, display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: f >= 58 ? '#E3F1E7' : '#FAF7EF', borderRadius: 22, padding: '18px 24px'}}>
        <span style={{fontSize: 30, fontWeight: 800}}>{f >= 58 ? 'Conectado' : 'Aguardando a leitura…'}</span>
        <span style={{fontSize: 26, color: C.cinza}}>{f >= 58 ? '+55 11 98888-7777' : ''}</span>
      </div>
    </Painel>
  );
};

const NO_GRUPO: Mensagem[] = OFERTAS.slice(0, 3).map((o, i) => ({...o, tipo: 'oferta', f: 6 + i * 30, hora: `20:${String(i * 15).padStart(2, '0')}`}));

const Automatico: React.FC = () => (
  <CelularNaCena inicio={-6} hora="20:30">
    <ConversaZap nome={GRUPO.nome} membros={GRUPO.membros} mensagens={NO_GRUPO} />
  </CelularNaCena>
);

const Busca: React.FC = () => {
  const f = useCurrentFrame();
  return (
    <Painel centro inicio={0}>
      <Rotulo>Buscar</Rotulo>
      <div style={{display: 'flex', flexWrap: 'wrap', gap: 12, marginTop: 14}}>
        {['Ofertas em geral', 'Palavra-chave', 'Loja', 'Categoria'].map((c, i) => <Chip key={c} texto={c} tamanho={25} ativo={f >= 24 ? i === 3 : i === 0} />)}
      </div>
      <div style={{marginTop: 14, fontSize: 28, fontWeight: 800, color: AMARELO_TEXTO, opacity: vai(f, 26, 36)}}>Categoria: Casa e Decoração</div>
      <Rotulo style={{marginTop: 26}}>Ordem</Rotulo>
      <div style={{display: 'flex', flexWrap: 'wrap', gap: 12, marginTop: 14}}>
        {['Mais vendidos', 'Maior comissão', 'Maior desconto'].map((c, i) => <Chip key={c} texto={c} ativo={f >= 44 ? i === 1 : i === 0} />)}
      </div>
      <div style={{marginTop: 18}}>
        <Linha nome="Comissão mínima" primeira>{Math.round(vai(f, 54, 80, 0, 10))}%</Linha>
        <Linha nome="Desconto mínimo">{Math.round(vai(f, 60, 86, 0, 30))}%</Linha>
        <Linha nome="Preço até">R$ {Math.round(vai(f, 66, 92, 0, 150))}</Linha>
      </div>
    </Painel>
  );
};

const DIAS = ['S', 'T', 'Q', 'Q', 'S', 'S', 'D'];

const Ritmo: React.FC = () => {
  const f = useCurrentFrame();
  const intervalo = f >= 30 ? 15 : f >= 18 ? 20 : 30;
  return (
    <Painel centro inicio={0}>
      <Linha nome="Intervalo" primeira>
        <span style={{display: 'inline-flex', alignItems: 'center', gap: 16}}>
          <span style={{width: 50, height: 50, borderRadius: '50%', border: `2px solid ${C.borda}`, display: 'grid', placeItems: 'center'}}>−</span>
          a cada {intervalo} min
          <span style={{width: 50, height: 50, borderRadius: '50%', border: `2px solid ${C.borda}`, display: 'grid', placeItems: 'center'}}>+</span>
        </span>
      </Linha>
      <div style={{padding: '20px 0', borderTop: `2px solid ${C.borda}`}}>
        <div style={{display: 'flex', justifyContent: 'space-between', fontSize: 33}}><span style={{color: C.cinza}}>Horário</span><b>8h às 22h</b></div>
        <div style={{position: 'relative', height: 18, borderRadius: 999, background: '#EDE8D9', marginTop: 16}}>
          <div style={{position: 'absolute', left: `${(8 / 24) * 100}%`, width: `${(14 / 24) * 100 * vai(f, 30, 56)}%`, top: 0, bottom: 0, borderRadius: 999, background: C.verde}} />
        </div>
      </div>
      <div style={{padding: '20px 0', borderTop: `2px solid ${C.borda}`, display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
        <span style={{fontSize: 33, color: C.cinza}}>Dias</span>
        <span style={{display: 'flex', gap: 8}}>
          {DIAS.map((d, i) => {
            const ligado = i < 6 || f >= 64;
            return <span key={i} style={{width: 50, height: 50, borderRadius: 14, display: 'grid', placeItems: 'center', fontSize: 24, fontWeight: 800,
              background: ligado ? C.verde : '#FAF7EF', color: ligado ? C.creme : C.cinza}}>{d}</span>;
          })}
        </span>
      </div>
      <Linha nome="Sem repetir produto">por 7 dias</Linha>
    </Painel>
  );
};

const PROXIMAS = OFERTAS.slice(3, 6);

const Teste: React.FC = () => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  return (
    <Painel centro inicio={0}>
      <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
        <div style={{fontSize: 34, fontWeight: 800}}>Próximas ofertas</div>
        <div style={{position: 'relative', background: C.amarelo, color: C.verde, fontWeight: 800, fontSize: 26, borderRadius: 999, padding: '12px 24px',
          transform: `scale(${f >= 12 && f < 18 ? 0.94 : 1})`}}>Testar busca<Toque x={90} y={26} f={12} /></div>
      </div>
      <div style={{marginTop: 18, display: 'grid', gap: 12}}>
        {PROXIMAS.map((o, i) => {
          const t = mola(f, 20 + i * 8, fps, 13);
          return (
            <div key={o.nome} style={{display: 'flex', gap: 18, alignItems: 'center', background: '#FAF7EF', borderRadius: 22, padding: 12, opacity: Math.min(1, t * 1.4),
              transform: `translateY(${(1 - t) * 30}px)`}}>
              <Img src={produto(o.foto)} style={{width: 92, height: 92, borderRadius: 16, objectFit: 'cover'}} />
              <div style={{flex: 1, minWidth: 0}}>
                <div style={{fontSize: 26, fontWeight: 800, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis'}}>{o.nome}</div>
                <div style={{fontSize: 24, color: C.cinza}}><span style={{color: C.ok, fontWeight: 800}}>{o.por}</span> · {o.vendidos}</div>
              </div>
            </div>
          );
        })}
      </div>
      <div style={{marginTop: 20, display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '18px 0 0', borderTop: `2px solid ${C.borda}`}}>
        <div>
          <div style={{fontSize: 30, fontWeight: 800}}>Modo simulação</div>
          <div style={{fontSize: 23, color: C.cinza}}>faz tudo, menos enviar</div>
        </div>
        <div style={{transform: 'scale(1.2)', transformOrigin: 'right center'}}><Interruptor ligado={vai(f, 68, 76)} /></div>
      </div>
    </Painel>
  );
};

const DATAS = ['9.9', '10.10', '11.11', 'Black Friday', '12.12'];

const Campanha: React.FC = () => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  return (
    <Painel centro inicio={0}>
      <div style={{display: 'flex', flexWrap: 'wrap', gap: 10, justifyContent: 'center'}}>
        {DATAS.map((d, i) => {
          const t = mola(f, 4 + i * 5, fps, 12);
          return <span key={d} style={{display: 'inline-flex', alignItems: 'center', gap: 8, background: C.verde, color: C.creme, borderRadius: 18, padding: '10px 15px',
            fontSize: 26, fontWeight: 800, whiteSpace: 'nowrap', transform: `scale(${0.7 + 0.3 * t})`, opacity: Math.min(1, t * 1.4)}}>
            <span style={{width: 26, height: 26, borderRadius: 8, background: C.amarelo, color: C.verde, display: 'grid', placeItems: 'center', fontSize: 17}}>✓</span>{d}</span>;
        })}
      </div>
      <div style={{marginTop: 18}}>
        <Linha nome="Intervalo" primeira><Troca de="a cada 30 min" para="a cada 15 min" quando={36} /></Linha>
        <Linha nome="Abertura"><Troca de="—" para="📣 É hoje: 11.11!" quando={46} /></Linha>
        <Linha nome="Cupom"><Troca de="—" para="ONZEONZE" quando={56} /></Linha>
      </div>
    </Painel>
  );
};

const Alerta: React.FC = () => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const preco = vai(f, 14, 48, 329.9, 279.9);
  const caiu = f >= 48;
  const msg = mola(f, 58, fps, 13);
  const brl = (v: number) => 'R$ ' + v.toLocaleString('pt-BR', {minimumFractionDigits: 2, maximumFractionDigits: 2});
  return (
    <Painel centro inicio={0}>
      <div style={{display: 'flex', gap: 24, alignItems: 'center'}}>
        <Img src={produto('airfryer')} style={{width: 170, height: 170, borderRadius: 24, objectFit: 'cover'}} />
        <div style={{flex: 1}}>
          <div style={{fontSize: 30, fontWeight: 800, lineHeight: 1.2}}>Air Fryer 4L com timer e painel touch</div>
          <div style={{display: 'flex', alignItems: 'baseline', gap: 14, marginTop: 10}}>
            <span style={{fontSize: 52, fontWeight: 800, color: caiu ? C.ok : C.tinta, fontVariantNumeric: 'tabular-nums'}}>{brl(preco)}</span>
            {caiu && <Selo texto="−15%" tom="ok" tamanho={26} />}
          </div>
          <div style={{fontSize: 23, color: C.cinza}}>Conferido agora · antes {brl(329.9)}</div>
        </div>
      </div>
      <div style={{marginTop: 24, background: '#E9E2D3', borderRadius: 26, padding: 18, opacity: Math.min(1, msg * 1.4), transform: `translateY(${(1 - msg) * 30}px)`}}>
        <div style={{background: C.branco, borderRadius: '8px 22px 22px 22px', padding: '16px 20px', fontSize: 27, lineHeight: 1.35}}>
          <b>📉 Baixou o preço!</b><br />Air Fryer 4L de <s style={{color: C.cinza}}>R$ 329,90</s> por <b style={{color: C.ok}}>R$ 279,90</b><br />
          <span style={{color: '#2F6FD8'}}>👉 s.shopee.com.br/4Lp9Xw</span>
        </div>
        <div style={{fontSize: 21, color: C.cinza, marginTop: 8, textAlign: 'right'}}>no grupo {GRUPO.nome}</div>
      </div>
    </Painel>
  );
};

const RECADO = '🎁 Cupom de R$ 20 liberado agora! Corre que acaba 👇';

const Avulsa: React.FC = () => {
  const f = useCurrentFrame();
  const letras = Math.round(vai(f, 6, 46, 0, RECADO.length, (t) => t));
  const agendada = f >= 86;
  return (
    <Painel centro inicio={0}>
      <Rotulo>Mensagem</Rotulo>
      <div style={{marginTop: 12, background: '#FAF7EF', border: `2px solid ${C.borda}`, borderRadius: 22, padding: '20px 22px', fontSize: 31, minHeight: 130, lineHeight: 1.35}}>
        {RECADO.slice(0, letras)}<span style={{opacity: f < 50 && Math.floor(f / 8) % 2 === 0 ? 1 : 0, borderLeft: `3px solid ${C.tinta}`, marginLeft: 2}} />
      </div>
      <Rotulo style={{marginTop: 24}}>Para</Rotulo>
      <div style={{display: 'flex', gap: 12, marginTop: 12}}>{['Todos os grupos', 'Um nicho', 'Escolher'].map((c, i) => <Chip key={c} texto={c} ativo={i === 0} />)}</div>
      <Rotulo style={{marginTop: 24}}>Quando</Rotulo>
      <div style={{display: 'flex', gap: 12, marginTop: 12, alignItems: 'center', flexWrap: 'wrap'}}>
        {['Agora', 'Agendar', 'Toda semana'].map((c, i) => <Chip key={c} texto={c} ativo={f >= 58 ? i === 2 : i === 0} />)}
        <span style={{fontSize: 28, fontWeight: 800, color: AMARELO_TEXTO, opacity: vai(f, 62, 72)}}>sexta, 20:00</span>
      </div>
      <div style={{marginTop: 26, background: agendada ? C.ok : C.verde, color: C.creme, borderRadius: 999, textAlign: 'center', padding: '20px 0', fontSize: 30, fontWeight: 800,
        transform: `scale(${f >= 80 && f < 86 ? 0.95 : 1})`}}>{agendada ? '✓ Agendada pra toda sexta' : 'Agendar'}</div>
    </Painel>
  );
};

const PREMIUM = [
  {titulo: 'Envio por nicho', texto: 'Cada grupo recebe as ofertas do seu tema'},
  {titulo: 'Copiar de outros grupos', texto: 'A oferta de outro afiliado sai com o seu link'},
  {titulo: 'Revisão do texto com IA', texto: 'Texto melhor sem mexer no preço e no link'},
];

const Premium: React.FC = () => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  return (
    <Centro><div style={{display: 'grid', gap: 22, fontFamily: FONTE}}>
      {PREMIUM.map((p, i) => {
        const t = mola(f, 4 + i * 40, fps, 13);
        const atual = f >= 4 + i * 40 && (i === PREMIUM.length - 1 || f < 4 + (i + 1) * 40);
        return (
          <div key={p.titulo} style={{background: atual ? C.branco : 'rgba(255,255,255,.9)', color: C.tinta, borderRadius: 32, padding: '26px 30px', display: 'flex', gap: 22, alignItems: 'center',
            border: `4px solid ${atual ? C.amarelo : 'transparent'}`, boxShadow: '0 20px 44px rgba(10,25,16,.25)', opacity: Math.min(1, t * 1.4), transform: `translateX(${(1 - t) * 120}px)`}}>
            <span style={{width: 70, height: 70, borderRadius: 20, background: C.verde, color: C.amarelo, display: 'grid', placeItems: 'center', fontSize: 36, flex: 'none'}}>{['🎯', '📋', '✨'][i]}</span>
            <div style={{flex: 1}}>
              <div style={{display: 'flex', alignItems: 'center', gap: 12}}><span style={{fontSize: 33, fontWeight: 800}}>{p.titulo}</span><Selo texto="Premium" tom="amarelo" tamanho={20} /></div>
              <div style={{fontSize: 26, color: C.cinza, marginTop: 6, lineHeight: 1.3}}>{p.texto}</div>
            </div>
          </div>
        );
      })}
    </div></Centro>
  );
};

/** O link de entrada: a página que vai no anúncio ou na bio; quem toca cai no grupo que tem vaga. */
const LinkDeEntrada: React.FC = () => {
  const f = useCurrentFrame();
  const convite = vai(f, 50, 66);
  return (
    <CelularNaCena inicio={-6} hora="20:14">
      <PaginaEntrada toque={44} />
      <Toque x={280} y={708} f={44} />
      {convite > 0 && <ConviteGrupo nome="Achadinhos da Bia #2" membros="987 participantes" t={convite} />}
    </CelularNaCena>
  );
};

const MembrosCap: React.FC = () => (
  <Painel centro inicio={0}>
    <Membros inicio={4} aviso={58} duracao={50} grupos={[
      {nome: 'Achadinhos da Bia #1', de: 1006, ate: 1019, dia: '+13'},
      {nome: 'Achadinhos da Bia #2', de: 958, ate: 986, dia: '+28'},
      {nome: 'Casa e Cozinha', de: 788, ate: 812, dia: '+24'},
      {nome: 'Achadinhos da Bia #3', de: 604, ate: 640, dia: '+36'},
    ]} />
  </Painel>
);

const Lotou: React.FC = () => {
  const f = useCurrentFrame();
  const novo = vai(f, 66, 84);
  return (
    <Painel centro inicio={0}>
      <Rotulo>Link de entrada · grupos em ordem</Rotulo>
      <div style={{marginTop: 18}}>
        <GruposDoLink compacto inicio={8} duracao={50} grupos={[
          {nome: 'Achadinhos da Bia #2', de: 990, ate: 1000},
          {nome: 'Achadinhos da Bia #3', de: 972, ate: 1000},
          {nome: 'Achadinhos da Bia #4', de: 0, ate: 6},
        ]} />
      </div>
      <div style={{marginTop: 16, display: 'flex', alignItems: 'center', gap: 16, background: '#FFF6D6', borderRadius: 22, padding: '16px 20px', opacity: novo,
        transform: `translateY(${(1 - novo) * 24}px)`}}>
        <FotoGrupo tamanho={58} />
        <div style={{flex: 1, fontSize: 27, fontWeight: 800, lineHeight: 1.25}}>Achadinhos da Bia #4 criado sozinho e já no link de entrada</div>
        <Selo texto="Premium" tom="amarelo" tamanho={20} />
      </div>
    </Painel>
  );
};

const SUB_IDS = [['Grupo VIP', 'grupovip', 1284.6], ['Achadinhos #2', 'grupo2', 912.3], ['Casa e cozinha', 'casa', 486.2], ['Beleza', 'beleza', 301.7]] as const;

const PorGrupo: React.FC = () => {
  const f = useCurrentFrame();
  return (
    <Painel centro inicio={0}>
      <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'baseline'}}>
        <div style={{fontSize: 32, fontWeight: 800}}>Comissão por Sub ID</div>
        <div style={{fontSize: 23, color: C.cinza}}>este mês</div>
      </div>
      <div style={{marginTop: 20, display: 'grid', gap: 20}}>
        {SUB_IDS.map(([nome, sub, v], i) => {
          const t = vai(f, 8 + i * 5, 50 + i * 5);
          return (
            <div key={sub} style={{display: 'grid', gridTemplateColumns: '230px 1fr', alignItems: 'center', gap: 18}}>
              <div><div style={{fontSize: 28, fontWeight: 800}}>{nome}</div><div style={{fontSize: 20, color: C.cinza}}>{sub}</div></div>
              <div style={{display: 'flex', alignItems: 'center', gap: 14}}>
                <div style={{height: 34, borderRadius: 10, width: `${(v / 1284.6) * 72 * t}%`, background: i === 0 ? C.amarelo : C.verde}} />
                <span style={{fontSize: 26, fontWeight: 800, whiteSpace: 'nowrap', fontVariantNumeric: 'tabular-nums'}}>
                  R$ {(v * t).toLocaleString('pt-BR', {minimumFractionDigits: 2, maximumFractionDigits: 2})}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </Painel>
  );
};

const CAPITULOS: Capitulo[] = [
  {nome: 'Conexão', titulo: 'Conecte o WhatsApp\n*em minutos.*', duracao: 110, Tela: Conexao, falas: [
    {f: 8, texto: 'Pelo QR Code como no WhatsApp Web', icone: '📷'}, {f: 62, texto: 'Sem deixar computador ligado', icone: '💻', tom: 'amarelo'}]},
  {nome: 'Ofertas', titulo: 'Ofertas no automático\n*com o seu link.*', duracao: 110, Tela: Automatico, falas: [
    {f: 8, texto: 'Foto, preço e o seu link de afiliado', icone: '🔗'}, {f: 62, texto: 'Em grupos e canais do WhatsApp', icone: '📣', tom: 'amarelo'}]},
  {nome: 'Busca e filtros', titulo: 'Você escolhe\n*o que vai pro grupo.*', duracao: 116, Tela: Busca, falas: [
    {f: 8, texto: 'Palavra, loja ou 15 categorias', icone: '🗂️'}, {f: 62, texto: 'Comissão, desconto e preço', icone: '🎯', tom: 'amarelo'}]},
  {nome: 'Ritmo', titulo: 'No seu ritmo\n*e no seu horário.*', duracao: 110, Tela: Ritmo, falas: [
    {f: 8, texto: 'Intervalo, horário e dias', icone: '🗓️'}, {f: 62, texto: 'Sem repetir produto no grupo', icone: '♻️', tom: 'amarelo'}]},
  {nome: 'Testar', titulo: 'Veja antes\n*o que vai sair.*', duracao: 112, Tela: Teste, falas: [
    {f: 8, texto: 'Sem gerar link e sem enviar', icone: '👀'}, {f: 66, texto: 'E tem o modo simulação', icone: '🧪', tom: 'amarelo'}]},
  {nome: 'Modo campanha', titulo: 'Datas da Shopee\n*no modo campanha.*', duracao: 110, Tela: Campanha, falas: [
    {f: 8, texto: 'Ritmo, frase e cupom só no dia', icone: '⚡'}, {f: 64, texto: 'Depois volta ao normal sozinho', icone: '↺', tom: 'amarelo'}]},
  {nome: 'Alerta de preço', titulo: 'O preço caiu?\n*O grupo fica sabendo.*', duracao: 116, Tela: Alerta, falas: [
    {f: 8, texto: 'O bot confere o preço sozinho', icone: '🔔'}, {f: 62, texto: 'E avisa no grupo com o seu link', icone: '📲', tom: 'amarelo'}]},
  {nome: 'Mensagens', titulo: 'Recados pros grupos\n*na hora ou agendados.*', duracao: 118, Tela: Avulsa, falas: [
    {f: 8, texto: 'Pra todos os grupos ou só alguns', icone: '📣'}, {f: 66, texto: 'Links da Shopee viram o seu', icone: '🔗', tom: 'amarelo'}]},
  {nome: 'Premium', titulo: 'No Premium\n*tem ainda mais.*', duracao: 138, Tela: Premium, falas: [
    {f: 6, texto: 'Cada grupo com o seu tema', icone: '🎯'}, {f: 46, texto: 'Ofertas copiadas com o seu link', icone: '📋', tom: 'amarelo'},
    {f: 86, texto: 'A IA revisa o texto antes', icone: '✨'}]},
  {nome: 'Link de entrada', titulo: 'Um link só\npra *todos os grupos.*', duracao: 132, Tela: LinkDeEntrada, falas: [
    {f: 6, texto: 'Um link só no anúncio ou na bio', icone: '📣'}, {f: 48, texto: 'A pessoa toca e cai num grupo com vaga', icone: '👉', tom: 'amarelo'},
    {f: 92, texto: 'Encheu? Ele manda pro próximo', icone: '🔁'}]},
  {nome: 'Membros', titulo: 'Veja quais grupos\n*estão lotando.*', duracao: 110, Tela: MembrosCap, falas: [
    {f: 8, texto: 'Entradas e saídas de cada grupo', icone: '📈'}, {f: 60, texto: 'Aviso quando passa de 95%', icone: '⚠️', tom: 'amarelo'}]},
  {nome: 'Grupo novo', titulo: 'Lotou? Ele cria\n*o próximo sozinho.*', duracao: 128, Tela: Lotou, falas: [
    {f: 8, texto: 'Quando todos estão quase cheios', icone: '🤖'}, {f: 70, texto: 'Premium: já entra no link de entrada', icone: '✨', tom: 'amarelo'}]},
  {nome: 'Resultados', titulo: 'Saiba quanto\n*cada grupo vende.*', duracao: 112, Tela: PorGrupo, falas: [
    {f: 8, texto: 'Um Sub ID próprio por grupo', icone: '🏷️'}, {f: 62, texto: 'A comissão de cada um no painel', icone: '📊', tom: 'amarelo'}]},
];

const SOBRA = 0; // os capítulos não se cruzam: o próximo entra quando o anterior já saiu

/** Um capítulo: o chapéu com o número, o título, a tela e as legendas. Entra pela direita e sai pela esquerda. */
const CenaDoCapitulo: React.FC<{c: Capitulo; numero: number}> = ({c, numero}) => {
  const f = useCurrentFrame();
  // um de cada vez: o que sai some nos últimos 6 quadros dele e o que entra só começa depois (nunca dois na tela)
  const entra_ = vai(f, 0, 13);
  const some = vai(f, c.duracao - 6, c.duracao, 0, 1, (t) => t);
  const desliza = vai(f, c.duracao - 6, c.duracao, 0, 1, Easing.in(Easing.cubic));
  const {Tela} = c;
  return (
    <AbsoluteFill style={{fontFamily: FONTE, opacity: Math.min(entra_ * 1.3, 1) * (1 - some), transform: `translateX(${(1 - entra_) * 160 - desliza * 160}px)`}}>
      <div style={{position: 'absolute', left: 90, right: 90, top: TOPO_TITULO}}>
        <div style={{fontSize: 28, fontWeight: 800, letterSpacing: '.14em', textTransform: 'uppercase', color: C.amarelo}}>{String(numero).padStart(2, '0')} · {c.nome}</div>
        <Titulo texto={c.titulo} inicio={2} tamanho={80} cor={C.creme} style={{marginTop: 18}} />
      </div>
      <Tela />
      <Legendas falas={c.falas} />
    </AbsoluteFill>
  );
};

/** A barra de progresso no topo: um traço por capítulo, o atual enchendo. */
const Progresso: React.FC<{inicios: number[]}> = ({inicios}) => {
  const f = useCurrentFrame();
  return (
    <div style={{position: 'absolute', left: 90, right: 90, top: 300, display: 'flex', gap: 8, zIndex: 80}}>
      {CAPITULOS.map((c, i) => {
        const cheio = vai(f, inicios[i], inicios[i] + c.duracao, 0, 1, (t) => t);
        return (
          <div key={c.nome} style={{flex: 1, height: 8, borderRadius: 4, background: 'rgba(246,243,234,.2)', overflow: 'hidden'}}>
            <div style={{width: `${cheio * 100}%`, height: '100%', background: C.amarelo}} />
          </div>
        );
      })}
    </div>
  );
};

const Abertura: React.FC = () => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const pilula = mola(f, 22, fps, 13);
  return (
    <AbsoluteFill style={{fontFamily: FONTE, alignItems: 'center', justifyContent: 'center', textAlign: 'center', padding: '0 80px'}}>
      <Fundo tom="escuro" />
      <Titulo texto={'Tudo o que o\n*Bot de WhatsApp*\nfaz por você'} inicio={-12} tamanho={104} alinhar="center" cor={C.creme} />
      <div style={{marginTop: 56, background: C.amarelo, color: C.verde, fontSize: 40, fontWeight: 800, borderRadius: 999, padding: '20px 40px',
        opacity: Math.min(1, pilula * 1.4), transform: `scale(${0.85 + 0.15 * pilula})`}}>13 recursos em menos de 1 minuto</div>
    </AbsoluteFill>
  );
};

const ABERTURA = 78;
const INICIOS = CAPITULOS.reduce<number[]>((a, c, i) => [...a, i === 0 ? ABERTURA : a[i - 1] + CAPITULOS[i - 1].duracao], []);
const FIM_DOS_CAPITULOS = INICIOS[INICIOS.length - 1] + CAPITULOS[CAPITULOS.length - 1].duracao;
export const DURACAO_BOT_COMPLETO = FIM_DOS_CAPITULOS + DURACAO_FINAL.comInclusos;

export const BotCompleto: React.FC = () => (
  <AbsoluteFill style={{background: C.verde}}>
    <Sequence durationInFrames={ABERTURA}><Abertura /></Sequence>
    <Sequence from={ABERTURA} durationInFrames={FIM_DOS_CAPITULOS - ABERTURA}>
      <Fundo tom="escuro" />
    </Sequence>
    {CAPITULOS.map((c, i) => (
      <Sequence key={c.nome} from={INICIOS[i]} durationInFrames={c.duracao + (i === CAPITULOS.length - 1 ? 0 : SOBRA)}>
        <CenaDoCapitulo c={c} numero={i + 1} />
      </Sequence>
    ))}
    <Sequence from={ABERTURA} durationInFrames={FIM_DOS_CAPITULOS - ABERTURA}><ProgressoNaCena inicios={INICIOS} /></Sequence>
    <Sequence from={ABERTURA - 9} durationInFrames={18}><Cortina /></Sequence>
    <Sequence from={FIM_DOS_CAPITULOS} durationInFrames={DURACAO_FINAL.comInclusos}>
      <Final frase={'Tudo isso\n*num bot só.*'} linha={CTA.bot} inclusos={INCLUSOS} />
    </Sequence>
    <Sequence from={FIM_DOS_CAPITULOS - 9} durationInFrames={18}><Cortina /></Sequence>
  </AbsoluteFill>
);

/** A barra de progresso dentro da Sequence (o frame dela começa na abertura). */
const ProgressoNaCena: React.FC<{inicios: number[]}> = ({inicios}) => <Progresso inicios={inicios.map((x) => x - ABERTURA)} />;

