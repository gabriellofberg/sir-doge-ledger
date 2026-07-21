; Inno Setup script for SirDoge Ledger (Windows)
; Build after: pyinstaller sir-doge.spec && npm run build (in frontend)

#define MyAppName "SirDoge Ledger"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "SirDoge"
#define MyAppURL "https://github.com/gabriellofberg/sir-doge-ledger"
#define MyBuildDir "dist\SirDogeLedger"

[Setup]
SourceDir=..\..
AppId={{B2C3D4E5-F6A7-8901-BCDE-F12345678901}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\..\dist\installer
OutputBaseFilename=SirDogeLedger-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "swedish"; MessagesFile: "compiler:Languages\Swedish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
english.RemoveSavedDataPrompt=Do you also want to remove saved data (database, uploads, password)?
swedish.RemoveSavedDataPrompt=Vill du också ta bort sparade data (databas, uppladdningar, lösenord)?

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#MyBuildDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\SirDogeLedger.exe"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\SirDogeLedger.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\SirDogeLedger.exe"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
  begin
    if MsgBox(ExpandConstant('{cm:RemoveSavedDataPrompt}'), mbConfirmation, MB_YESNO) = IDYES then
      DelTree(ExpandConstant('{localappdata}\sir-doge-ledger'), True, True, True);
  end;
end;
