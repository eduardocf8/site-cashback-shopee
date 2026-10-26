# Instagram dos afiliados (Estúdio Instagram › Automações)

O afiliado conecta o Instagram dele pelo **Login do Instagram para empresas** e cria automações de
resposta, no estilo do ManyChat. Está **em teste**: só aparece para a conta com "testa o Estúdio
Instagram" marcado no admin (Contas do Appfiliado). As automações são do plano **Premium**.

## O que faz

| Quando | O que sai |
|---|---|
| Alguém **comenta** num post (um post escolhido ou todos), com uma das palavras (ou qualquer texto) | Resposta pública no comentário (sorteada entre as opções, `{nome}` marca a pessoa) e/ou a mensagem no direto com o link |
| Alguém **responde um story** (um story no ar ou todos) | Mensagem no direto |
| Alguém **manda mensagem no direto** com uma das palavras (obrigatório ter palavra) | Mensagem no direto |

Regras: cada pessoa recebe uma vez por automação; aviso repetido da Meta não responde de novo; a
própria conta e resposta dentro de outro comentário ficam de fora; até 150 respostas por hora por
conta. O histórico ("Quem recebeu") mostra o que saiu e os erros do Instagram.

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
  resposta a story e direto dependem de `instagram_business_manage_messages`.
- A mensagem ligada a um comentário vale uma vez por comentário e até 7 dias depois dele. A mensagem
  no direto só pode ir até 24 horas depois que a pessoa escreveu ou respondeu o story.
- A conta precisa ser pública para receber avisos de comentário.
