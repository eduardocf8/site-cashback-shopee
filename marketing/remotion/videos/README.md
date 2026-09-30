# Vídeos renderizados

Os dois arquivos prontos da apresentação, versionados aqui para poderem ser baixados
sem precisar rodar o render.

| Arquivo | Duração | O que é |
|---|---|---|
| `apresentacao-calma.mp4` | 18,3s | Corte seco entre cenas, quadro parado, números prontos |
| `apresentacao-dinamica.mp4` | 15,8s | As cenas se empurram, o fundo dá zoom lento, os números contam |
| `apresentacao-espera-animada.mp4` | 20,4s | A versão com mais movimento: seis transições, a moeda da marca em voo, números que contam e rolam |
| `apresentacao-calma-gancho-espera.mp4` | 18,4s | A calma com outro gancho em dois tempos: a pergunta "Vai comprar na Shopee?" e, 0,9s depois, "Espera." grande |

Ambos em 1080×1920, 30fps, H.264.

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

## Marcadores de tempo da versão animada

Para encaixar efeito sonoro e narração no CapCut. Os tempos saem da mesma tabela que
monta o vídeo (`src/animada/EsperaAnimada.tsx`), a 30 fps; o vídeo tem 20,40s (612
quadros).

| Tempo | Quadro | Cena | O que acontece | Efeito sonoro sugerido |
|---|---|---|---|---|
| 1,10s | 33 | Gancho | "Espera." chega (a batida) | impacto grave; é o momento da fala "espera" |
| 1,93s | 58 | Transição 1 | íris abre do centro | whoosh curto |
| 2,73s | 82 | Frase | o grifo abre atrás de "cash-b," | marca de caneta / swipe leve |
| 2,93s | 88 | Frase | a moeda sai de "cash-b," (parte) | whoosh subindo + brilho |
| 4,00s | 120 | Frase | a moeda volta de baixo (volta) | whoosh descendo |
| 4,87s | 146 | Frase | a moeda pousa e "volta" aparece | moeda caindo / ding: o pouso |
| 5,47s | 164 | Transição 2 | empurrão para cima | whoosh grave |
| 5,67s | 170 | Mínimo | "1%" aparece | pop |
| 7,27s | 218 | Mínimo | "mínimo" dá a volta e sobe | whoosh curto |
| 8,27s | 248 | Mínimo | o número abre e o "6" rola | roleta / cliques rápidos até parar no 6 |
| 9,93s | 298 | Transição 3 | as portas se abrem | whoosh largo, duas metades |
| 10,67s | 320 | Bem mais | "bem mais" chega | impacto |
| 10,93s | 328 | Bem mais | as barras sobem em degraus | cinco notas subindo |
| 12,27s | 368 | Transição 4 | círculo claro sobe de baixo | whoosh + brilho |
| 12,73s | 382 | Saque | o número começa a contar | contador rápido |
| 13,80s | 414 | Saque | a marca de verificação aparece | ding de confirmação |
| 14,73s | 442 | Transição 5 | empurrão para o lado | whoosh lateral |
| 15,00s | 450 | Sem taxa | primeira marca de verificação | tick |
| 15,40s | 462 | Sem taxa | segunda marca de verificação | tick |
| 16,27s | 488 | Transição 6 | varredura em ponteiro | tique-taque / whoosh circular |
| 17,87s | 536 | Fechamento | ".com" some e "cash-b" cresce | crescendo até o impacto |
| 18,20s | 546 | Fechamento | as moedas estouram | impacto + moedas caindo |

O efeito sonoro é sugestão, não parte do arquivo: o vídeo sai sem áudio de propósito, para
a narração e o som ficarem no editor.
