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

## 6. Aviso do Windows SmartScreen/antivírus ao instalar (falso positivo) — ✅ mitigado em 2026-09-27
- Achado numa nova varredura por melhorias (não fazia parte da lista
  original de 5). Causa raiz: o `.exe` não é assinado digitalmente E era
  empacotado com PyInstaller, cujo padrão de "auto-extração" ao rodar é
  comum em malware de verdade, então antivírus com heurística
  costumavam marcar como suspeito. Discutimos comprar um certificado de
  assinatura de código (~US$99-120/ano) mas decidimos, por enquanto,
  pelas 3 mitigações gratuitas:
  1. **Trocado PyInstaller por Nuitka** (compila o Python de verdade
     para código de máquina nativo) em `requirements.txt`,
     `build_exe.bat`, `build_installer.ps1` e `installer.iss` — testei
     compilando o app inteiro com Nuitka nesta sandbox (Linux) e rodando
     o binário resultante (modo offscreen): compilou e abriu sem erro,
     incluindo a tela de licença. **Não testei a build real do Windows**
     (não tenho como rodar Windows aqui) — a primeira vez que isso rodar
     na máquina de build de verdade, confirme que gerou
     `dist\app.dist\Appfiliado.exe` e que o instalador funciona antes de
     distribuir. Novo pré-requisito: precisa de um compilador C na
     máquina de build (o Nuitka baixa um MinGW64 sozinho se não achar
     nenhum, via `--assume-yes-for-downloads`).
  2. **Passo de release documentado** em `README_APP.md`/
     `build_installer.ps1`: depois de gerar o instalador, subir no
     VirusTotal e, se algum antivírus acusar falso positivo, enviar pro
     portal gratuito da Microsoft
     (microsoft.com/en-us/wdsi/filesubmission) pra acelerar a remoção da
     detecção.
  3. **Página explicativa pra clientes** (o que fazer se o aviso
     aparecer na instalação): https://claude.ai/artifact/ExQwUy3oMYLsmjmRZ2nEpj
     — pode linkar na página de vendas/email de boas-vindas.
- `Bot.ee.spec` (config antiga do PyInstaller) removido, já sem uso.
- Certificado de assinatura de código continua como opção futura, se/quando
  fizer sentido pelo volume real de clientes — não implementado agora.
- **Correção em seguida (mesmo dia)**: o usuário reparou que o instalador
  gerado ainda ia se chamar `Bot.eeSetup.exe`/`Bot.ee.exe` — nome antigo
  do app, de antes de virar "Appfiliado". Corrigido em `installer.iss`
  (`MyAppName`, `MyAppExeName`, `AppPublisher`, `DefaultDirName`,
  `OutputBaseFilename` — o `AppId` foi mantido igual de propósito, pra
  não quebrar detecção de atualização), `build_exe.bat`,
  `build_installer.ps1`/`.bat` e o texto de oferta de teste em `app.py`
  ("OFERTA TESTE BOT.EE" → "OFERTA TESTE APPFILIADO"). Instalador agora
  sai como `AppfiliadoSetup.exe`, e o app instala em
  `%localappdata%\Appfiliado`.
- **Observação**: existe uma pasta irmã `bot_whatsapp_ofertas/` (sem
  "_generico") com os mesmos resquícios de "Bot.ee" - é um projeto
  separado que não mexi nesta sessão. Perguntar ao usuário se quer o
  mesmo tratamento lá antes de tocar.

## 7. Modo Grupo: origem agora aceita canal, além de grupo — implementado em 2026-09-28, confirmar em uso real
- Pedido do usuário: hoje a captura de mensagens (`grupo_origem`) só
  funcionava com um grupo normal do WhatsApp; canais só eram suportados
  como destino de envio.
