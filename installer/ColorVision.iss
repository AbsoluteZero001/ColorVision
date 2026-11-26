#ifndef MyAppVersion
  #define MyAppVersion "1.5.0"
#endif

#ifndef SourceDir
  #define SourceDir "..\build\installer-staging"
#endif

#define MyAppName "ColorVision"
#define MyAppDisplayName "ColorVision 颜色识别系统"
#define MyAppPublisher "ColorVision"
#define MyAppExeName "ColorVision.exe"

[Setup]
AppId={{8F6A9C3B-4E2F-4F4A-9B18-7C3F6D2E4101}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppDisplayName} V{#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={code:GetDefaultInstallDir}
AppendDefaultDirName=yes
UsePreviousAppDir=yes
DisableDirPage=no
DisableProgramGroupPage=yes
DefaultGroupName={#MyAppName}
OutputDir=..\dist
OutputBaseFilename=ColorVision_Setup
SetupIconFile=..\assets\ColorVision.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppDisplayName}
Compression=lzma2/normal
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=commandline
AppMutex=ColorVision_App_Running
CloseApplications=yes
CloseApplicationsFilter=*.exe,*.dll
RestartApplications=no
DirExistsWarning=no
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
LaunchApp=启动 ColorVision 颜色识别系统

[Dirs]
; Grant standard users Modify (NOT Full Control) ONLY on writable app data/config/cache/log folders.
Name: "{app}\config"; Permissions: users-modify
Name: "{app}\data"; Permissions: users-modify
Name: "{app}\data\photos"; Permissions: users-modify
Name: "{app}\data\photos\captures"; Permissions: users-modify
Name: "{app}\data\photos\uploads"; Permissions: users-modify
Name: "{app}\data\history"; Permissions: users-modify
Name: "{app}\data\database"; Permissions: users-modify
Name: "{app}\cache"; Permissions: users-modify
Name: "{app}\logs"; Permissions: users-modify

[Files]
Source: "{#SourceDir}\ColorVision.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceDir}\_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#SourceDir}\README.md"; DestDir: "{app}"; Flags: ignoreversion
; Preserve user configuration during upgrades and uninstalls.
Source: "{#SourceDir}\config\app.json"; DestDir: "{app}\config"; Flags: onlyifdoesntexist uninsneveruninstall; Permissions: users-modify
Source: "{#SourceDir}\config\api-config.json"; DestDir: "{app}\config"; Flags: onlyifdoesntexist uninsneveruninstall; Permissions: users-modify
Source: "{#SourceDir}\config\camera.json"; DestDir: "{app}\config"; Flags: onlyifdoesntexist uninsneveruninstall; Permissions: users-modify

[Icons]
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\{#MyAppExeName}"; Comment: "启动 ColorVision 颜色识别系统"
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\{#MyAppExeName}"; Comment: "启动 ColorVision 颜色识别系统"
Name: "{group}\卸载 {#MyAppName}"; Filename: "{uninstallexe}"; IconFilename: "{app}\{#MyAppExeName}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchApp}"; Flags: nowait postinstall skipifsilent

[Code]
const
  DRIVE_REMOVABLE = 2;
  DRIVE_FIXED = 3;
  INSTALL_DIR_PLACEHOLDER = '__COLORVISION_INSTALL_DIR__';

var
  MissingDDrivePrompted: Boolean;
  DefaultTargetWasFallback: Boolean;

function GetDriveTypeW(lpRootPathName: string): UINT;
  external 'GetDriveTypeW@kernel32.dll stdcall';

function IsDriveAvailable(const DriveRoot: string): Boolean;
var
  DriveType: UINT;
begin
  Result := False;
  if not DirExists(DriveRoot) then
    Exit;
  DriveType := GetDriveTypeW(DriveRoot);
  Result := (DriveType = DRIVE_FIXED) or (DriveType = DRIVE_REMOVABLE);
end;

function FindFallbackDrive(): string;
var
  DriveIdx: Integer;
  Candidate: string;
begin
  for DriveIdx := Ord('E') to Ord('Z') do
  begin
    Candidate := Chr(DriveIdx) + ':\';
    if IsDriveAvailable(Candidate) then
    begin
      Result := Candidate;
      Exit;
    end;
  end;
  Result := AddBackslash(ExpandConstant('{sd}'));
end;

function GetDefaultInstallDir(Param: string): string;
begin
  if IsDriveAvailable('D:\') then
  begin
    DefaultTargetWasFallback := False;
    Result := 'D:\ColorVision';
  end
  else
  begin
    DefaultTargetWasFallback := True;
    Result := FindFallbackDrive() + 'ColorVision';
  end;
end;

function JsonEscapeString(const Value: string): string;
var
  I: Integer;
  Ch: Char;
begin
  Result := '';
  for I := 1 to Length(Value) do
  begin
    Ch := Value[I];
    if Ch = '\' then
      Result := Result + '\\'
    else if Ch = '"' then
      Result := Result + '\"'
    else
      Result := Result + Ch;
  end;
end;

function HasCmdSwitch(const SwitchName: string): Boolean;
var
  I: Integer;
begin
  Result := False;
  for I := 1 to ParamCount do
  begin
    if CompareText(ParamStr(I), SwitchName) = 0 then
    begin
      Result := True;
      Exit;
    end;
  end;
end;

function IsBareDriveRoot(const DirPath: string): Boolean;
var
  Normalized: string;
begin
  Normalized := RemoveBackslashUnlessRoot(Trim(DirPath));
  Result := (Length(Normalized) <= 3) and (Pos(':', Normalized) = 2);
end;

procedure InitializeWizard();
begin
  MissingDDrivePrompted := False;
end;

procedure CurPageChanged(CurPageID: Integer);
var
  FallbackDir: string;
begin
  if CurPageID = wpSelectDir then
  begin
    if (not IsDriveAvailable('D:\')) and (not DirExists(WizardDirValue + '\_internal')) and (not MissingDDrivePrompted) and (not WizardSilent) then
    begin
      MissingDDrivePrompted := True;
      FallbackDir := WizardDirValue;
      WizardForm.SelectDirLabel.Caption :=
        '未检测到可用的 D 盘，已为您自动选择备用磁盘。您可以直接安装到下方路径，或点击“浏览”选择其他可用磁盘目录：';
      MsgBox(
        '未检测到可用的 D 盘，无法使用默认安装路径 D:\ColorVision。' + #13#10 + #13#10 +
        '已为您自动切换为：' + FallbackDir + #13#10 +
        '请在当前页面确认或自定义其他可用磁盘路径。',
        mbInformation,
        MB_OK
      );
    end;
  end;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if CurPageID = wpSelectDir then
  begin
    if IsBareDriveRoot(WizardDirValue) then
    begin
      if not WizardSilent then
        MsgBox(
          '不能将安装路径直接设为磁盘根目录（例如 C:\ 或 D:\）。' + #13#10 +
          '请选择具体的子目录（例如 D:\ColorVision）。',
          mbError,
          MB_OK
        );
      Result := False;
    end;
  end;
end;

procedure UpdateAppJsonInstallDir();
var
  AppJsonPath: string;
  EscapedAppDir: string;
  RawText: string;
  ContentUtf8: AnsiString;
begin
  AppJsonPath := ExpandConstant('{app}\config\app.json');
  if not FileExists(AppJsonPath) then
    Exit;
  if not LoadStringFromFile(AppJsonPath, ContentUtf8) then
    Exit;
  RawText := UTF8Decode(ContentUtf8);
  if Pos(INSTALL_DIR_PLACEHOLDER, RawText) > 0 then
  begin
    EscapedAppDir := JsonEscapeString(ExpandConstant('{app}'));
    StringChangeEx(RawText, INSTALL_DIR_PLACEHOLDER, EscapedAppDir, True);
    SaveStringToFile(AppJsonPath, UTF8Encode(RawText), False);
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  SessionCache: string;
begin
  if CurStep = ssPostInstall then
  begin
    UpdateAppJsonInstallDir();
    SessionCache := ExpandConstant('{app}\cache\runtime-session.json');
    if FileExists(SessionCache) then
      DeleteFile(SessionCache);
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  AppDir: string;
  HasUserData: Boolean;
  ShouldPurge: Boolean;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    AppDir := RemoveBackslashUnlessRoot(ExpandConstant('{app}'));
    if IsBareDriveRoot(AppDir) then
      Exit;

    HasUserData :=
      DirExists(AppDir + '\config') or
      DirExists(AppDir + '\data') or
      DirExists(AppDir + '\cache') or
      DirExists(AppDir + '\logs');

    if not HasUserData then
      Exit;

    ShouldPurge := False;
    if HasCmdSwitch('/PURGE') then
    begin
      ShouldPurge := True;
    end
    else if not UninstallSilent then
    begin
      ShouldPurge :=
        MsgBox(
          'ColorVision 程序主体已卸载，默认已保留您的配置和业务数据：' + #13#10 +
          '  - config（应用、API 及摄像头配置）' + #13#10 +
          '  - data（历史图片、上传历史、本地数据库）' + #13#10 +
          '  - cache（缓存）与 logs（运行日志）' + #13#10 + #13#10 +
          '是否完全清理整个 ColorVision 安装文件夹？' + #13#10 +
          '警告：选择“是”将永久删除上述所有数据与历史图片，且无法恢复！',
          mbConfirmation,
          MB_YESNO or MB_DEFBUTTON2
        ) = IDYES;
    end;

    if ShouldPurge then
    begin
      DelTree(AppDir, True, True, True);
    end;
  end;
end;
