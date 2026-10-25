# Toolbelt's installer (25 Oct 2026). Install.cmd runs this; Windows' Apps list runs it with -Uninstall.
#
# Install:   finds Python 3.12+ (offers to get it with winget), copies the app to %LOCALAPPDATA%\Programs\Toolbelt,
#            makes Toolbelt's own Python folder (%LOCALAPPDATA%\Toolbelt\venv), installs the packages, adds Toolbelt
#            to Settings > Apps (with an Uninstall button) and starts it. Toolbelt then makes its Start-menu entry.
# Uninstall: closes Toolbelt, puts back what it changed in Windows (main.py --uninstall: Calculator key, Win+W,
#            the internet switch's tasks, the Start-menu entries), removes the app folder and the Apps entry, and asks
#            before removing Toolbelt's data (settings, engines, App guard's quarantine).
# Everything is for this Windows user only: no admin rights needed (the internet switch's removal asks once).
param(
    [switch]$Uninstall,
    [string]$Target = (Join-Path $env:LOCALAPPDATA "Programs\Toolbelt"),
    [string]$Data = (Join-Path $env:LOCALAPPDATA "Toolbelt"),
    [string]$RegName = "Toolbelt",
    [switch]$Yes,            # answer yes to every question (for tests)
    [switch]$NoStart,        # don't start Toolbelt at the end (for tests)
    [switch]$SkipPackages,   # don't run pip (for tests)
    [switch]$SkipCleanup     # don't run main.py --uninstall (for tests: it would undo this PC's real settings)
)
$ErrorActionPreference = "Stop"
$Source = $PSScriptRoot
$Venv = Join-Path $Data "venv"
$VenvPy = Join-Path $Venv "Scripts\python.exe"
$RegKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\$RegName"

function Say($text, $colour = "Gray") { Write-Host $text -ForegroundColor $colour }
function Ask($question) {
    if ($Yes) { return $true }
    $answer = Read-Host "$question (y/n)"
    return $answer -match '^(y|yes|j|ja)$'
}
function Fail($text) {
    Say ""
    Say $text "Red"
    exit 1
}

