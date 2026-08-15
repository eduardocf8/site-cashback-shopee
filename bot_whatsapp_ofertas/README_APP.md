# Bot.ee - Aplicativo

Versao atual: 1.0.0

Esta pasta contem o bot transformado em aplicativo com interface.

## Rodar em desenvolvimento

1. Instale as dependencias:

```bat
python -m pip install -r requirements.txt
python -m playwright install chromium
```

2. Abra o app:

```bat
python app.py
```

3. Preencha:

- grupo de origem
- grupos de destino, separados por ponto e virgula
- canais de destino, se quiser (opcional; tambem separados por ponto e virgula)
- AppID da Shopee
- Secret da Shopee
- tempos em segundos
- Sub IDs, se quiser rastrear cliques/vendas na Shopee
- se deseja ignorar links ja enviados anteriormente

4. Use os botoes `Testar API Shopee` e `Testar grupos` se quiser conferir tudo antes de iniciar.
5. Clique em `Salvar configuracoes` e depois em `Iniciar bot`.

## Enviar para grupo e para canal do WhatsApp ao mesmo tempo

Na aba "Execução" existem dois campos de destino separados:

- **Grupos de destino**: conversas/grupos normais do WhatsApp, na aba padrão
  "Conversas".
- **Canais de destino** (opcional): canais do WhatsApp (WhatsApp Channels),
  que ficam em outro lugar da interface do WhatsApp, na aba "Canais" -
  separada dos grupos normais.

Os dois campos podem ser preenchidos ao mesmo tempo: quando isso acontece, o
bot envia a mesma oferta para todos os grupos E para todos os canais, no
mesmo ciclo. Se só um dos campos estiver preenchido, o bot envia só para
esse.

Pontos importantes sobre canais:

- O nome informado deve ser exatamente igual ao nome do canal.
- Só quem administra o canal consegue publicar nele; se a conta usada pelo
  bot não for admin do canal, o envio falha.
- O campo "Grupo de origem" (de onde o bot lê as ofertas) continua sendo
  sempre um grupo/conversa normal - os campos de destino é que definem para
  onde as ofertas são enviadas.
- Logo depois que o WhatsApp Web carrega/loga, o ícone de "Canais" na
  lateral pode demorar até ~1 minuto pra aparecer (o WhatsApp está
  sincronizando esse recurso com o celular) - isso acontece mesmo com a
  conta já administrando um canal. O bot aguarda até 90 segundos por esse
  ícone antes de desistir, então a primeira tentativa após abrir o
  WhatsApp pode demorar um pouco mais que o normal; isso é esperado.
- Como o layout de Canais no WhatsApp Web muda com certa frequência, use o
  botão `Testar grupos` após configurar para confirmar que o bot encontra o
  canal antes de deixar o envio automático rodando.

## Categorias no relatorio de Sub ID

A aba "Indicadores" e o relatorio diario por email não mostram mais o Sub ID
cru retornado pela Shopee: os valores são agrupados em categorias de origem,
definidas em `ConversorAfiliados.classificar_sub_id_relatorio` (`afiliados.py`):

- Sub ID começando com `user` → **cash-b**
- Sub ID composto só por traço(s) (`-`) → **redes sociais**
- Sub ID contendo `siteconversor` → **siteconversor**
- Sub ID contendo `grupoofertas` → **grupoofertas**
- Qualquer outro valor continua aparecendo como o próprio Sub ID (categoria
  ainda não mapeada).

## Gerar EXE

Execute:

```bat
build_exe.bat
```

O executavel sera criado em:

```text
dist\Bot.ee\Bot.ee.exe
```

## Gerar instalador

Para gerar um instalador `.exe`, instale o Inno Setup:

```text
https://jrsoftware.org/isdl.php
```

Depois execute:

```bat
build_installer.bat
```

O instalador sera criado em:

```text
installer\Bot.eeSetup.exe
```

Por padrao, o instalador sugere uma pasta dentro de `AppData` do usuario, mas a pessoa pode escolher outra pasta. O app salva `config_usuario.json`, `mensagens_app.db`, `logs/` e o perfil do WhatsApp na pasta escolhida na instalacao.

O build ja configura `PLAYWRIGHT_BROWSERS_PATH=0` para incluir o Chromium usado pelo Playwright dentro do aplicativo empacotado.

## Arquivos importantes

- `app.py`: interface visual
- `bot_runner.py`: controlador iniciar/parar do bot
- `settings.py`: leitura e salvamento das configuracoes
- `config_usuario.json`: criado automaticamente quando o app roda
- `mensagens_app.db`: guarda mensagens vistas e links ja enviados
- `logs/`: guarda os arquivos de log por dia
- `assets/`: guarda icones e arquivos visuais do aplicativo
- `installer.iss`: configuracao do instalador Inno Setup
- `build_installer.bat`: atalho para gerar o executavel e depois o instalador
- `build_installer.ps1`: script principal usado pelo `build_installer.bat`
- `afiliados.py`: conversao via API Shopee
- `whatsapp.py`: controle do WhatsApp Web
