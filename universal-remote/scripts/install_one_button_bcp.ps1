# BCP single launcher: reversible migration, no deletion of shortcuts or user files.
param([switch]$Apply,[switch]$NoAutoStart)
$ErrorActionPreference='Stop'
$root=Join-Path $env:LOCALAPPDATA 'BCP-Universal-Remote'
$source=Join-Path $root 'build-repo\universal-remote\windows\bcp_control_center.pyw'
$target=Join-Path $root 'bcp_control_center.pyw'
$desktop=[Environment]::GetFolderPath('Desktop')
$archive=Join-Path $desktop '_Projets et outils\BCP - anciens raccourcis'
$launcher=Join-Path $desktop 'BCP - OUVRIR.lnk'
$startup=[Environment]::GetFolderPath('Startup')
$startupLink=Join-Path $startup 'BCP - Centre de contrôle.lnk'
if(-not(Test-Path -LiteralPath $source)){throw 'CONTROL_CENTER_SOURCE_MISSING'}
$python=(Get-Command python.exe -ErrorAction Stop).Source
$pythonw=Join-Path (Split-Path -Parent $python) 'pythonw.exe'
if(-not(Test-Path -LiteralPath $pythonw)){throw 'PYTHONW_NOT_FOUND'}
& $python -m py_compile $source
if($LASTEXITCODE -ne 0){throw 'CONTROL_CENTER_SYNTAX_ERROR'}
$legacy=@(Get-ChildItem -LiteralPath $desktop -File|
  Where-Object { $_.Name -like 'BCP*' -and
    $_.Extension -in @('.cmd','.lnk','.url','.bat') -and
    $_.FullName -ne $launcher })
Write-Output ('BCP_OLD_DESKTOP_SHORTCUTS='+$legacy.Count)
Write-Output ('BCP_NEW_DESKTOP_SHORTCUT='+$launcher)
Write-Output ('BCP_KEEP_PREVIOUS_SHORTCUTS='+$archive)
if(-not $Apply){
  Write-Output 'BCP_SINGLE_BUTTON_DRY_RUN_PASS'
  Write-Output 'Nothing was moved, deleted, or installed'
  exit 0
}
New-Item -ItemType Directory -Force -Path $archive|Out-Null
$backup=Join-Path $root ('backups\ONE_BUTTON_'+(Get-Date -Format 'yyyyMMdd_HHmmss'))
New-Item -ItemType Directory -Force -Path $backup|Out-Null
$originalWasPresent=Test-Path -LiteralPath $target
if($originalWasPresent){
  Copy-Item -LiteralPath $target -Destination (Join-Path $backup 'bcp_control_center.pyw') -Force
}
Copy-Item -LiteralPath $source -Destination $target -Force
& $python -m py_compile $target
if($LASTEXITCODE -ne 0){throw 'INSTALLED_UI_FAILED_COMPILE'}
$old=@()
try{
  $shell=New-Object -ComObject WScript.Shell
  foreach($shortcut in $legacy){
    $dst=Join-Path $archive $shortcut.Name
    if(Test-Path -LiteralPath $dst){
      $stem=[IO.Path]::GetFileNameWithoutExtension($shortcut.Name)
      $dst=Join-Path $archive ($stem+'_'+(Get-Date -Format 'yyyyMMdd_HHmmss')+$shortcut.Extension)
    }
    Move-Item -LiteralPath $shortcut.FullName -Destination $dst -ErrorAction Stop
    $old+=@{old=$shortcut.FullName;archived=$dst}
  }
  $link=$shell.CreateShortcut($launcher)
  $link.TargetPath=$pythonw
  $link.Arguments='"'+$target+'"'
  $link.WorkingDirectory=$root
  $link.Description='BCP: un seul centre de contrôle, connexion automatique, appareils et diagnostic'
  $link.IconLocation="$env:SystemRoot\System32\shell32.dll,14"
  $link.Save()
  if(-not(Test-Path $launcher)){throw 'LAUNCHER_CREATION_FAILED'}
  if(-not $NoAutoStart){
    $autolink=$shell.CreateShortcut($startupLink)
    $autolink.TargetPath=$pythonw
    $autolink.Arguments='"'+$target+'" --minimized'
    $autolink.WorkingDirectory=$root
    $autolink.Description='BCP Control Center – démarrage automatique'
    $autolink.Save()
  }
  $old|ConvertTo-Json -Depth 3|Set-Content -LiteralPath (Join-Path $backup 'archived-shortcuts.json') -Encoding utf8
  Write-Output ('BCP_SINGLE_LAUNCHER_INSTALLED='+$launcher)
  Write-Output ('BCP_OLD_SHORTCUTS_ARCHIVED='+$old.Count)
  Write-Output ('BCP_BACKUP='+$backup)
  Write-Output ('BCP_AUTOSTART_CONFIGURED='+(-not $NoAutoStart))
}catch{
  foreach($entry in $old){
    if(Test-Path -LiteralPath $entry.archived){
      Move-Item -LiteralPath $entry.archived -Destination $entry.old -Force
    }
  }
  if(Test-Path -LiteralPath $launcher){Remove-Item -LiteralPath $launcher -Force}
  if($originalWasPresent){
    Copy-Item -LiteralPath (Join-Path $backup 'bcp_control_center.pyw') -Destination $target -Force
  }elseif(Test-Path $target){Remove-Item -LiteralPath $target -Force}
  throw
}
