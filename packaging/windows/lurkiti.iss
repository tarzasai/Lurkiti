; Inno Setup script for lurkiti. Compiled in CI on the windows runner:
;   ISCC /DMyAppVersion=<version> packaging\windows\lurkiti.iss
; Expects the PyInstaller onedir output in dist\lurkiti\.
#ifndef MyAppVersion
  #define MyAppVersion "0.0.0"
#endif
#define MyAppName "Lurkiti"
#define MyAppExeName "lurkiti.exe"

[Setup]
AppId={{7F3C1E88-2A5D-4B6F-8C1A-LURK1T1TRAY}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=Tarzasai
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=dist\installer
OutputBaseFilename=lurkiti-{#MyAppVersion}-setup
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"; Flags: unchecked
Name: "startup"; Description: "Start {#MyAppName} when I log in"; GroupDescription: "Startup:"; Flags: unchecked

[Files]
Source: "dist\lurkiti\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: startup

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent
