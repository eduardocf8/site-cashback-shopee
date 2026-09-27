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

## 2. Segredos salvos em texto puro — ✅ resolvido em 2026-09-27
- `shopee_api_secret` e `relatorio_email_senha_app` (senha de app do
  Gmail) agora são cifrados em disco com o DPAPI do Windows (novo
  módulo `credenciais_seguras.py`, chamado de dentro de
  `AppSettings.load()`/`save()`). A cifra é amarrada à conta do usuário
  do Windows na máquina atual — ninguém abre o `config_usuario.json`
  (ou um arquivo exportado) num editor de texto e vê a credencial.
- Continua funcionando sem pywin32/fora do Windows (fica em texto puro,
  degradação segura) e migra sozinho configs antigas já salvas em texto
  puro (decifra normal, recifra no próximo save).
- Efeito colateral conhecido e tratado: um `config_usuario.json`
  exportado/backupeado num computador não decifra em outro computador
  (é o ponto todo do DPAPI). "Importar configurações" e "Restaurar
  backup" agora detectam isso e avisam o usuário pra preencher a
  credencial de novo, em vez de deixar a API falhar em silêncio.
- Adicionado `pywin32` ao `requirements.txt` (só Windows) e
  `win32crypt` aos `hiddenimports` do `Bot.ee.spec`, pra garantir que o
  PyInstaller empacote o módulo no `.exe`.

## 3. Sem trava de instância única — ✅ resolvido em 2026-09-27
- `main()` (`app.py`) agora usa `QLockFile` (Qt) logo ao abrir, antes até
  da tela de licença: tenta travar `appfiliado.lock` em `APP_DIR`. Se já
  tiver outra janela aberta, mostra um aviso ("Appfiliado já está
  aberto...") e fecha, sem chegar a mexer no perfil do Chrome/banco.
- QLockFile já resolve sozinho o caso de a trava ter ficado "presa" por
  um fechamento anormal (queda de energia, processo morto à força): ele
  detecta que o PID dono não está mais rodando e libera a trava sozinho
  — testei isso simulando um "crash" (processo morto sem chamar
  `unlock()`) e confirmando que a trava é recuperada na tentativa
  seguinte, sem travar o usuário pra sempre.
- Só bloqueia de fato no erro `LockFailedError` (outra instância viva
  segurando a trava). Em `PermissionError`/`UnknownError` (ex: pasta
  sincronizada com OneDrive se comportando de forma estranha) deixa
  seguir normal, pra não bloquear o app por causa de um problema de
  infraestrutura sem relação com o risco real.
- `appfiliado.lock` adicionado ao `.gitignore`.

## 4. Zero testes automatizados — ✅ primeira leva feita em 2026-09-27
- Criada a pasta `tests/` com 128 testes (pytest), cobrindo exatamente as
  partes isoladas sugeridas antes de partir pra UI/integração:
  - `parser.py` (extração/limpeza de links, id de mensagem).
  - `formatador.py` (limpeza de linhas, preços, chamada/descrição da
    oferta, pipeline completo de `formatar_texto_oferta`).
  - `categorias_shopee.py` (normalização de texto, filtro de categoria).
  - `afiliados.py` — o núcleo de cálculo de indicadores (`agrupar_indicadores`,
    `calcular_resumo_status_pedidos`, `_comissao_conversao_valida`,
    conversão de números BR, `oferta_passa_filtros` etc.), usando
    `ConversorAfiliados()` sem rede/navegador (só a parte pura).
  - `credenciais_seguras.py` e `atualizacao.py` (os dois módulos novos
    desta sessão) — testes que simulam o DPAPI e usam um servidor HTTP
    local de verdade pra cobrir os casos de erro (JSON quebrado, HTTP
    500, servidor fora do ar, link malicioso etc.).
- Ainda **não** cobre a interface (PySide6) nem a automação real do
  WhatsApp/Shopee (browser/Playwright) — fica pra uma próxima etapa, se
  quiser continuar.
- `pytest.ini` (`testpaths = tests`) e `requirements-dev.txt` (pytest, sem
  poluir o `requirements.txt` de produção/exe). Como rodar: documentado no
  `README_APP.md`.
- Não mexi no `.github/workflows/` do monorepo (CI automático a cada
  push) — é uma decisão que afeta a infraestrutura compartilhada com o
  site cash-b, então fica pra quando o usuário confirmar que quer isso.

## 5. Email institucional da marca Appfiliado (contato@appfiliado.com.br)
- Combinado em 2026-09-26 (madrugada). Diferente do "Relatório por email"
  do bot (esse já existe e é só Gmail) — aqui é o email da marca/empresa,
  usado por ex. pelo backend do site pra mandar a chave de licença.
- Caminho decidido, nessa ordem:
  1. Comprar o domínio `appfiliado.com.br` (Registro.br, ~R$40/ano).
  2. Criar a caixa de email no **Zoho Mail, plano Mail Lite**
     (R$5/usuário/mês, cobrado anual = R$60/ano por caixa — tem app
     oficial iOS/Android e também funciona via IMAP/SMTP em qualquer
     app de email).
  3. Verificar o domínio `appfiliado.com.br` no painel do **Brevo**
     (adicionar domínio + configurar os registros DNS SPF/DKIM que ele
     pedir) — sem isso o envio automático de email pode cair em spam ou
     ser recusado.
  4. Só depois de tudo isso, trocar a variável `APPFILIADO_EMAIL_REMETENTE`
     no Render (hoje ainda no valor provisório `Appfiliado
     <contato@cash-b.com>`, ver `cashback_shopee/settings.py` e
     `.env.example`) para `Appfiliado <contato@appfiliado.com.br>`.
- Status: nada comprado/configurado ainda. Usuário decidiu deixar pra
  quando "o bot estiver da forma que eu quero" — sem risco em adiar, já
  que ainda não há cliente real do Appfiliado enviando/recebendo email.
