/** Telas do Bot de WhatsApp recriadas para os vídeos "Grupos cheios" e "Bot completo": a página do link
 * de entrada, o convite do grupo, os grupos do link enchendo na ordem, o painel de membros, a criação do
 * próximo grupo e os cartões curtos de cada recurso. Os dados são os da conta fictícia "Achadinhos da Bia",
 * os mesmos dos prints do painel. Cada tela recebe o frame da cena (ou usa o da Sequence onde está). */
import React from 'react';
import {Img, useCurrentFrame, useVideoConfig} from 'remotion';
import {C, FONTE} from '../appfiliado/marca';
import {Icone, Interruptor, produto} from '../appfiliado/ui';
import {POS, mola, vai} from './comum';

export const VERMELHO = '#B42318';
export const VERMELHO_SUAVE = '#FDECEA';
export const ALERTA = '#7A5B00';
export const ALERTA_SUAVE = '#FBF1CF';
export const ZAP = '#25D366';
export const AMARELO_TEXTO = '#8A6A00';

// --- base ---------------------------------------------------------------------------------------

/** Área da tela entre o título e a legenda (POS.celular até a legenda): o conteúdo fica centralizado nela. */
export const AREA = {top: 600, altura: 870};

/** Cartão branco do painel, na margem de 90 px, entrando de baixo. Com `centro`, fica no meio da AREA
 * (o espaço acima e abaixo dele é o mesmo, seja qual for a altura do cartão). */
export const Painel: React.FC<{top?: number; centro?: boolean; inicio?: number; children: React.ReactNode; style?: React.CSSProperties; sai?: number}> = ({
  top = POS.celular, centro, inicio = 0, children, style, sai = 0,
}) => {
  const f = useCurrentFrame();
  const t = vai(f, inicio, inicio + 18);
  const cartao = (
    <div style={{position: centro ? 'relative' : 'absolute', ...(centro ? {} : {left: 90, right: 90, top}), background: C.branco, color: C.tinta, borderRadius: 40,
      padding: '34px 38px', fontFamily: FONTE, boxShadow: '0 30px 70px rgba(10,25,16,.22)', opacity: Math.min(1, t * 1.5) * (1 - sai),
      transform: `translateY(${(1 - t) * 90 - sai * 80}px) scale(${1 - sai * 0.05})`, ...style}}>
      {children}
    </div>
  );
  return centro ? <Centro>{cartao}</Centro> : cartao;
};

/** Centraliza o conteúdo na AREA. */
export const Centro: React.FC<{children: React.ReactNode}> = ({children}) => (
  <div style={{position: 'absolute', left: 90, right: 90, top: AREA.top, height: AREA.altura, display: 'flex', flexDirection: 'column', justifyContent: 'center'}}>{children}</div>
);

export const Rotulo: React.FC<{children: React.ReactNode; style?: React.CSSProperties}> = ({children, style}) => (
  <div style={{fontSize: 24, fontWeight: 800, letterSpacing: '.12em', textTransform: 'uppercase', color: AMARELO_TEXTO, ...style}}>{children}</div>
);

export const Selo: React.FC<{texto: React.ReactNode; tom: 'vermelho' | 'alerta' | 'ok' | 'cinza' | 'verde' | 'amarelo'; tamanho?: number; style?: React.CSSProperties}> = ({texto, tom, tamanho = 24, style}) => {
  const cores = {
    vermelho: [VERMELHO_SUAVE, VERMELHO], alerta: [ALERTA_SUAVE, ALERTA], ok: ['#E3F1E7', '#1F6B3E'], cinza: ['#EFEADB', C.cinza],
    verde: [C.verde, C.creme], amarelo: [C.amarelo, C.verde],
  }[tom];
  return <span style={{display: 'inline-flex', alignItems: 'center', gap: 8, background: cores[0], color: cores[1], fontSize: tamanho, fontWeight: 800, borderRadius: 999,
    padding: '6px 16px', whiteSpace: 'nowrap', ...style}}>{texto}</span>;
};

export const Barra: React.FC<{porcento: number; cor: string; altura?: number}> = ({porcento, cor, altura = 16}) => (
  <div style={{height: altura, borderRadius: 999, background: '#EDE8D9', overflow: 'hidden'}}>
    <div style={{width: `${Math.max(0, Math.min(100, porcento))}%`, height: '100%', borderRadius: 999, background: cor}} />
  </div>
);

const mil = (n: number) => Math.round(n).toLocaleString('pt-BR');
export const corDaLotacao = (p: number) => (p >= 100 ? VERMELHO : p >= 95 ? '#C98A00' : C.verde);

