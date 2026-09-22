"""
Configuração central do navegador de automação usado nas tarefas da Shopee
(login, resolver links curtos, capturar produtos de uma coleção).

Por que este módulo existe
--------------------------
A Shopee derruba automação (mostrando captcha / "navegador não suportado" /
página /verify/) ANTES mesmo de renderizar o conteúdo. Trocar Chrome por Edge
não resolve, porque o que ela detecta não é a marca do navegador, e sim os
sinais de automação que o Playwright deixa por padrão:

  1. A flag de linha de comando "--enable-automation" (mostra a barra "sendo
     controlado por software de teste" e é o sinal nº 1 lido pela Shopee).
  2. A flag "--enable-blink-features=IdleDetection" e afins.
  3. navigator.webdriver == true.
  4. Ausência da flag "--disable-blink-features=AutomationControlled", que é o
     que de fato esconde o controle por CDP.

Este módulo concentra os argumentos corretos em UM lugar só, para os três
pontos de launch usarem exatamente a mesma configuração (sem divergir com o
tempo). O ponto mais importante é o par:

    ignore_default_args=["--enable-automation"]
    args=[..., "--disable-blink-features=AutomationControlled"]

que juntos removem os sinais que disparam o captcha da Shopee.
"""

# User-Agent de um Chrome real recente. Manter alinhado com uma versão
# plausível evita o "navegador não aceito". (Se você atualizar o Chrome/Edge
# instalado, pode subir esse número, mas não é obrigatório.)
USER_AGENT_PADRAO = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)

# Script injetado em TODA página nova antes de qualquer script do site rodar.
# MANTIDO MINIMO DE PROPOSITO: esconde apenas navigator.webdriver, que e o
# sinal essencial. Adulterar navigator.plugins/languages/permissions costuma
# QUEBRAR o widget antibot da Shopee (que checa se essas props foram mexidas),
# resultando em "Erro de Carregamento" no lugar do captcha. Menos e mais aqui.
SCRIPT_ANTI_DETECCAO = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
"""


def _args_janela(headless_visual):
    """
    headless_visual=True aqui significa "janela pequena/discreta" (o bot roda
    de fato com janela, só menor). False = maximizada. Nunca usamos headless
    de verdade para a Shopee, porque headless é trivialmente detectável.
    """
    if headless_visual:
        return ["--window-size=1280,900"]
    return ["--start-maximized"]


def montar_args_navegador(headless_visual=False):
    """
    Monta a lista de args de linha de comando para o Chromium/Chrome/Edge de
    forma a NÃO parecer automação. Ordem não importa; o que importa é a
    presença de --disable-blink-features=AutomationControlled.
    """
    args = [
        # A flag mais importante: desliga a sinalização de "controlado por
        # automação" que a Shopee lê.
        "--disable-blink-features=AutomationControlled",
        # Reduz pop-ups/avisos que denunciam ambiente de automação, SEM mexer
        # em isolamento de origem/iframes.
        "--no-default-browser-check",
        "--no-first-run",
        "--disable-popup-blocking",
        "--lang=pt-BR",
    ]
    # IMPORTANTE: NAO adicionar aqui flags que quebram iframes de origem
    # cruzada (ex.: --disable-features=IsolateOrigins,site-per-process nem
    # --disable-infobars agressivo). O widget de captcha da Shopee roda dentro
    # de um iframe de terceiro; desligar isolamento de site faz o captcha
    # falhar ao CARREGAR ("Erro de Carregamento"), impedindo ate a resolucao
    # manual.
    args.extend(_args_janela(headless_visual))
    return args


def montar_kwargs_launch(
    user_data_dir,
    channel=None,
    headless_visual=False,
    extra_args=None,
):
    """
    Monta o dicionário de kwargs para chromium.launch_persistent_context(...)
    já com a configuração anti-detecção correta.

    - ignore_default_args=["--enable-automation"] REMOVE a flag que o Playwright
      injeta por padrão e que dispara o captcha da Shopee. Esta é a mudança
      que faltava e que faz o Chrome E o Edge pararem de pedir captcha.
    - channel=None faz cair no Chromium embutido do Playwright (fallback).
    """
    args = montar_args_navegador(headless_visual=headless_visual)
    if extra_args:
        args.extend(extra_args)

    kwargs = {
        "user_data_dir": str(user_data_dir),
        "headless": False,
        "no_viewport": True,
        "timeout": 30000,
        "args": args,
        # >>> A CORREÇÃO CENTRAL DO CAPTCHA <<<
        "ignore_default_args": ["--enable-automation"],
        "locale": "pt-BR",
        "timezone_id": "America/Sao_Paulo",
    }
    if channel:
        # Usando o Chrome/Edge REAL instalado: NAO sobrescrever o User-Agent.
        # O UA nativo do navegador e coerente com os "client hints" (versao,
        # motor) que ele envia. Forcar um UA fixo (ex.: Chrome/126) enquanto o
        # navegador real e outra versao cria uma inconsistencia que servicos
        # antibot leem como robo - e pode ate quebrar o carregamento do
        # proprio captcha ("Erro de Carregamento").
        kwargs["channel"] = channel
    else:
        # Chromium embutido do Playwright (fallback): aqui vale forcar um UA de
        # Chrome real, porque o UA padrao do Chromium "puro" e mais suspeito.
        kwargs["user_agent"] = USER_AGENT_PADRAO
    return kwargs


def aplicar_anti_deteccao_no_contexto(contexto):
    """
    Aplica o script anti-detecção no CONTEXTO inteiro (todas as abas, presentes
    e futuras), antes de qualquer script do site rodar. Chame isso logo depois
    de abrir o launch_persistent_context.
    """
    try:
        contexto.add_init_script(SCRIPT_ANTI_DETECCAO)
    except Exception:
        # Se por algum motivo não der para aplicar no contexto (versão antiga
        # do Playwright), não é fatal: cada página ainda aplica o seu próprio
        # init script como fallback.
        pass

