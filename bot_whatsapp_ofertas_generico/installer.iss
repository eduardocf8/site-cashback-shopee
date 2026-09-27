#define MyAppName "Bot.ee"
#define MyAppVersion "1.0.0"
#define MyAppExeName "Bot.ee.exe"

[Setup]
AppId={{9F3F0E98-A5BD-43B4-8AE0-3C8E42685B01}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=Bot.ee
DefaultDirName={localappdata}\Bot.ee
DisableDirPage=no
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=installer
OutputBaseFilename=Bot.eeSetup
SetupIconFile=assets\app_icon.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na Área de Trabalho"; GroupDescription: "Atalhos:"; Flags: unchecked

[Files]
; A pasta de saida do Nuitka leva o nome do script de entrada (app.py ->
; app.dist), nao o nome do produto - ver build_installer.ps1.
Source: "dist\app.dist\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Abrir {#MyAppName}"; Flags: nowait postinstall skipifsilent