/** Círculo com a foto do grupo (as mesmas fotos de produto, recortadas). */
export const FotoGrupo: React.FC<{tamanho: number; foto?: string}> = ({tamanho, foto = 'bolsa'}) => (
  <Img src={produto(foto)} style={{width: tamanho, height: tamanho, borderRadius: '50%', objectFit: 'cover', flex: 'none', border: `3px solid ${C.amarelo}`}} />
);

// --- link de entrada -----------------------------------------------------------------------------

const SELOS = ['🔥 Ofertas todo dia', '🔇 Só admins enviam', '✅ Grátis'];

/** A página do link de entrada (modelo Clássico), desenhada na tela do celular (560 x 1120). */
export const PaginaEntrada: React.FC<{toque?: number}> = ({toque = 9999}) => {
  const f = useCurrentFrame();
  const aperto = f >= toque && f < toque + 8 ? 0.94 : 1;
  return (
    <div style={{position: 'absolute', inset: 0, background: C.creme, color: C.tinta, fontFamily: FONTE}}>
      <div style={{position: 'absolute', top: 64, left: 24, right: 24, height: 50, borderRadius: 25, background: '#E9E3D3', display: 'flex', alignItems: 'center', gap: 8,
        padding: '0 18px', fontSize: 17, color: C.cinza, whiteSpace: 'nowrap', overflow: 'hidden'}}>🔒 achadinhosdabia.appfiliado.com.br/grupo-vip/</div>
      <div style={{position: 'absolute', top: 160, left: 28, right: 28, background: C.branco, borderRadius: 40, padding: '44px 30px 34px', textAlign: 'center',
        boxShadow: '0 14px 30px rgba(23,48,31,.08)'}}>
        <div style={{display: 'flex', justifyContent: 'center'}}><FotoGrupo tamanho={150} /></div>
        <div style={{fontSize: 38, fontWeight: 800, lineHeight: 1.12, marginTop: 22, letterSpacing: '-.02em'}}>Grupo VIP de Achadinhos</div>
        <div style={{fontSize: 23, color: C.cinza, lineHeight: 1.35, marginTop: 12}}>Cupons e ofertas relâmpago da Shopee antes de todo mundo.</div>
        <div style={{display: 'flex', flexWrap: 'wrap', gap: 10, justifyContent: 'center', marginTop: 20}}>
          {SELOS.map((s) => <span key={s} style={{fontSize: 18, fontWeight: 800, background: '#FBE6EC', color: '#B0285A', borderRadius: 999, padding: '8px 14px'}}>{s}</span>)}
        </div>
        <div style={{marginTop: 28, background: ZAP, color: C.branco, borderRadius: 24, height: 88, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 14,
          fontSize: 29, fontWeight: 800, transform: `scale(${aperto})`, boxShadow: '0 10px 22px rgba(37,211,102,.35)'}}>
          <Icone nome="bot" tamanho={36} cor={C.branco} espessura={2.4} /> Quero entrar no grupo
        </div>
        <div style={{fontSize: 20, fontWeight: 800, marginTop: 22}}>Mais de 2.700 pessoas já estão nos grupos</div>
        <div style={{fontSize: 17, color: C.cinza, marginTop: 12}}>Grupo de ofertas no WhatsApp</div>
      </div>
    </div>
  );
};

/** O convite do grupo da vez, como o WhatsApp mostra depois do toque. */
export const ConviteGrupo: React.FC<{nome: string; membros: string; t?: number}> = ({nome, membros, t = 1}) => (
  <div style={{position: 'absolute', inset: 0, background: `rgba(14,23,18,${0.45 * t})`, color: C.tinta, fontFamily: FONTE, display: 'flex', flexDirection: 'column', justifyContent: 'flex-end'}}>
    <div style={{background: C.branco, borderRadius: '44px 44px 0 0', padding: '46px 34px 70px', textAlign: 'center', boxShadow: '0 -10px 30px rgba(0,0,0,.08)',
      transform: `translateY(${(1 - t) * 105}%)`}}>
      <div style={{width: 70, height: 8, borderRadius: 4, background: '#D9D2C0', margin: '0 auto 34px'}} />
      <div style={{display: 'flex', justifyContent: 'center'}}><FotoGrupo tamanho={150} /></div>
      <div style={{fontSize: 36, fontWeight: 800, marginTop: 22}}>{nome}</div>
      <div style={{fontSize: 22, color: C.cinza, marginTop: 8}}>Grupo · {membros}</div>
      <div style={{fontSize: 22, color: C.cinza, marginTop: 26}}>Você foi convidado para entrar neste grupo.</div>
      <div style={{marginTop: 30, background: ZAP, color: C.branco, borderRadius: 999, height: 80, display: 'grid', placeItems: 'center', fontSize: 28, fontWeight: 800}}>Entrar no grupo</div>
    </div>
  </div>
);

