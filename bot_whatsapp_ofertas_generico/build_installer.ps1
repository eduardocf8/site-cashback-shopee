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
        foreach ($path in @("build", "dist\Bot.ee", "dist\ShopeeZapBot")) {
            if (Test-Path -LiteralPath $path) {
                Remove-Item -LiteralPath $path -Recurse -Force
            }
        }

        if ((Test-Path -LiteralPath "dist\Bot.ee") -or (Test-Path -LiteralPath "dist\ShopeeZapBot")) {
            throw "Nao consegui limpar a pasta dist do aplicativo. Feche o Bot.ee, Chrome/Chromium, Explorer e pause o OneDrive se ele estiver sincronizando essa pasta."
        }
    }

    Run-Step "Gerando executavel com PyInstaller..." {
        python -m PyInstaller --noconfirm --windowed --name Bot.ee --icon "assets\app_icon.ico" --add-data "assets;assets" app.py
    }

    $iscc = Find-InnoCompiler
    if (-not $iscc) {
        throw "Inno Setup nao encontrado. Confirme se ele esta instalado. Caminho comum: C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
    }

    Run-Step "Gerando instalador com Inno Setup..." {
        & $iscc installer.iss
    }

    Write-Host ""
    Write-Host "Instalador gerado em: installer\Bot.eeSetup.exe"
    exit 0
}
catch {
    Write-Host ""
    Write-Host "O processo falhou:"
    Write-Host $_.Exception.Message
    exit 1
}
