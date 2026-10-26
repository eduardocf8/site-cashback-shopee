# Instagram dos afiliados (Automações do Instagram e publicação do Estúdio)

O afiliado conecta o Instagram dele pelo **Login do Instagram para empresas** e cria automações de
resposta, no estilo do ManyChat. As Automações são um módulo próprio (`instagram` e
`instagram_premium`): o Standard responde comentários, com até 5 automações ligadas; o Premium
também responde stories e DMs, não tem limite de ligadas, manda o link num botão (modelo de botão da
API; se o Instagram recusar, vai o link no texto) e gera o link com um Sub ID por automação
(`link_afiliado`, pelo conversor do painel). Limites em `licencas/planos.py` (`AUTOMACOES`). Até o
lançamento (`APPFILIADO_LANCAMENTO_INSTAGRAM`), só aparece para a conta com "testa o Estúdio
Instagram" marcado no admin (Contas do Appfiliado).

## O que faz

| Quando | O que sai |
|---|---|
| Alguém **comenta** num post (um post escolhido ou todos), com uma das palavras (ou qualquer texto) | Resposta pública no comentário (sorteada entre as opções, `{nome}` marca a pessoa) e/ou a DM com o link |
| Alguém **responde um story** (um story no ar ou todos) | DM |
| Alguém **manda uma DM** com uma das palavras (obrigatório ter palavra) | DM |

Regras: cada pessoa recebe uma vez por automação; aviso repetido da Meta não responde de novo; a
própria conta e resposta dentro de outro comentário ficam de fora. Sem limite por mês. O Instagram
aceita 750 DMs de resposta a comentário por hora em cada conta: passando de 600 na hora, as respostas
entram na fila (`Disparo.na_fila`) e o worker manda na hora seguinte, em ordem (`webhook.enviar_fila`),
dentro do prazo do Instagram (7 dias depois do comentário, 24 horas depois da DM). O histórico
("Quem recebeu") mostra o que saiu, o que está na fila e os erros do Instagram.

No editor de um post do Estúdio, "Criar automação" já abre com o nome e o link de afiliado do produto.

## Onde está cada coisa

| Arquivo | O que faz |
|---|---|
| `models.py` | `ContaInstagram` (token cifrado com `painel/cripto.py`), `Automacao`, `Disparo` |
| `api.py` | Chamadas a `graph.instagram.com` (v26.0): login, token de 60 dias, avisos, posts, respostas |
| `conexao.py` | Conectar, renovar o token (worker do painel, `sincronizar_painel`), desconectar, `signed_request` |
| `webhook.py` | Os avisos da Meta das contas dos afiliados |
| `painel/views_instagram.py` | As telas e os endereços que a Meta chama |

O webhook é **um só** para o app da Meta: `https://cash-b.com/instagram/automacao/webhook/`
(`automacao_instagram/views.webhook_instagram`). Ele separa primeiro os avisos das contas conectadas
aqui (pelo `entry.id`) e o resto segue para a automação da cash-b.

## Configuração no app da Meta (uma vez)

1. **Instagram › Configuração da API com login do Instagram › Configurar login comercial do Instagram:**
   - URL de redirecionamento OAuth: `https://app.appfiliado.com.br/estudio/instagram/retorno/`
   - URL de retorno de chamada para cancelar autorização: `https://app.appfiliado.com.br/instagram/desautorizar/`
   - URL de solicitação de exclusão de dados: `https://app.appfiliado.com.br/instagram/apagar-dados/`
2. **Webhooks** (mesma tela): o endereço acima, com o `INSTAGRAM_WEBHOOK_VERIFY_TOKEN`, e os campos
   `comments` e `messages` assinados.
3. **Variáveis no Render:** o ID e o segredo do app do Instagram já estão em `INSTAGRAM_APP_ID` e
   `INSTAGRAM_APP_SECRET`. Se o login do Instagram usar outro par, defina
   `APPFILIADO_INSTAGRAM_APP_ID` e `APPFILIADO_INSTAGRAM_APP_SECRET`.

## Limites da Meta (importante)

- **Contas de clientes exigem Acesso Avançado em todas as permissões**, inclusive
  `instagram_business_basic`. Com Acesso Padrão, só funciona para contas que você administra e que
  têm função no app (a sua, por exemplo).
- **Avisos de comentário só chegam com Acesso Avançado de `instagram_business_manage_comments`**
  (documentação de webhooks, out/2026). Até a aprovação, a automação de comentário fica parada;
  resposta a story e DM dependem de `instagram_business_manage_messages`.
- A DM ligada a um comentário vale uma vez por comentário e até 7 dias depois dele. As outras DMs
  só podem ir até 24 horas depois que a pessoa escreveu ou respondeu o story.
- A conta precisa ser pública para receber avisos de comentário.

## Publicar no Instagram (todos os planos do Estúdio)

- No editor, "Publicar no Instagram" salva o post, desenha cada slide em JPEG de 1080 px no navegador
  e manda para `estudio/<pk>/publicar/`, para publicar agora ou num horário marcado (até 60 dias).
- Post 1:1 ou 4:5 vai para o feed: uma imagem ou carrossel (até 10), com a legenda do editor.
  Post 9:16 vira stories, um por slide, sem legenda (a API não coloca adesivo de link).
- `publicar.py`: a fila. Uma thread do worker (`sincronizar_painel --loop`) confere a cada 15 s,
  pega cada publicação com um update atômico e chama a API: container por imagem → espera o
  `status_code` → `media_publish`. Nos stories, guarda cada um que saiu: numa nova tentativa, não repete.
- A Meta baixa as imagens por `/instagram/midia/<token>.jpg` (sem login, token secreto). O endereço
  só responde enquanto a publicação não saiu; depois as imagens são apagadas do banco.
- Telas: a janela de publicar no editor e `estudio/publicacoes/` (agendadas, publicadas, cancelar,
  tentar de novo). O selo do post no Estúdio (agendado, publicado, erro) segue a última publicação.