- Implementado em `whatsapp.py`: `preparar_monitoramento_origem` agora
  detecta sozinho se `grupo_origem` é um grupo ou um canal (tenta grupo
  primeiro, cai pra canal se não achar) e guarda o tipo detectado
  (`self._tipo_origem_detectado`) pra não tentar os dois de novo a cada
  ciclo - só redetecta se o app for reiniciado. Reaproveita a mesma
  infraestrutura de navegação já usada pro envio a canais
  (`ir_para_aba_canais`, `_clicar_item_lateral_generico_por_titulo`),
  mas a confirmação de que abriu certo usa só o nome no cabeçalho
  (`temNome`), sem exigir caixa de mensagem - a conta pode só *seguir*
  o canal de origem sem ser admin dele (admin só é necessário pra
  *publicar*, não pra ler).
- `abrir_grupo()` (método antigo, só grupo) foi removido - não tinha
  mais nenhuma chamada depois dessa mudança.
- Testado nesta sessão: 5 testes novos (`tests/test_whatsapp_origem.py`)
  cobrindo a lógica de detecção/cache/fallback com Playwright mockado
  (detecta grupo de primeira, cai pra canal quando grupo falha, erro
  quando nem um nem outro existe, reaproveita o tipo já descoberto nas
  duas variações). App inteiro renderizado offscreen sem erro.
- **O que NÃO pude testar**: se a captura de mensagens
  (`capturar_mensagens`, que lê `div[data-testid='msg-container']`) lê
  corretamente o conteúdo de dentro de um canal de verdade - só valida
  isso com WhatsApp Web real, que não tenho acesso nesta sandbox. Testar
  configurando `grupo_origem` com o nome de um canal de verdade e
  conferindo se as ofertas aparecem na aba Logs/Histórico normalmente.

## 8. Ajustes de tela: botões cortados, campo Categoria/nicho e cor do título "Sobre" — resolvido em 2026-09-28
- **Botões cortados nas abas Execução e Modo Shopee**: causa raiz era o
  `config_tabs.setMinimumHeight(390)` - alto o suficiente pro conteúdo
  caber com a fonte usada no teste (Linux), mas aparentemente insuficiente
  no Windows de verdade (fonte Segoe UI renderiza um pouco mais larga/alta -
  já vimos esse padrão várias vezes nesta sessão). Aumentado pra `440`,
  dando ~50px de folga extra pras 6 abas de configuração de uma vez.
  **Não pude confirmar no Windows real** (só o ambiente Linux desta
  sandbox) - se ainda cortar em algum lugar, me avise que aumento mais.
- **Filtro "Categoria/nicho" no Modo Shopee**: confirmado no código
  (`afiliados.py::oferta_passa_filtros`) que as categorias já eram
  *ignoradas* quando "Tipo de busca" não é "Por categoria" - ou seja,
  selecionar categorias com "Ofertas gerais" escolhido nunca teve efeito
  nenhum, é exatamente igual a rodar sem nenhuma categoria selecionada.
  O campo já ficava desabilitado (`setEnabled(False)`) nesse caso, só não
  tinha nenhum estilo visual de "desabilitado" - por isso parecia igual a
  um campo normal. Adicionado `QLineEdit:disabled`/`QComboBox:disabled`
  no `apply_styles()` (fundo e texto acinzentados), que agora vale pra
  **todos** os campos desabilitados do app (não só esse), incluindo
  Palavra-chave/nicho e Loja/marca que tinham o mesmo problema visual.
- **Título "Appfiliado v1.0.0" ilegível na tela Sobre**: reaproveitava o
  estilo `#appTitle` (texto branco, pensado pra o fundo escuro da barra
  lateral) - invisível no fundo claro do diálogo. Criado `#aboutTitle`
  próprio, com a mesma cor escura (`#20372F`) usada nos botões "Verificar
  atualizações"/"Fechar".