function Stop-Toolbelt {
    # Toolbelt.exe / pythonw start the real Python as a child, so look at the command line: anything running this main.py
    $main = Join-Path $Target "main.py"
    Get-CimInstance Win32_Process -Filter "Name like 'python%' or Name = 'Toolbelt.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -and $_.CommandLine.IndexOf($main, [StringComparison]::OrdinalIgnoreCase) -ge 0 -and $_.ProcessId -ne $PID } |
        ForEach-Object { Say "Closing the running Toolbelt..."; Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
}

function Find-Python {
    # The py launcher first, then python on PATH, then the usual folders. Windows' Store stand-in (WindowsApps\python.exe)
    # only opens the Store, so a candidate counts only when it really runs and is 3.12 or newer.
    $candidates = @()
    if (Get-Command py -ErrorAction SilentlyContinue) { $candidates += , @("py", "-3") }
    if (Get-Command python -ErrorAction SilentlyContinue) { $candidates += , @((Get-Command python).Source) }
    foreach ($dir in @("$env:LOCALAPPDATA\Python\pythoncore-3.14-64", "$env:LOCALAPPDATA\Programs\Python\Python314",
                       "$env:LOCALAPPDATA\Programs\Python\Python313", "$env:LOCALAPPDATA\Programs\Python\Python312")) {
        if (Test-Path "$dir\python.exe") { $candidates += , @("$dir\python.exe") }
    }
    foreach ($c in $candidates) {
        try {
            $exe = $c[0]; $extra = @($c | Select-Object -Skip 1)
            $out = & $exe @extra -c "import sys; print(sys.executable); print(int(sys.version_info >= (3, 12)))" 2>$null
            if ($LASTEXITCODE -eq 0 -and $out.Count -ge 2 -and $out[1] -eq "1") { return $out[0] }
        } catch { }
    }
    return $null
}

function Install-Toolbelt {
    Say ""
    Say "  Toolbelt setup" "Yellow"
    Say "  Installs for this Windows user only: the app in $Target, its Python folder and data in $Data."
    Say ""

    # 1. Python
    $python = Find-Python
    if (-not $python) {
        Say "Toolbelt needs Python 3.12 or newer, and it isn't on this PC."
        if (-not (Get-Command winget -ErrorAction SilentlyContinue)) { Fail "Install Python from https://www.python.org/downloads/ (tick 'Add to PATH'), then run Install.cmd again." }
        if (-not (Ask "Install Python 3.14 now with winget (Microsoft's installer, about 30 MB)?")) { Fail "Python is needed. Install it from https://www.python.org/downloads/ and run Install.cmd again." }
        & winget install --id Python.Python.3.14 -e --scope user --accept-package-agreements --accept-source-agreements
        $env:Path = [Environment]::GetEnvironmentVariable("Path", "User") + ";" + [Environment]::GetEnvironmentVariable("Path", "Machine")
        $python = Find-Python
        if (-not $python) { Fail "Python was installed but can't be found yet. Close this window and run Install.cmd again." }
    }
    Say "Python: $python" "Green"

    # 2. The app files (an update replaces the code but keeps everything in $Data)
    $same = (Resolve-Path $Source).Path.TrimEnd('\') -ieq ([IO.Path]::GetFullPath($Target)).TrimEnd('\')
    if (-not $same) {
        Stop-Toolbelt
        New-Item -ItemType Directory -Force -Path $Target | Out-Null
        foreach ($dir in @("toolbelt", "web")) {
            if (Test-Path (Join-Path $Target $dir)) { Remove-Item -Recurse -Force (Join-Path $Target $dir) }
            Copy-Item -Recurse (Join-Path $Source $dir) (Join-Path $Target $dir)
        }
        foreach ($file in @("main.py", "requirements.txt", "README.md", "LICENSE", "setup.ps1", "Install.cmd", "Toolbelt.cmd")) {
            if (Test-Path (Join-Path $Source $file)) { Copy-Item -Force (Join-Path $Source $file) (Join-Path $Target $file) }
        }
    }
    Say "App: $Target" "Green"

    # 3. Toolbelt's own Python folder and its packages
    if (-not (Test-Path $VenvPy)) {
        Say "Making Toolbelt's Python folder..."
        New-Item -ItemType Directory -Force -Path $Data | Out-Null
        & $python -m venv $Venv
        if ($LASTEXITCODE -ne 0) { Fail "Couldn't make the Python folder ($Venv)." }
    }
    if (-not $SkipPackages) {
        Say "Installing the packages (pywebview, Pillow, onnxruntime and a few more, about 150 MB, a few minutes)..."
        & $VenvPy -m pip install --upgrade --quiet pip
        & $VenvPy -m pip install --quiet -r (Join-Path $Target "requirements.txt")
        if ($LASTEXITCODE -ne 0) { Fail "pip couldn't install the packages. Is the internet on? Then run Install.cmd again." }
    }
    Say "Python folder: $Venv" "Green"

    # 4. Settings > Apps (with Uninstall)
    $version = "1.0"
    $m = Select-String -Path (Join-Path $Target "main.py") -Pattern '^VERSION = "([0-9.]+)' | Select-Object -First 1
    if ($m) { $version = $m.Matches[0].Groups[1].Value }
    $uninstall = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$(Join-Path $Target 'setup.ps1')`" -Uninstall -Target `"$Target`" -Data `"$Data`""
    if ($RegName -ne "Toolbelt") { $uninstall += " -RegName `"$RegName`"" }
    New-Item -Path $RegKey -Force | Out-Null
    $values = @{ DisplayName = "Toolbelt"; DisplayVersion = $version; Publisher = "Shamilimanuel"; InstallLocation = $Target
                 DisplayIcon = (Join-Path $Target "web\icons\toolbelt-cartridge.ico"); UninstallString = $uninstall
                 URLInfoAbout = "https://github.com/Shamilimanuel/Toolbelt" }
    foreach ($k in $values.Keys) { Set-ItemProperty -Path $RegKey -Name $k -Value $values[$k] }
    Set-ItemProperty -Path $RegKey -Name NoModify -Value 1 -Type DWord
    Set-ItemProperty -Path $RegKey -Name NoRepair -Value 1 -Type DWord
    Say "Added to Settings > Apps (uninstall it from there)." "Green"

    # 5. Start it: on its first start Toolbelt adds itself to the Start menu
    Say ""
    if (-not $NoStart) {
        Start-Process -FilePath (Join-Path $Venv "Scripts\pythonw.exe") -ArgumentList "`"$(Join-Path $Target 'main.py')`"" -WorkingDirectory $Target
        Say "Done. Toolbelt is starting; from now on it's in the Start menu." "Yellow"
    } else {
        Say "Done." "Yellow"
    }
}

function Uninstall-Toolbelt {
    Say ""
    Say "  Uninstall Toolbelt" "Yellow"
    if (-not (Ask "Remove Toolbelt from this PC?")) { Say "Nothing was changed."; return }

    Stop-Toolbelt
    if (-not $SkipCleanup -and (Test-Path $VenvPy) -and (Test-Path (Join-Path $Target "main.py"))) {
        Say "Putting back what Toolbelt changed in Windows..."
        & $VenvPy (Join-Path $Target "main.py") --uninstall
    }
    if (Test-Path $Target) { Remove-Item -Recurse -Force $Target }
    if (Test-Path $RegKey) { Remove-Item -Recurse -Force $RegKey }
    Say "The app is removed." "Green"

    if (Test-Path $Data) {
        $mb = [math]::Round(((Get-ChildItem -Recurse -File $Data -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum) / 1MB)
        $quarantine = Join-Path $Data "quarantine"
        $held = @(Get-ChildItem -File $quarantine -ErrorAction SilentlyContinue).Count
        Say ""
        Say "Toolbelt's data is still there ($mb MB): settings, the engines, its Python folder$(if ($held) { ", and $held file(s) in App guard's quarantine" })."
        if ($held) { Say "Quarantined files are gone for good if you remove the data. Restore them in Toolbelt first if you want any back." "Red" }
        if (Ask "Remove the data too?") {
            Remove-Item -Recurse -Force $Data
            Say "Data removed." "Green"
        } else {
            Say "Kept: $Data (a reinstall picks it up again)."
        }
    }
    Say ""
    Say "Toolbelt is uninstalled." "Yellow"
}

if ($Uninstall) { Uninstall-Toolbelt } else { Install-Toolbelt }