export type GrupoDoLink = {nome: string; de: number; ate: number; limite?: number};

/** Os grupos do link em ordem, enchendo: o primeiro que não está cheio é o "grupo da vez". */
export const GruposDoLink: React.FC<{grupos: GrupoDoLink[]; inicio: number; duracao: number; compacto?: boolean}> = ({grupos, inicio, duracao, compacto}) => {
  const f = useCurrentFrame();
  const membros = grupos.map((g) => Math.round(vai(f, inicio, inicio + duracao, g.de, g.ate, (t) => t)));
  const daVez = grupos.findIndex((g, i) => membros[i] < (g.limite ?? 1000));
  return (
    <div style={{display: 'grid', gap: compacto ? 14 : 18}}>
      {grupos.map((g, i) => {
        const limite = g.limite ?? 1000;
        const p = (membros[i] * 100) / limite;
        const cheio = membros[i] >= limite;
        const agora = i === daVez;
        return (
          <div key={g.nome} style={{display: 'flex', alignItems: 'center', gap: 20, padding: compacto ? '16px 20px' : '20px 24px', borderRadius: 26,
            background: agora ? '#E3F1E7' : '#FAF7EF', border: `3px solid ${agora ? C.ok : 'transparent'}`}}>
            <div style={{width: 46, height: 46, borderRadius: '50%', background: cheio ? VERMELHO : agora ? C.ok : '#D9D2C0', color: C.branco, display: 'grid', placeItems: 'center',
              fontSize: 22, fontWeight: 800, flex: 'none'}}>{cheio ? '✓' : i + 1}</div>
            <div style={{flex: 1, minWidth: 0}}>
              <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 10}}>
                <span style={{fontSize: compacto ? 28 : 31, fontWeight: 800, whiteSpace: 'nowrap'}}>{g.nome}</span>
                <span style={{fontSize: 24, color: C.cinza, fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap'}}>{mil(membros[i])} de {mil(limite)}</span>
              </div>
              <div style={{marginTop: 10}}><Barra porcento={p} cor={cheio ? VERMELHO : agora ? C.ok : '#C9C2AE'} altura={12} /></div>
            </div>
            <div style={{width: 150, textAlign: 'right', flex: 'none'}}>
              {cheio ? <Selo texto="Cheio" tom="vermelho" /> : agora ? <Selo texto="● Agora" tom="ok" /> : <Selo texto="Próximo" tom="cinza" />}
            </div>
          </div>
        );
      })}
    </div>
  );
};

// --- membros dos grupos ------------------------------------------------------------------------------

export type GrupoAcompanhado = {nome: string; de: number; ate: number; dia: string};

/** O painel de membros: os números de 24 h e 7 dias e os grupos com a lotação de cada um. */
export const Membros: React.FC<{grupos: GrupoAcompanhado[]; inicio: number; duracao?: number; aviso?: number}> = ({grupos, inicio, duracao = 70, aviso = 9999}) => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const lotando = grupos.filter((g) => g.ate * 100 / 1024 >= 95).length;
  const t = mola(f, aviso, fps, 13);
  return (
    <div>
      <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 14}}>
        {[['Membros', 5945, '', 'em 8 grupos'], ['24 horas', 56, '+', 'entraram 112'], ['7 dias', 388, '+', 'ganho de membros']].map(([r, v, sinal, sub], k) => (
          <div key={r as string} style={{background: '#FAF7EF', borderRadius: 22, padding: '16px 18px'}}>
            <div style={{fontSize: 21, color: C.cinza}}>{r}</div>
            <div style={{fontSize: 40, fontWeight: 800, color: sinal ? '#1F6B3E' : C.tinta, fontVariantNumeric: 'tabular-nums'}}>
              {sinal}{mil(vai(f, inicio + k * 4, inicio + k * 4 + 40, 0, v as number))}
            </div>
            <div style={{fontSize: 18, color: C.cinza}}>{sub}</div>
          </div>
        ))}
      </div>
      <div style={{marginTop: 22, display: 'grid', gap: 4}}>
        {grupos.map((g, i) => {
          const m = vai(f, inicio + 6 + i * 3, inicio + 6 + i * 3 + duracao, g.de, g.ate);
          const p = (m * 100) / 1024;
          return (
            <div key={g.nome} style={{display: 'grid', gridTemplateColumns: '1fr 120px 92px', alignItems: 'center', gap: 16, padding: '15px 4px', borderTop: i ? `2px solid ${C.borda}` : 'none'}}>
              <div style={{minWidth: 0}}>
                <div style={{fontSize: 29, fontWeight: 800, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis'}}>{g.nome}</div>
                <div style={{marginTop: 8}}><Barra porcento={p} cor={corDaLotacao(p)} altura={11} /></div>
              </div>
              <div style={{textAlign: 'right'}}>
                <div style={{fontSize: 29, fontWeight: 800, fontVariantNumeric: 'tabular-nums'}}>{mil(m)}</div>
                <div style={{fontSize: 19, color: p >= 95 ? corDaLotacao(p) : C.cinza, fontWeight: 800}}>{Math.floor(p)}% cheio</div>
              </div>
              <div style={{textAlign: 'right', fontSize: 25, fontWeight: 800, color: '#1F6B3E'}}>{g.dia}</div>
            </div>
          );
        })}
      </div>
      <div style={{marginTop: 18, background: ALERTA_SUAVE, color: ALERTA, borderRadius: 22, padding: '18px 22px', fontSize: 25, fontWeight: 800, lineHeight: 1.3,
        opacity: f >= aviso ? Math.min(1, t * 1.4) : 0, transform: `translateY(${(1 - t) * 20}px)`}}>
        ⚠️ {lotando} grupos com mais de 95% da lotação: vale abrir o próximo.
      </div>
    </div>
  );
};

