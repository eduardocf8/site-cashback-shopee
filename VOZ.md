# cash-b — guia de voz

Este arquivo documenta como a cash-b escreve (tom, verbos, expressões) —
ver `BRAND.md` pra identidade visual. É um documento vivo: cresce conforme
o dono da marca aponta o que soa diferente do jeito dele de falar.

## Regras já validadas

- **Nunca descreva o cashback base como condicional ("pode voltar", "pode
  gerar").** Toda compra na Shopee gera cashback — o que varia é só o
  valor, conforme a % de comissão. Frases como "toda compra pode voltar
  parte do dinheiro" dão a entender (errado) que às vezes não tem
  cashback nenhum. Usar sempre afirmativo: "volta", "gera", "cai".
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
- **"Pra" só quando for contração de "para" + "a" (artigo feminino).**
  Ex: "pra revisão" está errado porque não existe "para a revisão" por trás
  — o certo é "para revisão". Já "pra próxima sincronização" está certo,
  porque é "para a próxima sincronização". Na dúvida, escrever por extenso
  ("para você", "para quem comprou") e só contrair pra "pra" se sobrar um
  "a" antes do substantivo/pronome feminino.
  - Exceção: citação literal de um texto que já existe no site (ex: o
    botão "Ir pra Shopee") não muda, mesmo fugindo da regra — é o nome
    real do elemento, não prosa livre.

## Onde essas regras já foram aplicadas

- `instagram_bot/conteudo.py` — bancos `LEMBRETES` e `POSTS_INSTITUCIONAIS`
  (2026-08-10).
- Gênero feminino da marca — templates do site, e-mails transacionais,
  conteúdo do Instagram e documentação interna (2026-08-14).
- `marketing/instagram/gerar_carrossel_beneficios.py` — regra do "pra"
  (2026-08-16).
- Carrosséis 01, 08 e 09 — "Pix" no lugar de "PIX" (2026-09-04). O
  restante do site ainda usa "PIX" (~86 ocorrências), pendente.

## Para pedir ajustes de voz numa conversa nova

Aponta esse arquivo junto com `BRAND.md`. Se notar algo soando diferente
do seu jeito de falar, aponta o trecho específico (ou onde ele está no
código) — a regra só entra aqui depois de confirmada com um exemplo real,
não por suposição.
