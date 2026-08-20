; Inno Setup script for BumpSpoof.
; Build the app first (packaging/dist/BumpSpoof), then compile this with Inno
; Setup 6+ (ISCC.exe packaging\installer.iss) to produce Output\BumpSpoof-Setup.exe.

#define AppName "BumpSpoof"
#define AppVersion "2.0.0"
#define AppPublisher "BumpSpoof"
#define AppExe "BumpSpoof.exe"

[Setup]
AppId={{C0FFEE00-B00B-4B00-9E55-BUMPSP00F001}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=Output
OutputBaseFilename={#AppName}-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
ArchitecturesAllowed=x64compatible
WizardStyle=modern
; No admin needed if installed per-user; default installs to Program Files (admin).
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
Name: "vi"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Tạo lối tắt trên Desktop"; GroupDescription: "Lối tắt:"

[Files]
; The whole PyInstaller one-folder output.
Source: "dist\BumpSpoof\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\Gỡ cài đặt {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "Chạy {#AppName} ngay"; Flags: nowait postinstall skipifsilent

; User data (~/.bumpspoof) lives in the profile and is intentionally NOT removed
; on uninstall, so tours/favorites/device memory survive a reinstall.
