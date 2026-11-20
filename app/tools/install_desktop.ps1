# Per-user install; no administrator permissions or shared Python required.
$ErrorActionPreference = 'Stop'
$project = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$source = Join-Path $project 'dist/Bela Lab'
$destination = Join-Path $env:LOCALAPPDATA 'Programs/Bela Lab'
$data = Join-Path $env:LOCALAPPDATA 'Bela Lab'
if (!(Test-Path -LiteralPath (Join-Path $source 'Bela Lab.exe'))) { throw 'Build the desktop executable first.' }
$running = Get-Process -Name 'Bela Lab' -ErrorAction SilentlyContinue
if ($running) { throw 'Close Bela Lab before installing an update.' }
New-Item -ItemType Directory -Path $destination -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $source 'Bela Lab.exe') -Destination $destination -Force
Copy-Item -LiteralPath (Join-Path $project 'app/assets/bela-lab.ico') -Destination $destination -Force
Copy-Item -LiteralPath (Join-Path $source '_internal') -Destination $destination -Recurse -Force
# Import the current project archive once. Updates never replace existing app saves.
$saves = Join-Path $data 'saves/dashboard'
if (!(Test-Path -LiteralPath $saves)) {
    New-Item -ItemType Directory -Path $saves -Force | Out-Null
    $old = Join-Path $project 'saves/dashboard'
    if (Test-Path -LiteralPath $old) {
        Get-ChildItem -LiteralPath $old -File | Where-Object { $_.Name -eq 'active.json' -or $_.Name -like '*.player.json' -or $_.Name -like '*.feedback.json' } | Copy-Item -Destination $saves
    }
    foreach ($folder in @('bots','analysis','trump-analysis','review')) {
        $path = Join-Path $old $folder
        if (Test-Path -LiteralPath $path) { Copy-Item -LiteralPath $path -Destination $saves -Recurse }
    }
}
$shell = New-Object -ComObject WScript.Shell
$menu = Join-Path ([Environment]::GetFolderPath('Programs')) 'Bela Lab'
New-Item -ItemType Directory -Path $menu -Force | Out-Null
foreach ($link in @((Join-Path $menu 'Bela Lab.lnk'), (Join-Path ([Environment]::GetFolderPath('Desktop')) 'Bela Lab.lnk'))) {
    $shortcut = $shell.CreateShortcut($link)
    $shortcut.TargetPath = Join-Path $destination 'Bela Lab.exe'
    $shortcut.WorkingDirectory = $destination
    $shortcut.IconLocation = (Join-Path $destination 'bela-lab.ico') + ',0'
    $shortcut.Description = 'Play and analyse Croatian Bela'
    $shortcut.Save()
}
Write-Output "Installed: $(Join-Path $destination 'Bela Lab.exe')"
Write-Output "Saved games: $saves"