- **Correção em seguida (mesmo dia)**: o usuário reportou que "Categoria/
  nicho" continuava respondendo a clique (abria o popup e deixava marcar
  categoria) mesmo com "Ofertas gerais" selecionado, apesar do
  `setEnabled(False)`. Causa real: `ComboBoxMultiplaSelecao` guarda o
  popup de seleção como uma janela separada (`Qt.Popup`) e intercepta
  clique nela via `eventFilter` - o bloqueio automático de eventos que o
  Qt aplica a um widget desabilitado não alcançava essa janela separada.
  Corrigido fazendo o próprio `eventFilter` checar `self.isEnabled()` e
  ignorar o clique quando desabilitado. Testado com 4 testes novos
  (`tests/test_combo_multipla_selecao.py`): clique abre popup/marca item
  quando habilitado (comportamento existente preservado), e não faz nada
  quando desabilitado (bug corrigido) - usando `QMouseEvent` de verdade,
  não só chamando a função Python isolada.
- **Correção importante em seguida (mesmo dia)**: o aumento de
  `config_tabs.setMinimumHeight()` pra `440` piorou a situação no Windows
  real - o usuário reportou sobreposição feia em praticamente todas as 6
  abas (botões colados na barra de abas de baixo, texto cortado, vazios
  enormes em abas com pouco conteúdo). **Revertido para `390`** (valor
  original). Causa provável do "puxar o número mais alto não ajudou":
  `config_tabs` não cresce à custa da janela - ele só tira espaço de
  `data_tabs` (que tem o stretch todo). Se a janela real do usuário não
  tem altura de sobra, aumentar o mínimo de um lado só empurra o
  problema pra sobreposição em vez de resolver. Troquei a estratégia:
  em vez de mexer no orçamento de altura compartilhado entre as 6 abas
  (arriscado, já provou que piora as coisas), reduzi margens/espaçamento
  *só* dentro das abas Execução e Modo Shopee (as duas que realmente
  tinham conteúdo cortado): `execution_form`/`offers_form` com menos
  margem vertical, espaçamento entre os itens do painel de opções
  reduzido, e a caixa de status do Modo Shopee de 96px pra 70px mínimos
  (ela é rolável, não perde texto). Renderizei as 6 abas de novo
  (offscreen) pra confirmar que nenhuma ficou com sobreposição -
  continua sem poder confirmar 100% no Windows real, mas essa
  abordagem tem risco bem menor de piorar outras abas, já que só toca
  no conteúdo interno das duas abas com problema relatado.

## 9. Bloqueador crítico: nenhum cliente conseguia ativar a licença — ✅ resolvido em 2026-09-29
- Achado na pergunta "o que falta pra divulgar": `licenca_servidor_url`
  tinha default `""` em `settings.py`. Como esse campo não aparece em
  nenhuma tela (é dev-only), **todo cliente novo cairia em "Servidor de
  licenças não configurado"** ao tentar ativar a chave, sem nenhum jeito
  de resolver sozinho - só descobrimos porque o próprio usuário passou por
  isso e eu ajudei a editar o arquivo manualmente.
- Corrigido: `licenca_servidor_url` agora tem como valor padrão
  `https://site-cashback-shopee.onrender.com/licencas/validar/` (o
  endereço real, já validado nesta sessão com uma licença de teste
  criada direto no admin). Testado: uma instalação nova, sem nenhum
  `config_usuario.json` prévio, já recebe esse valor certo automaticamente
  (simulei isso diretamente, criando um `AppSettings.load()` num arquivo
  que não existia ainda).
- `LICENCA.md` atualizado (a seção "O que falta" estava desatualizada
  nesse ponto).
- **Ainda pendente, mesmo tema**: só o evento "compra aprovada" da Kiwify
  foi confirmado contra um payload real - cancelamento/reembolso/
  chargeback/atraso ainda não foram testados com um evento de verdade.
  Recomendo testar isso (ex: assinar e cancelar de propósito, conferir no
  admin se bloqueia) antes do primeiro cliente pagante.
