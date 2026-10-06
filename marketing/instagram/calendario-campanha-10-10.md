# Calendário da campanha 10.10 (50% a mais de cashback)

De sábado 3/10 a domingo 11/10. A campanha vale no **sábado, 10/10, das 0h às 23h59** (horário de
Brasília).

**Os horários são uma sugestão geral**, não vêm dos dados do perfil: almoço (12h) e começo da noite
(19h–20h30) costumam ser as melhores janelas no Brasil. Confira no Instagram em Insights >
"Quando seus seguidores estão online" e troque pelos horários em que o seu público está de fato.
Feed e reels dá para agendar no Meta Business Suite; stories também.

## Antes de tudo (você)

1. No Shell do Render: `python manage.py simular_campanha --multiplicador 1.5 --dias 60`
   (confirma a margem com pedidos reais antes de anunciar).
2. No admin, "Campanhas de cashback": multiplicador `1.5`, início `10/10/2026 00:00`, fim
   `10/10/2026 23:59:59`. A faixa do site liga sozinha 3 dias antes (madrugada de 7/10).
3. Conferir que o último deploy do Render tem a faixa e o e-mail com banner.

## Dia a dia

| Dia | Horário | O que posta | Arquivo |
|---|---|---|---|
| **Sáb 3** | 19h | Story seu, falando: "sábado que vem, dia 10/10, 50% a mais de cashback em todo pedido na Shopee pelo nosso site". Sem figurinha de contagem ainda | roteiro na conversa |
| **Dom 4** | — | Descanso. Se ainda não postou, o carrossel 11 (datas duplas) pode entrar aqui, às 12h | `carrossel-11-datas-duplas/` |
| **Seg 5** | — | Carrossel não foi postado hoje: passa para terça às 12h | — |
| **Ter 6** | 10h | **Verificações sem exposição** (nada fica visível para o público): no Shell do Render, o teste das bordas da campanha e o `simular_campanha`; no admin, conferir a campanha cadastrada; e a **prévia do administrador** em `/previa-campanha/` (só você vê). Ver "Como testar sem expor a campanha" abaixo | — |
| Ter 6 | 12h | **Feed: carrossel 12** (a explicação completa). Compartilhe no story às 12h30 | `carrossel-12-10-10/` + `legenda.txt` |
| **Qua 7** | de manhã | Abrir o site e conferir que a **faixa** apareceu ("Dia 10.10: 50% a mais de cashback..."). É o aviso de 3 dias, previsto; os cards ainda mostram o valor normal | — |
| Qua 7 | 12h | **Story 1, teaser "vem aí"**, com a **figurinha de contagem regressiva** para 10/10 | `stories-10-10/story-01-teaser.png` |
| Qua 7 | 19h | **Reel A** (objetos: calendário, letreiro, recibo, relógio) | `remotion/videos/campanha-10-10-a-objetos.mp4` + `legenda-campanha-10-10-a.txt` |
| **Qui 8** | 12h | **Story 2, "faltam 2 dias"** (1,6% → 2,4% e 1% → 1,5%). Só vale postado neste dia | `stories-10-10/story-02-faltam-2-dias.png` |
| Qui 8 | 19h | **Story "antes → agora"** (Kit Peseira: R$ 4,05 → R$ 6,08) | `cards-antes-agora/story-antes-agora.png` |
| **Sex 9** | 12h | **Reel B** (gravação de tela, abre com "na Shopee?") | `remotion/videos/campanha-10-10-b-gravacao-de-tela.mp4` + `legenda-campanha-10-10-b.txt` |
| Sex 9 | à noite | **Anúncio pago no ar (a decidir):** arte nova como segundo anúncio, sem mexer na campanha que converte | — |
| Sex 9 | 20h | Story seu, curto: "amanhã é o dia". Ainda não existe arte de "amanhã" (ver abaixo) | — |
| **Sáb 10** | 00h05 | **Conferência ao vivo:** campanha no ar. Abrir o site e conferir a faixa ("no 10/10") e os cards (Kit Peseira 8,7% / R$ 6,08). Se algo estiver errado, editar ou apagar a campanha no admin: vale na hora, sem deploy | — |
| Sáb 10 | 8h30 | **E-mail** da campanha (banner `banner-10-10-completo.png`, Corpo curto, tipo "Anúncio/promoção", filtro "e-mail verificado") | `banner-email/` |
| Sáb 10 | de manhã | **Push (a decidir):** ainda não verifiquei se o push tem envio em massa | — |
| Sáb 10 | 9h | **Story 3, "hoje"** | `stories-10-10/story-03-hoje.png` |
| Sáb 10 | 20h30 | **Story 4, "últimas horas"** | `stories-10-10/story-04-ultimas-horas.png` |
| **Dom 11** | 12h | Story seu: obrigado, e lembrar que o cashback fica pendente até a Shopee validar a compra | — |

## Como testar sem expor a campanha

A campanha não pode ficar visível para o público antes do dia 10, então **não há teste com
campanha de teste ativa no site**. O que dá para provar antes, sem expor nada:

1. **Lógica de datas (Shell do Render):** as bordas do dia 10 (23h59 do dia 9, 0h e 23h59:59 do dia 10,
   0h do dia 11) e quando a faixa liga (madrugada do dia 7). Só leitura, ninguém vê.
2. **Margem (Shell do Render):** `python manage.py simular_campanha --multiplicador 1.5 --dias 60`.
3. **Código:** os testes automáticos de campanha, faixa, simulação e carimbo do pedido (38 testes),
   todos passando na versão atual.
4. **Prévia do administrador (só você):** logado como superusuário, abra `/previa-campanha/` e ligue a
   prévia por 2 horas. Aí, no seu navegador, a home, as ofertas, o painel e o cadastro aparecem com a
   campanha no ar (faixa e cards; um aviso vermelho lembra que é prévia). Qualquer outra pessoa,
   inclusive outro usuário logado, enxerga o site normal; para quem não é superusuário a tela
   responde 404. Não grava nada e não muda o cashback pago.
5. **A faixa de aviso (dia 7)** é o único trecho que o público vê antes do dia 10, e é a regra
   combinada de 3 dias antes.
6. **O teste de verdade é no dia 10, às 00h05**, com a campanha no ar de propósito. Reversível na
   hora no admin, sem deploy.
7. **Pedido carimbado:** conferir no dia 11, depois da sincronização das 3h, que os pedidos de 10/10
   têm multiplicador `1.50` e os de 9/10 às 23h59 e de 11/10 às 00h têm `1.00`.

## Observações

- **Reels A e B** dizem a mesma coisa de formas bem diferentes: o espaço de 2 dias entre eles (A na quarta,
  B na sexta) evita repetição.
- **Contagem regressiva:** a figurinha do Instagram vai no teaser (qua 7). Quem toca nela recebe o
  lembrete no dia.
- **E-mail:** uma vez só, no dia, às 8h30. Alternativa: sexta às 19h, avisando de véspera. Mandar
  nos dois cansa quem está na lista.
- **Story de sexta ("amanhã"):** ainda não existe arte. Dá para fazer falando, ou pedir uma peça
  nova.
- **Push e anúncio pago:** estavam no plano de 2/10 e ficam marcados como "a decidir".
- **Nada de "hoje" nos posts de feed e reels:** eles ficam no perfil depois do dia 10.
- **Só publicar os stories 3 e 4 com a campanha cadastrada no admin.**
