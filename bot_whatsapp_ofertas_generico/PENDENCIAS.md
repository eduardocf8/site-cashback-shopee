# Pendências — Appfiliado

Lista de temas discutidos que ficaram "pra depois". Quando o usuário pedir
algo como "fale minhas pendências", listar os itens abaixo e perguntar qual
encarar primeiro. Ao resolver um item, marcar como concluído (ou remover) e
registrar isso no commit que fizer a mudança.

## 1. Configurar o endpoint de verificação de atualização
- Código já implementado e testado (`atualizacao.py`, integrado ao `app.py`
  em 2026-09-26/27 — checagem silenciosa no início + botão manual na tela
  "Sobre"). Falta a parte de infraestrutura, que o usuário pediu ajuda mas
  não agora:
  - Montar o arquivo JSON de "versão disponível" (`versao_disponivel`,
    `url_download`, `notas`, `obrigatoria`).
  - Escolher onde hospedar esse arquivo (opção discutida: um arquivo
    público no GitHub, já que é simples e gratuito).
  - Hospedar o instalador da nova versão em algum link direto de download.
  - Preencher `atualizacao_servidor_url` em `config_usuario.json` com o
    link real do arquivo JSON.
  - Testar o fluxo ponta a ponta com uma versão fictícia antes do primeiro
    uso real.

## 2. Segredos salvos em texto puro
- `shopee_api_secret` e `relatorio_email_senha_app` (senha de app do
  Gmail) ficam gravados sem criptografia em `config_usuario.json` e são
  incluídos, também sem proteção, no recurso "Exportar configurações".
- Risco: se o usuário mandar esse arquivo exportado pra suporte ou
  guardar em nuvem, vaza credenciais.
- Sugestão discutida: mascarar esses campos no export, ou cifrar com uma
  chave derivada da máquina.
- Status: não implementado, aguardando decisão do usuário.

## 3. Sem trava de instância única
- Nada impede abrir o app duas vezes ao mesmo tempo (mesmo perfil do
  Chrome, mesmo banco SQLite) — risco de posts duplicados ou corrupção
  de dados.
- Sugestão discutida: lock local (arquivo ou porta) checado ao iniciar.
- Status: não implementado, aguardando decisão do usuário.

## 4. Zero testes automatizados
- App com mais de 12 mil linhas (`app.py`, `bot_runner.py`, `afiliados.py`,
  `whatsapp.py` etc.) sem nenhum teste unitário.
- Sugestão discutida: começar por partes isoladas e fáceis de testar
  (parser de ofertas, formatador, cálculo de indicadores) antes de partir
  pra UI/integração.
- Status: não implementado, aguardando decisão do usuário.
