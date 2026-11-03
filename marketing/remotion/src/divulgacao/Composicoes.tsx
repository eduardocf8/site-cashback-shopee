/** Os vídeos de divulgação do Appfiliado (9:16): 4 temas, de 2 a 3 versões cada. Cada tema vive no
 * seu arquivo e exporta o componente e a duração de cada versão. */
import React from 'react';
import {Composition} from 'remotion';
import {BotAntesDepois, BotCampanha, BotUmDia, DURACAO_BOT_ANTES_DEPOIS, DURACAO_BOT_CAMPANHA, DURACAO_BOT_UM_DIA} from './bot';
import {ALTURA, FPS, LARGURA} from './comum';
import {ConversorColeEConverta, DURACAO_CONVERSOR, DURACAO_RADAR, RadarAcheOProduto} from './ferramentas';
import {DURACAO_RESULTADOS_FALTA, DURACAO_RESULTADOS_GRUPO, ResultadosQualGrupo, ResultadosQuantoFalta} from './resultados';
import {DURACAO_SITE_MONTE, DURACAO_SITE_STORY, SiteDoStoryAoClique, SiteMonteOSeu} from './site';

const VIDEOS: {id: string; componente: React.FC; duracao: number}[] = [
  {id: 'Bot-AntesDepois', componente: BotAntesDepois, duracao: DURACAO_BOT_ANTES_DEPOIS},
  {id: 'Bot-UmDiaNoAutomatico', componente: BotUmDia, duracao: DURACAO_BOT_UM_DIA},
  {id: 'Bot-DatasDaShopee', componente: BotCampanha, duracao: DURACAO_BOT_CAMPANHA},
  {id: 'Site-MonteOSeu', componente: SiteMonteOSeu, duracao: DURACAO_SITE_MONTE},
  {id: 'Site-DoStoryAoClique', componente: SiteDoStoryAoClique, duracao: DURACAO_SITE_STORY},
  {id: 'Resultados-QuantoFalta', componente: ResultadosQuantoFalta, duracao: DURACAO_RESULTADOS_FALTA},
  {id: 'Resultados-QualGrupoVende', componente: ResultadosQualGrupo, duracao: DURACAO_RESULTADOS_GRUPO},
  {id: 'Radar-AcheOProduto', componente: RadarAcheOProduto, duracao: DURACAO_RADAR},
  {id: 'Conversor-ColeEConverta', componente: ConversorColeEConverta, duracao: DURACAO_CONVERSOR},
];

export const ComposicoesDivulgacao: React.FC = () => (
  <>
    {VIDEOS.map((v) => (
      <Composition key={v.id} id={v.id} component={v.componente} durationInFrames={v.duracao} fps={FPS} width={LARGURA} height={ALTURA} />
    ))}
  </>
);
