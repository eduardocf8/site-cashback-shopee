# Roadmap — cash-b

Continuação das fases do `README.md` (que vai até a Fase 7 — deploy em produção).
Cada fase é um pacote de trabalho que pode virar uma conversa/sessão própria.
Marca o checkbox conforme for implementando.

## Fase 8 — Jurídico e confiança

O mais urgente do roadmap: o site já coleta CPF, e-mail e chave PIX, e mexe
com transferência de dinheiro (hoje em sandbox da Asaas) — isso deixa de ser
"bom ter" e vira exigência básica antes de abrir pra usuários de verdade.

- [ ] **Termos de Uso** — regras de cashback, prazos, motivos de cancelamento,
      responsabilidades do cash-b e do usuário.
- [ ] **Política de Privacidade (LGPD)** — quais dados são coletados (CPF,
      e-mail, chave PIX, histórico de cliques/pedidos), pra que servem, com
      quem são compartilhados (Shopee, Asaas), e os direitos do titular.
- [ ] **Aviso de cookies** — banner simples, exigido junto com a política de
      privacidade.
- [ ] **Página "Regras do cashback"** — versão mais completa do que já está
      na home (venda direta x indireta), incluindo prazo de liberação e o que
      cancela um pedido.
- [ ] Links pra essas páginas no rodapé de `home.html` (hoje o rodapé só tem
      uma linha de texto).

## Fase 9 — Suporte

- [ ] **FAQ / Perguntas frequentes** — cobrir dúvidas como "quanto tempo
      demora o cashback", "por que meu pedido foi cancelado", "qual o valor
      mínimo de saque", além de explicar os 4 tipos de saldo do dashboard
      (pendente/validado/liberado/cancelado) com mais detalhe do que a legenda
      curta que já existe em cada cartão.
- [ ] **Fale conosco** — formulário de contato de verdade (hoje não existe
      nenhum canal). Pode ser simples: formulário que manda e-mail pro
      `contato@cash-b.com` usando a mesma infraestrutura de e-mail do Brevo
      já configurada (ver `BRAND.md`).

## Fase 10 — Conta do usuário

Dá pra aproveitar a infraestrutura de e-mail que já está funcionando
(recuperação de senha) pra essas features.

- [ ] **Confirmação de e-mail no cadastro** — hoje qualquer e-mail é aceito
      sem verificar que o usuário tem acesso a ele.
- [ ] **Trocar senha estando logado** — hoje só existe o fluxo de "esqueci
      minha senha"; falta uma opção dentro da própria conta.
- [ ] **Editar dados cadastrais** — nome, e-mail, CPF.
- [ ] **E-mails automáticos de status** — avisar o usuário quando um pedido é
      validado/liberado, ou quando um saque é pago. Hoje ele só descobre
      entrando no dashboard.

## Fase 11 — Polimento técnico

- [ ] **Paginação/filtro no histórico** — hoje o dashboard mostra só os
      últimos 30 pedidos, 20 saques e 30 links gerados, sem filtro nem
      paginação.
- [ ] **Páginas de erro 404/500 customizadas** — usando a identidade visual
      do cash-b em vez da página padrão do Django.
- [ ] **SEO básico** — meta tags (já tem uma description na home), sitemap.xml,
      robots.txt.

## Fase 12 — Crescimento (não essencial agora)

- [ ] **Programa de indicação** — "chame um amigo, ganhe X de cashback" ou
      similar.

---

Pra continuar esse roadmap numa conversa nova, basta apontar esse arquivo
(`ROADMAP.md`) e o `BRAND.md` — juntos eles dão o contexto de identidade
visual e do que falta implementar, sem precisar reconstruir o histórico da
conversa original.
