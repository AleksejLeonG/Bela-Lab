; Compile through app/tools/build_windows_installer.ps1.
#ifndef StageRoot
  #error StageRoot must point to an extracted Bela Lab release bundle.
#endif
#ifndef ReleaseVersion
  #error ReleaseVersion must match the bundled Bela Lab executable.
#endif
#define ProjectUrl "https://github.com/AleksejLeonG/Bela-Lab"

[Setup]
AppId={{8D36D51D-21D1-4B0B-83A8-3D60C909A21C}
AppName=Bela Lab
AppVersion={#ReleaseVersion}
AppPublisher=Bela Lab project
AppPublisherURL={#ProjectUrl}
AppSupportURL={#ProjectUrl}/issues
AppUpdatesURL={#ProjectUrl}/releases
VersionInfoVersion={#ReleaseVersion}
VersionInfoDescription=Bela Lab Setup
DefaultDirName={localappdata}\Programs\Bela Lab
DefaultGroupName=Bela Lab
DisableWelcomePage=no
DisableProgramGroupPage=no
AllowNoIcons=no
PrivilegesRequired=lowest
MinVersion=10.0
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
AppMutex=Local\BelaLabDesktop
UninstallDisplayIcon={app}\Bela Lab.exe
LicenseFile={#StageRoot}\TERMS.md
SetupIconFile=assets\bela-lab.ico
OutputBaseFilename=Bela-Lab-{#ReleaseVersion}-Windows-x64-Setup
WizardStyle=modern
Compression=lzma2
SolidCompression=yes

[Files]
; Saved matches, preferences and logs live outside the install directory.
Source: "{#StageRoot}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Bela Lab"; Filename: "{app}\Bela Lab.exe"; WorkingDir: "{app}"

[Run]
Filename: "{app}\Bela Lab.exe"; Description: "Launch Bela Lab"; Flags: postinstall nowait skipifsilent unchecked; Check: WebView2Available
Filename: "https://developer.microsoft.com/microsoft-edge/webview2/"; Description: "WebView2 is missing. Open Microsoft's Evergreen Runtime download page"; Flags: postinstall shellexec nowait skipifsilent; Check: not WebView2Available

[Code]
function WebView2Available: Boolean;
var
  Version: String;
begin
  { Microsoft documents these per-machine and per-user Evergreen runtime keys. }
  Result :=
    (RegQueryStringValue(HKLM32, 'SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', Version)
      and (Version <> '') and (Version <> '0.0.0.0'))
    or (RegQueryStringValue(HKCU, 'SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', Version)
      and (Version <> '') and (Version <> '0.0.0.0'));
end;
