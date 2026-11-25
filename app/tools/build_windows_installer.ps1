param(
    [Parameter(Mandatory)][string]$ReleaseZip,
    [string]$Compiler
)

$ErrorActionPreference = 'Stop'
$project = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../..')).Path
$zip = (Resolve-Path -LiteralPath $ReleaseZip).Path
$expected = ((Get-Content -LiteralPath "$zip.sha256" -Raw).Trim() -split '\s+')[0]
if ($expected -ine (Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash) {
    throw 'The release ZIP does not match its SHA-256 file.'
}

if (!$Compiler) {
    $command = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    $candidates = @(
        $command.Source
        (Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6/ISCC.exe')
        (Join-Path $env:LOCALAPPDATA 'Programs/Inno Setup 6/ISCC.exe')
    )
    $Compiler = $candidates | Where-Object { $_ -and (Test-Path -LiteralPath $_ -PathType Leaf) } |
        Select-Object -First 1
}
if (!$Compiler) { throw 'Install Inno Setup 6, or provide the path to ISCC.exe with -Compiler.' }
$Compiler = (Resolve-Path -LiteralPath $Compiler).Path

$dist = (Resolve-Path -LiteralPath (Join-Path $project 'dist')).Path
$temporaryRoot = (Resolve-Path -LiteralPath ([IO.Path]::GetTempPath())).Path.TrimEnd('\')
$stage = Join-Path $temporaryRoot ('bela-installer-stage-' + [guid]::NewGuid().ToString('N'))
$payload = Join-Path $stage 'payload'
try {
    Expand-Archive -LiteralPath $zip -DestinationPath $payload
    $executable = Get-Item -LiteralPath (Join-Path $payload 'Bela Lab.exe')
    $version = $executable.VersionInfo.ProductVersion
    if ($version -notmatch '^\d+\.\d+\.\d+$') { throw 'Invalid release version in Bela Lab.exe.' }
    $expectedZip = "Bela-Lab-$version-Windows-x64.zip"
    if ((Split-Path -Leaf $zip) -ne $expectedZip) { throw "Expected $expectedZip for this build." }
    if (Test-Path -LiteralPath (Join-Path $payload 'saves')) { throw 'The installer payload contains save data.' }
    $fileName = "Bela-Lab-$version-Windows-x64-Setup.exe"
    $output = Join-Path $dist $fileName
    $checksum = "$output.sha256"
    if ((Test-Path -LiteralPath $output) -or (Test-Path -LiteralPath $checksum)) {
        throw 'The setup or its checksum already exists. Move the previous build before packaging.'
    }
    $compiled = Join-Path $stage $fileName
    & $Compiler "/DStageRoot=$payload" "/DReleaseVersion=$version" "/O$stage" (Join-Path $project 'app/BelaLab.iss')
    if ($LASTEXITCODE -ne 0 -or !(Test-Path -LiteralPath $compiled -PathType Leaf)) {
        throw "Inno Setup compilation failed with exit code $LASTEXITCODE."
    }
    Move-Item -LiteralPath $compiled -Destination $output
    $hash = (Get-FileHash -LiteralPath $output -Algorithm SHA256).Hash.ToLowerInvariant()
    Set-Content -LiteralPath $checksum -Value "$hash  $(Split-Path -Leaf $output)" -Encoding ascii
    Write-Output $output
    Write-Output $checksum
} finally {
    if (Test-Path -LiteralPath $stage) {
        $resolved = (Resolve-Path -LiteralPath $stage).Path
        if ((Split-Path -Parent $resolved) -eq $temporaryRoot -and (Split-Path -Leaf $resolved) -like 'bela-installer-stage-*') {
            try { Remove-Item -LiteralPath $resolved -Recurse -Force }
            catch { Write-Warning "Could not remove temporary installer files at $resolved. $($_.Exception.Message)" }
        }
    }
}
