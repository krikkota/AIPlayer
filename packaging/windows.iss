#ifndef AppVersion
  #define AppVersion "0.2.2"
#endif
#ifndef ProjectRoot
  #define ProjectRoot ".."
#endif

[Setup]
AppId={{93205E5A-D4D5-45AA-8DC5-4F67142E98F1}
AppName=AIPlayer
AppVersion={#AppVersion}
AppPublisher=AIPlayer
AppComments=Local audio and video player with transcription
DefaultDirName={localappdata}\Programs\AIPlayer
DefaultGroupName=AIPlayer
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
SetupArchitecture=x64
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.19045
SourceDir={#ProjectRoot}
OutputDir=outputs
OutputBaseFilename=AIPlayer-{#AppVersion}-Windows-x64-Setup
SetupIconFile=player\assets\Player.ico
UninstallDisplayIcon={app}\AIPlayer.exe
WizardSmallImageFile=player\assets\Player.png
WizardImageFile=
WizardStyle=modern dynamic
DisableWelcomePage=no
Compression=lzma2/normal
SolidCompression=yes
CloseApplications=yes
RestartApplications=no
SetupLogging=yes

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "outputs\AIPlayer\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\AIPlayer"; Filename: "{app}\AIPlayer.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\AIPlayer"; Filename: "{app}\AIPlayer.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\AIPlayer.exe"; Description: "{cm:LaunchProgram,AIPlayer}"; WorkingDir: "{app}"; Flags: nowait postinstall skipifsilent

[Messages]
russian.WelcomeLabel1=Установка AIPlayer
russian.WelcomeLabel2=Видео, аудио и текст записи — в одном плеере.%n%nУстановщик подготовит приложение для вашей учётной записи. Распознавание речи и локальные модели настраиваются при первом запуске.%n%nНажмите «Далее», чтобы продолжить.
english.WelcomeLabel1=Install AIPlayer
english.WelcomeLabel2=Video, audio and a searchable transcript in one player.%n%nSetup will install the application for your Windows account. Speech recognition and local models are configured when you first open the player.%n%nClick Next to continue.
