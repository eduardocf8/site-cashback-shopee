# Vídeos renderizados

Os dois arquivos prontos da apresentação, versionados aqui para poderem ser baixados
sem precisar rodar o render.

| Arquivo | Duração | O que é |
|---|---|---|
| `apresentacao-calma.mp4` | 18,3s | Corte seco entre cenas, quadro parado, números prontos |
| `apresentacao-dinamica.mp4` | 15,8s | As cenas se empurram, o fundo dá zoom lento, os números contam |
| `apresentacao-espera-animada.mp4` | 20,5s | A versão com mais movimento: seis transições, a moeda da marca em voo, números que contam e rolam |
| `apresentacao-calma-gancho-espera.mp4` | 18,4s | A calma com outro gancho em dois tempos: a pergunta "Vai comprar na Shopee?" e, 0,9s depois, "Espera." grande |
| `campanha-10-10-a-objetos.mp4` | 18,0s | Reel da campanha 10.10 (50% a mais de cashback), versão A: calendário, letreiro, recibo e relógio sobre cores chapadas |
| `campanha-10-10-b-gravacao-de-tela.mp4` | 18,0s | O mesmo reel, versão B: gravação de tela de app, com uma rolagem contínua e um dedo que toca |

Todos em 1080×1920, 30fps, H.264. As legendas dos reels da campanha estão em `legenda-campanha-10-10-a.txt` e `legenda-campanha-10-10-b.txt` (os números batem com `dados.json`; conferir de novo se a campanha mudar). Os dois reels da campanha 10.10 são sem música: ela é colocada no editor. Para renderizar de novo (rode antes `python3 exportar_dados_campanha.py`): `npm run render:campanha` e `npm run render:campanha-b`.

**Estes arquivos são saída, não fonte.** Quem manda é `../src/`: mexer no MP4 faz o
ajuste sumir no próximo render. Para gerar de novo:

```bash
cd marketing/remotion
npm run render            # calma
npm run render:dinamica   # dinâmica
```

O render escreve em `../saida/`, que fica fora do git justamente para os arquivos de
trabalho não entrarem no histórico. Esta pasta é só para as versões que valem a pena
guardar — copie para cá quando uma delas for a boa, em vez de versionar todo render.

## Sincronia da versão animada com a música

A versão `apresentacao-espera-animada.mp4` foi montada para uma música específica, de
**111,32 BPM** (uma batida a cada **0,539s = 16,17 quadros**). A música não está no
repositório (direitos), então o que fica aqui é a análise, para o vídeo poder ser
refeito ou reencaixado.

**Como usar no CapCut:** coloque a música no quadro 0 do vídeo, sem cortar o início. O
vídeo tem 20,5s; a música tem mais, então basta terminá-la com fade de uns 0,7s
a partir de 19,8s (o último quadro é a batida 37).

O que a análise da música mostrou:

- **Grade de batidas:** a batida `k` cai em `0,575s + 0,539s × k`. A grade bate nos dois
  trechos da música com 8ms de diferença, então é confiável.
- **O drop:** a música tem uma pausa real de 0,39s (silêncio digital de 10,23s a 10,62s)
  e volta forte na **batida 19, em 10,82s (quadro 325)**. É onde as portas se abrem.
- **Dois trechos com o mesmo andamento:** um groove mais leve até 10,2s e um trecho cheio
  depois do drop.

O que foi refeito em relação à versão anterior: toda transição passou a durar **uma
batida (16 quadros)** e a começar numa batida, e cada cena foi dimensionada para que o
primeiro movimento da seguinte caia na batida em que a transição termina. A versão anterior
tinha eventos a até 4 quadros (130ms) da batida, o que se ouve como "quase". Agora os golpes
principais caem a 1 quadro ou menos.

Como a grade tem 16,17 quadros por batida, não dá para todos os eventos caírem em quadro
inteiro exato; o erro máximo de arredondamento é meio quadro (17ms).

A tabela usa a batida mais próxima (inteira, ou meia-batida quando o evento cai numa
colcheia). O efeito sonoro é sugestão, não parte do arquivo: o vídeo sai sem áudio de
propósito, para a narração e o som ficarem no editor.

| Tempo | Quadro | Batida | Cena | O que acontece | Efeito sonoro sugerido |
|---|---|---|---|---|---|
| 1,10s | 33 | 1 | Gancho | "Espera." entra de uma vez, com a rajada de raios | impacto grave; é o momento da fala "espera" |
| 2,20s | 66 | 3 | Transição 1 | íris abre do centro (1 batida) | whoosh curto |
| 3,00s | 90 | 4.5 | Frase | o grifo abre atrás de "cash-b," | marca de caneta / swipe leve |
| 3,27s | 98 | 5 | Frase | "parte do dinheiro" sobe | leve, sem destaque |
| 4,33s | 130 | 7 | Frase | "dinheiro" vira a moeda | pop / moeda surgindo |
| 4,60s | 138 | 7.5 | Frase | a moeda sai voando (parte) | whoosh subindo + brilho |
| 5,43s | 163 | 9 | Frase | a moeda volta de baixo (volta) | whoosh descendo |
| 5,97s | 179 | 10 | Frase | a moeda pousa e "volta" aparece | moeda caindo / ding: o pouso |
| 6,50s | 195 | 11 | Transição 2 | empurrão para cima (1 batida) | whoosh grave |
| 6,77s | 203 | 11.5 | Mínimo | "1%" aparece | pop |
| 8,40s | 252 | 14.5 | Mínimo | "mínimo" dá a volta e sobe | whoosh curto |
| 9,20s | 276 | 16 | Mínimo | o número abre e o "6" começa a rolar | roleta / cliques rápidos até parar no 6 |
| 10,83s | 325 | 19 | Transição 3 | as portas se abrem NO DROP | o golpe principal da música; whoosh largo em duas metades |
| 11,10s | 333 | 19.5 | Bem mais | "Muitas vezes," sobe | leve |
| 11,63s | 349 | 20.5 | Bem mais | "bem mais" chega | impacto |
| 11,90s | 357 | 21 | Bem mais | as barras sobem, uma por colcheia | cinco notas subindo |
| 12,97s | 389 | 23 | Transição 4 | círculo claro sobe de baixo (1 batida) | whoosh + brilho |
| 13,50s | 405 | 24 | Saque | o número começa a contar | contador rápido |
| 14,57s | 437 | 26 | Saque | a marca de verificação aparece | ding de confirmação |
| 15,13s | 454 | 27 | Transição 5 | empurrão para o lado (1 batida) | whoosh lateral |
| 15,40s | 462 | 27.5 | Sem taxa | primeira marca de verificação | tick |
| 15,93s | 478 | 28.5 | Sem taxa | segunda marca de verificação | tick |
| 16,73s | 502 | 30 | Transição 6 | varredura em ponteiro (1 batida) | tique-taque / whoosh circular |
| 17,27s | 518 | 31 | Fechamento | "acesse / cash-b.com" assenta | suave |
| 18,33s | 550 | 33 | Fechamento | ".com" some e "cash-b" cresce | crescendo até o impacto |
| 20,50s | 615 | 37 | Fim | último quadro, na batida 37 | a música faz fade aqui |
