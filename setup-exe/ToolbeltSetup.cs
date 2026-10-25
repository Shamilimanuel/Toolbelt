// ToolbeltSetup.exe (25 Oct 2026, his ask "can we also make a exe"): a small setup program. It downloads Toolbelt's
// code from GitHub (main.zip) into %TEMP%, unpacks it and runs its setup.ps1 (Python, the app in
// %LOCALAPPDATA%\Programs\Toolbelt, its packages, Settings > Apps), then cleans up and waits for Enter.
// It deliberately does NOT run "irm ... | iex": Defender blocks an unknown program starting PowerShell that way
// (Trojan:Win32/Commando.A!ml, seen 25 Oct), and rightly so. It always fetches the newest code, so it never needs
// rebuilding for a new Toolbelt version. Build: setup-exe\build.cmd (Windows' own C# compiler, nothing to install).
// TOOLBELT_SETUP_ARGS (separated by |) passes extra arguments to setup.ps1; Toolbelt's own test uses it.
using System;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Net;
using System.Reflection;

[assembly: AssemblyTitle("Toolbelt Setup")]
[assembly: AssemblyDescription("Downloads Toolbelt from github.com/Shamilimanuel/Toolbelt and installs it for this Windows user")]
[assembly: AssemblyCompany("Shamilimanuel")]
[assembly: AssemblyProduct("Toolbelt")]
[assembly: AssemblyCopyright("MIT licence, Shamilimanuel")]
[assembly: AssemblyVersion("1.0.1.0")]
[assembly: AssemblyFileVersion("1.0.1.0")]

static class ToolbeltSetup
{
    const string Zip = "https://github.com/Shamilimanuel/Toolbelt/archive/refs/heads/main.zip";

    static int Main(string[] args)
    {
        Console.Title = "Toolbelt setup";
        Console.WriteLine("Toolbelt setup");
        Console.WriteLine("Downloads Toolbelt from github.com/Shamilimanuel/Toolbelt and installs it for this Windows user.");
        Console.WriteLine();
        string work = Path.Combine(Path.GetTempPath(), "toolbelt-setup-" + Guid.NewGuid().ToString("N").Substring(0, 8));
        int code = 1;
        try
        {
            Console.WriteLine("Downloading...");
            ServicePointManager.SecurityProtocol |= SecurityProtocolType.Tls12;
            Directory.CreateDirectory(work);
            string zip = Path.Combine(work, "toolbelt.zip");
            using (var web = new WebClient())
            {
                web.Headers.Add("User-Agent", "ToolbeltSetup/1.0");
                web.DownloadFile(Zip, zip);
            }
            string unpacked = Path.Combine(work, "code");
            ZipFile.ExtractToDirectory(zip, unpacked);
            string setup = Directory.GetDirectories(unpacked).Select(d => Path.Combine(d, "setup.ps1")).FirstOrDefault(File.Exists);
            if (setup == null) throw new Exception("the download has no setup.ps1");

            string extra = "";
            string fromEnv = Environment.GetEnvironmentVariable("TOOLBELT_SETUP_ARGS");
            if (!string.IsNullOrEmpty(fromEnv))
                extra = string.Join(" ", fromEnv.Split('|').Select(a => a.StartsWith("-") ? a : "\"" + a + "\""));
            var start = new ProcessStartInfo(Path.Combine(Environment.SystemDirectory, @"WindowsPowerShell\v1.0\powershell.exe"),
                "-NoProfile -ExecutionPolicy Bypass -File \"" + setup + "\" " + extra) { UseShellExecute = false };
            using (var ps = Process.Start(start))
            {
                ps.WaitForExit();
                code = ps.ExitCode;
            }
        }
        catch (Exception error)
        {
            Console.WriteLine();
            Console.WriteLine("Toolbelt couldn't be installed: " + error.Message);
        }
        finally
        {
            try { Directory.Delete(work, true); } catch { }
        }
        if (Array.IndexOf(args, "--no-pause") < 0)
        {
            Console.WriteLine();
            Console.Write("Press Enter to close this window.");
            Console.ReadLine();
        }
        return code;
    }
}
