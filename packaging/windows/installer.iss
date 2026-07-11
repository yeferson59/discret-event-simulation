; Instalador Windows (Inno Setup) para el build de PyInstaller.
; Se corre desde CI con:
;   iscc packaging\windows\installer.iss /DSourceDir=dist\SimuladorEventosDiscretos /DAppVersion=1.0.0
; `SourceDir` y `AppVersion` tienen defaults para poder correrlo también a mano.

#ifndef SourceDir
  #define SourceDir "..\..\dist\SimuladorEventosDiscretos"
#endif
#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif

#define AppName "Simulador de Eventos Discretos"
#define AppExeName "SimuladorEventosDiscretos.exe"

[Setup]
AppId={{6F1B2E6E-6C2B-4E7A-9B0E-5B6E7B6C9E10}
AppName={#AppName}
AppVersion={#AppVersion}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
UninstallDisplayIcon={app}\{#AppExeName}
OutputDir=..\..\installer_output
OutputBaseFilename=SimuladorEventosDiscretos-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Tasks]
Name: desktopicon; Description: "Crear acceso directo en el escritorio"; GroupDescription: "Accesos directos:"

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Ejecutar {#AppName}"; Flags: nowait postinstall skipifsilent
