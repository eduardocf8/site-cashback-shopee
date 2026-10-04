# Assistente de dúvidas gerais (cérebro do futuro bot de WhatsApp)

Este app é a parte que **chama a IA**, isolada do resto. O bot de WhatsApp (webhook,
worker, conversas no admin) ainda não existe; quando existir, ele só vai usar
`assistente.ia.responder()` e não vai saber qual empresa ou modelo está por trás.

Escopo decidido: só **dúvidas gerais** (como funciona, prazos, saque via Pix, "é
confiável?", campanhas). Nada de consultar a conta da pessoa: perguntas sobre pedido,
saldo ou saque vão para uma pessoa da equipe.

## Por que foi feito assim

- **A IA fica atrás de uma interface própria** (`ia.py`): trocar de modelo é mudar
  `ASSISTENTE_IA_MODELO` no `.env`; trocar de empresa (OpenAI, Google...) é escrever um
  provedor novo em `provedores/` e registrá-lo em `PROVEDORES`, sem mexer no bot.
- **Os números nunca são digitados no prompt.** A base de conhecimento é o texto das
  páginas públicas do site, renderizado pelas mesmas views que o site usa
  (`base_conhecimento.py`). Os pisos de cashback, o saque mínimo e o "até X%" chegam
  pelo mesmo contexto que preenche a página, então o assistente nunca contradiz o site.
  A campanha vem de `CampanhaCashback.para_faixa()`, a mesma regra da faixa do site.
- **As regras de voz vêm do `VOZ.md`**, lidas na hora (`instrucoes.py`): uma regra nova
  confirmada lá passa a valer para o assistente sem copiar nada.
- **A base inteira cabe no prompt** (cerca de 8 mil tokens), sem banco vetorial. Ela vai
  em cache: nas mensagens seguintes custa 10% do preço. A data e a campanha ficam depois
  do trecho em cache, para não perdê-lo a cada minuto.
- **Resposta em formato garantido pela API** (`resposta` + `passar_para_humano`): o bot
  sabe quando passar para uma pessoa sem tentar adivinhar pelo texto. Se a IA recusar,
  cortar a resposta ou devolver algo fora do formato, a resposta vira uma mensagem padrão
  e a conversa vai para uma pessoa (`motivo_falha` diz o porquê).
- **Na dúvida, não inventa**: as instruções mandam responder só com o que está nas
  páginas e passar para uma pessoa quando a resposta não está lá.
- **Sonnet 5.5 com esforço de raciocínio "low"**: é o indicado para conversa (rápido e
  barato) e dúvida de FAQ não precisa de mais. No Sonnet, se o filtro de segurança da
  Anthropic recusar uma mensagem por engano, a própria API tenta de novo num modelo
  alternativo (`fallbacks: "default"`). O Haiku 4.5 não aceita nenhum dos dois
  parâmetros, então eles só vão para o Sonnet.
- **Custo calculado em cada resposta** (`precos.py`): é a base do teto diário de gasto
  que o bot vai ter.

## Onde cada coisa mora

- `ia.py` — `responder(historico, modelo=None)`, os tipos `Mensagem` e `RespostaIA`, e a
  exceção `IAIndisponivel` (sem chave, API fora do ar, limite de uso). Quem chama precisa
  tratar essa exceção: mandar uma mensagem fixa e passar a conversa para uma pessoa.
- `provedores/claude.py` — a chamada à API da Claude pelo SDK oficial (`anthropic`).
- `base_conhecimento.py` — monta o texto das páginas (`PAGINAS`) e os dados do momento.
  Para incluir uma página nova, acrescente-a em `PAGINAS`.
- `instrucoes.py` — como o assistente deve se comportar e o formato da resposta.
- `precos.py` — preço por token de cada modelo. Revise se a Anthropic mudar o preço.
- `verificacao_voz.py` — confere no texto os deslizes de voz mais comuns ("PIX",
  "+50%", "o cash-b", "pode voltar", Markdown que o WhatsApp não mostra).
- `perguntas_teste.py` — perguntas da comparação entre modelos, com armadilhas.
- `management/commands/comparar_modelos_assistente.py` — a comparação.

## Comparar Sonnet 5.5 e Haiku 4.5

O comando faz as mesmas perguntas aos dois modelos e gera um relatório HTML com as
respostas lado a lado, o custo, o tempo de resposta, os problemas de voz e se cada um
passou para uma pessoa quando devia. A escolha deve sair da leitura das respostas, não
só do preço: o bot fala de dinheiro e prazo.

1. Crie uma chave em console.anthropic.com (API Keys), com cartão cadastrado. Vale
   definir um limite mensal de gasto no console.
2. Coloque a chave no `.env`: `ANTHROPIC_API_KEY=...`
3. Rode:

   ```bash
   python manage.py comparar_modelos_assistente
   ```

   Opções: `--casos prazo_hoje,campanha` (só algumas perguntas),
   `--modelos claude-haiku-4-5` (só um modelo), `--saida arquivo.html`,
   `--cotacao 5.50` (reais por dólar).
4. Abra o `relatorio_comparacao_assistente.html` gerado (fica fora do Git).

Uma rodada completa (28 perguntas x 2 modelos) custa menos de US$ 0,50 (menos de
R$ 3). A pergunta sobre campanha só faz sentido com a campanha cadastrada no banco
usado. No banco local, cadastre a do 10/10 no admin antes de rodar.

Para escolher o modelo, mude `ASSISTENTE_IA_MODELO` no `.env` (ou no Render).

## Quando a base não cobre uma pergunta

O jeito certo de ensinar algo novo ao assistente é escrever a resposta no FAQ do site
(`paginas/templates/paginas/faq.html`): o assistente lê o FAQ, então quem entra no site
e quem pergunta no WhatsApp leem a mesma resposta. Depois, acrescente a pergunta em
`perguntas_teste.py` para a próxima comparação conferir.

## Próximos passos (o bot em si)

Ver o plano no resumo da conversa de planejamento (branch
`claude/cash-b-virtual-assistant-m7tgpk`): webhook do WhatsApp (Cloud API oficial da
Meta), worker no Render, conversas e caixa de resposta no admin, teto diário de gasto,
limite de mensagens por pessoa e a linha sobre atendimento por WhatsApp na política de
privacidade.
