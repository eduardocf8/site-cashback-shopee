# cash-b — guia de voz

Este arquivo documenta como a cash-b escreve (tom, verbos, expressões) —
ver `BRAND.md` pra identidade visual. É um documento vivo: cresce conforme
o dono da marca aponta o que soa diferente do jeito dele de falar.

## Regras já validadas

- **Nunca descreva o cashback base como condicional ("pode voltar", "pode
  gerar").** O que varia é o valor, conforme a % de comissão. Frases como
  "toda compra pode voltar parte do dinheiro" dão a entender (errado) que
  às vezes não tem cashback nenhum por acaso. Usar sempre afirmativo:
  "volta", "gera", "cai".
  - Mas **não prometer "toda compra" / "em toda compra"**: categorias sem
    comissão de afiliado na Shopee (ex: alimentos e bebidas) não geram
    cashback. O diferencial que dá pra afirmar sem ressalva é não ter
    limite: "sem limite por produto nem por número de compras" (hero da
    home) - na Cuponomia, por exemplo, o cashback na Shopee acaba depois
    da primeira compra (benchmark, ROADMAP Fase 13).
  - Exceção: bônus de campanha de comissão extra (link de produto
    específico) é de fato condicional — aí "pode render mais cashback"
    está correto, porque só ativa quando a Shopee tem campanha rodando.
- **Sem imperativo na forma "tu" (testa, cadastra, pede, acompanha).**
  Usar a forma "você" (teste, cadastre, peça, acompanhe) — é o padrão que
  já era seguido no banco `DICAS` de `instagram_bot/conteudo.py`, só o
  banco `POSTS_INSTITUCIONAIS` que tinha fugido dele.
- **A marca é tratada como substantivo feminino**: "a cash-b", "na cash-b",
  "da cash-b", "pela cash-b" — nunca "o cash-b", "no cash-b", "do cash-b"
  etc. Vale só quando "cash-b" é o próprio substantivo sendo referido
  ("bem-vindo à cash-b"); quando ela aparece como modificador de outro
  substantivo, o gênero desse outro substantivo é quem manda ("o site
  cash-b", "o link da cash-b" — aqui "link" já é masculino, então "do").
- **"Pix", não "PIX".** O nome é definido pelo Banco Central como nome
  próprio, não como sigla - só a primeira letra é maiúscula. Vale em
  qualquer lugar onde a palavra aparece como texto para o usuário ("saque
  via Pix", "chave Pix"). Nomes de constante e de campo no código
  (`chave_pix`, `TIPO_PIX`) não mudam - a regra é de escrita, não de código.
- **"Pra" e "pro" só quando forem contração de "para" + artigo.**
  "Para a" vira "pra", "para o" vira "pro" (ex: "pra Shopee", "pro
  vendedor", "pra primeira compra"). Em texto novo, escrever sempre assim,
  nunca "para a" / "para o" / "para os" / "para as" por extenso.
  - Sem artigo por trás, escrever "para" por extenso: "para você", "para
    quem comprou", "para começar", "para sempre", "para um", "para esse".
    "Pra você" e "pra começar" estão errados porque não existe "para a você"
    nem "para a começar" por trás.
  - O mesmo vale no plural: "para os" vira "pros" e "para as" vira "pras".
  - Exceção: texto de terceiros (mensagens de erro do governo, categorias
    da Shopee) não muda.
- **Sem vírgula antes do complemento em título.** "Ofertas automáticas da
  Shopee com o seu link", não "da Shopee, com o seu link". Vale para
  títulos e chamadas em que o "com…" / "no…" completa a frase.
- **Appfiliado: o público é "afiliado Shopee", não quem "divulga a Shopee".**
  Use "para afiliados Shopee", "para quem é afiliado Shopee", "ser afiliado
  Shopee". Evite "divulgar a Shopee" e "feito para quem divulga a Shopee".

## Onde essas regras já foram aplicadas

- `instagram_bot/conteudo.py` — bancos `LEMBRETES` e `POSTS_INSTITUCIONAIS`
  (2026-08-10).
- Gênero feminino da marca — templates do site, e-mails transacionais,
  conteúdo do Instagram e documentação interna (2026-08-14).
- `marketing/instagram/gerar_carrossel_beneficios.py` — regra do "pra"
  (2026-08-16).
- Carrosséis 01, 08 e 09 — "Pix" no lugar de "PIX" (2026-09-04).
- Restante do site — "Pix" no lugar de "PIX" (2026-09-04): templates
  (`paginas/`, `accounts/`, `links/`), e-mails transacionais
  (`pedidos/notificacoes.py`, `saques/`) e conteúdo do bot
  (`instagram_bot/conteudo.py`). Ficaram de fora de propósito as
  mensagens de erro simuladas da Asaas/Inter em `saques/tests.py`
  (texto de terceiro, fora do controle de voz da cash-b).

## Para pedir ajustes de voz numa conversa nova

Aponta esse arquivo junto com `BRAND.md`. Se notar algo soando diferente
do seu jeito de falar, aponta o trecho específico (ou onde ele está no
código) — a regra só entra aqui depois de confirmada com um exemplo real,
não por suposição.
