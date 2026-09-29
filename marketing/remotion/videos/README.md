# Vídeos renderizados

Os dois arquivos prontos da apresentação, versionados aqui para poderem ser baixados
sem precisar rodar o render.

| Arquivo | Duração | O que é |
|---|---|---|
| `apresentacao-calma.mp4` | 18,3s | Corte seco entre cenas, quadro parado, números prontos |
| `apresentacao-dinamica.mp4` | 15,8s | As cenas se empurram, o fundo dá zoom lento, os números contam |

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
