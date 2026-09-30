import React from 'react';
import {CenaGancho} from './cenas';

/** O primeiro quadro sozinho, para avaliar o efeito de "Espera." antes de juntar ao vídeo.
 * 78 frames: a pergunta, a pausa, a chegada e um segundo de pausa para ver o efeito
 * assentar. Não tem a transição de saída. */
export const DURACAO_GANCHO_TESTE = 78;

export const GanchoExplosaoA: React.FC = () => (
  <CenaGancho dur={DURACAO_GANCHO_TESTE} efeito="explosaoA" />
);

export const GanchoExplosaoB: React.FC = () => (
  <CenaGancho dur={DURACAO_GANCHO_TESTE} efeito="explosaoB" />
);
