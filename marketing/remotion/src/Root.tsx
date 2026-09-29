import React from 'react';
import {Composition} from 'remotion';
import {Apresentacao} from './Apresentacao';
import {DURACAO, FPS} from './constantes';

export const RemotionRoot: React.FC = () => (
  <Composition
    id="Apresentacao"
    component={Apresentacao}
    durationInFrames={DURACAO}
    fps={FPS}
    width={1080}
    height={1920}
  />
);