// --- criar o próximo grupo ------------------------------------------------------------------------

const PASSOS_DO_GRUPO = ['Mesma foto e descrição do último', 'Só administradores enviam', 'Sub ID próprio: achadinhos4', 'Já na sua Automação', 'Link de convite pronto', 'Entrou no link de entrada'];

/** O próximo grupo sendo criado: cada passo marca na hora em que fica pronto. */
export const CriandoGrupo: React.FC<{inicio: number; intervalo?: number; passos?: string[]}> = ({inicio, intervalo = 20, passos = PASSOS_DO_GRUPO}) => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const pronto = f >= inicio + passos.length * intervalo;
  return (
    <div>
      <div style={{display: 'flex', alignItems: 'center', gap: 22}}>
        <FotoGrupo tamanho={96} />
        <div style={{flex: 1}}>
          <div style={{fontSize: 36, fontWeight: 800}}>Achadinhos da Bia #4</div>
          <div style={{fontSize: 23, color: C.cinza, marginTop: 4}}>{pronto ? 'Pronto e já recebendo gente' : 'Criando o próximo grupo…'}</div>
        </div>
        <Selo texto={pronto ? '✓ Pronto' : 'Criando'} tom={pronto ? 'ok' : 'amarelo'} tamanho={26} />
      </div>
      <div style={{marginTop: 24, display: 'grid', gap: 2}}>
        {passos.map((p, i) => {
          const t = mola(f, inicio + i * intervalo, fps, 12);
          const feito = f >= inicio + i * intervalo;
          return (
            <div key={p} style={{display: 'flex', alignItems: 'center', gap: 18, padding: '14px 0', borderTop: `2px solid ${C.borda}`, fontSize: 30, fontWeight: 800,
              color: feito ? C.tinta : '#B9B19C'}}>
              <span style={{width: 44, height: 44, borderRadius: '50%', background: feito ? C.ok : '#EDE8D9', color: C.branco, display: 'grid', placeItems: 'center', fontSize: 24, flex: 'none',
                transform: `scale(${feito ? 0.7 + 0.3 * t : 1})`}}>{feito ? '✓' : ''}</span>
              {p}
            </div>
          );
        })}
      </div>
    </div>
  );
};

/** O e-mail que chega avisando do grupo novo. */
export const AvisoEmail: React.FC<{inicio: number; top: number; texto: string}> = ({inicio, top, texto}) => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  if (f < inicio) return null;
  const t = mola(f, inicio, fps, 14);
  return (
    <div style={{position: 'absolute', left: 130, right: 130, top, background: C.verde, color: C.creme, borderRadius: 30, padding: '22px 26px', display: 'flex', gap: 18,
      alignItems: 'center', fontFamily: FONTE, boxShadow: '0 24px 50px rgba(10,25,16,.35)', opacity: Math.min(1, t * 1.4), transform: `translateY(${(1 - t) * -50}px) scale(${0.92 + 0.08 * t})`}}>
      <span style={{width: 60, height: 60, borderRadius: 18, background: C.amarelo, display: 'grid', placeItems: 'center', fontSize: 32, flex: 'none'}}>✉️</span>
      <div>
        <div style={{fontSize: 20, fontWeight: 800, color: C.amarelo, letterSpacing: '.08em', textTransform: 'uppercase'}}>E-mail do Appfiliado · agora</div>
        <div style={{fontSize: 25, fontWeight: 800, lineHeight: 1.25, marginTop: 4}}>{texto}</div>
      </div>
    </div>
  );
};

export {Interruptor};
