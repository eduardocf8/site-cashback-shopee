$ErrorActionPreference = "Stop"

Set-Location -LiteralPath $PSScriptRoot
$env:PLAYWRIGHT_BROWSERS_PATH = "0"

function Run-Step {
    param(
        [string]$Title,
        [scriptblock]$Action
    )

    Write-Host ""
    Write-Host $Title
    & $Action
}

function Find-InnoCompiler {
    $command = Get-Command iscc.exe -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    $candidates = @(
        (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
        (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe"),
        (Join-Path $env:LocalAppData "Programs\Inno Setup 6\ISCC.exe")
    )

    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path -LiteralPath $candidate)) {
            return $candidate
        }
    }

    return $null
}

try {
    Run-Step "Instalando/conferindo dependencias..." {
        python -m pip install -r requirements.txt
    }

    Run-Step "Instalando/conferindo Chromium do Playwright..." {
        python -m playwright install chromium
    }

    Run-Step "Limpando builds anteriores..." {
        # dist\Bot.ee e dist\ShopeeZapBot: nomes usados antes do app se
        # chamar Appfiliado - mantidos aqui so pra limpar builds antigas
        # que ainda possam existir na maquina de quem gera o instalador.
        foreach ($path in @("build", "dist\app.dist", "dist\app.build", "dist\Bot.ee", "dist\ShopeeZapBot")) {
            if (Test-Path -LiteralPath $path) {
                Remove-Item -LiteralPath $path -Recurse -Force
            }
        }

        if ((Test-Path -LiteralPath "dist\app.dist") -or (Test-Path -LiteralPath "dist\Bot.ee") -or (Test-Path -LiteralPath "dist\ShopeeZapBot")) {
            throw "Nao consegui limpar a pasta dist do aplicativo. Feche o Appfiliado, Chrome/Chromium, Explorer e pause o OneDrive se ele estiver sincronizando essa pasta."
        }
    }

    # Trocado de PyInstaller para Nuitka em 2026-09-27: o PyInstaller
    # empacota um interpretador Python + bytecode e se "auto-extrai" ao
    # rodar, um padrao que antivirus com heuristica costumam marcar como
    # falso positivo (chegava a ser detectado por varios engines no
    # VirusTotal). O Nuitka compila o Python de verdade para codigo de
    # maquina nativo - o mesmo app, compilado com Nuitka, teve muito
    # menos deteccoes nos testes que fizemos.
    #
    # Pre-requisito novo (o PyInstaller nao precisava disso): um
    # compilador C. --assume-yes-for-downloads deixa o Nuitka baixar
    # sozinho um MinGW64 portatil na primeira vez, se nao achar nenhum
    # instalado (Visual Studio Build Tools tambem funciona, se preferir).
    Run-Step "Gerando executavel com Nuitka..." {
        python -m nuitka --standalone --assume-yes-for-downloads --enable-plugins=pyside6 --windows-console-mode=disable --windows-icon-from-ico="assets\app_icon.ico" --include-data-dir="assets=assets" --output-dir=dist --output-filename=Appfiliado.exe app.py
    }

    $iscc = Find-InnoCompiler
    if (-not $iscc) {
        throw "Inno Setup nao encontrado. Confirme se ele esta instalado. Caminho comum: C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
    }

    Run-Step "Gerando instalador com Inno Setup..." {
        & $iscc installer.iss
    }

    Write-Host ""
    Write-Host "Instalador gerado em: installer\AppfiliadoSetup.exe"
    Write-Host ""
    Write-Host "Proximo passo recomendado (reduz aviso de antivirus/SmartScreen):"
    Write-Host "1. Confira o instalador no VirusTotal: https://www.virustotal.com/"
    Write-Host "2. Se algum antivirus acusar falso positivo, envie o arquivo para analise da Microsoft:"
    Write-Host "   https://www.microsoft.com/en-us/wdsi/filesubmission"
    exit 0
}
catch {
    Write-Host ""
    Write-Host "O processo falhou:"
    Write-Host $_.Exception.Message
    exit 1
}
