@echo off
rem Builds ToolbeltSetup.exe with Windows' own C# compiler (.NET Framework 4, part of Windows: nothing to install).
rem The exe isn't kept in git: it goes to a GitHub Release as a download.
setlocal
set CSC=%WINDIR%\Microsoft.NET\Framework64\v4.0.30319\csc.exe
if not exist "%CSC%" set CSC=%WINDIR%\Microsoft.NET\Framework\v4.0.30319\csc.exe
"%CSC%" /nologo /target:exe /platform:anycpu /optimize+ /r:System.IO.Compression.dll /r:System.IO.Compression.FileSystem.dll /win32icon:"%~dp0..\web\icons\toolbelt-cartridge.ico" /out:"%~dp0ToolbeltSetup.exe" "%~dp0ToolbeltSetup.cs"
