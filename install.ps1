# Toolbelt in one line (PowerShell):
#
#     irm https://raw.githubusercontent.com/Shamilimanuel/Toolbelt/main/install.ps1 | iex
#
# Downloads Toolbelt from GitHub into a temporary folder and runs its setup.ps1 there (that one does the real work:
# Python, the app in %LOCALAPPDATA%\Programs\Toolbelt, its packages, Settings > Apps). Run the same line again to update.
# setup.ps1 runs in its own PowerShell, so nothing here changes the window you pasted this into.
# (TOOLBELT_SETUP_ARGS, separated by |, passes extra arguments to setup.ps1; Toolbelt's own test uses it.)
& {
    $ErrorActionPreference = "Stop"
    $ProgressPreference = "SilentlyContinue"                    # Invoke-WebRequest is much faster without its progress bar
    [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
    $zipUrl = "https://github.com/Shamilimanuel/Toolbelt/archive/refs/heads/main.zip"
    $work = Join-Path $env:TEMP ("toolbelt-setup-" + [guid]::NewGuid().ToString("N").Substring(0, 8))
    $zip = "$work.zip"
    try {
        Write-Host "Downloading Toolbelt from GitHub..." -ForegroundColor Yellow
        Invoke-WebRequest -Uri $zipUrl -OutFile $zip -UseBasicParsing
        Expand-Archive -Path $zip -DestinationPath $work -Force
        $source = Get-ChildItem -Path $work -Directory | Select-Object -First 1
        $setup = Join-Path $source.FullName "setup.ps1"
        if (-not (Test-Path $setup)) { throw "The download has no setup.ps1." }
        $extra = @()
        if ($env:TOOLBELT_SETUP_ARGS) { $extra = $env:TOOLBELT_SETUP_ARGS -split '\|' }
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $setup @extra
    } catch {
        Write-Host "Toolbelt couldn't be installed: $($_.Exception.Message)" -ForegroundColor Red
    } finally {
        Remove-Item -Recurse -Force -Path $work, $zip -ErrorAction SilentlyContinue
    }
}
