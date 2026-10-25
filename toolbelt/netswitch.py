r"""The internet switch (his ask, 17 Oct: "sometimes I have to test something and turn my internet off, but it's annoying
to unplug my internet cable"). It switches his Ethernet adapter off and on, like pulling the cable.

Windows only lets an administrator switch adapters, so the setup (once, with his OK and one admin prompt) makes two
scheduled tasks in Task Scheduler's \Toolbelt\ folder: "Internet off" and "Internet on". Each holds its whole command
inside the task itself (no script file anywhere), and only an administrator can change a task, so nothing else on the
PC can use them to get admin rights. Toolbelt then just starts one of them with `schtasks /run`: no prompt, no internet
needed (turning it back on works while offline). Removing them takes one admin prompt too.
"""
import re
import subprocess
import tempfile
import time
from pathlib import Path

import psutil

NO_WINDOW = 0x08000000
FOLDER = "\\Toolbelt\\"
TASKS = {False: "Internet off", True: "Internet on"}
SAFE_NAME = re.compile(r"^[\w .()\-]{1,80}$")


def _ps(command, timeout=20):
    done = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", command], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout, creationflags=NO_WINDOW)
    return done.stdout.strip()


def adapters():
    """The real network adapters (not virtual ones): [{name, status: Up / Disconnected / Disabled, what}]."""
    out = _ps("Get-NetAdapter -Physical | ForEach-Object { $_.Name + '|' + $_.Status + '|' + $_.InterfaceDescription }")
    found = []
    for line in out.splitlines():
        parts = line.split("|")
        if len(parts) == 3 and SAFE_NAME.match(parts[0]):
            found.append({"name": parts[0], "status": parts[1], "what": parts[2]})
    return found


def pick_adapter():
    """His Ethernet (the one in use, else the first wired one, else the first one)."""
    found = adapters()
    for want in (lambda a: a["status"] == "Up", lambda a: "ethernet" in (a["name"] + a["what"]).lower(), lambda a: True):
        for a in found:
            if want(a):
                return a["name"]
    return ""


def state(name):
    """"on", "nocable" (switched on but no connection: unplugged or the router is off) or "off" (switched off).
    psutil answers instantly; only when the adapter isn't up does Windows get asked which of the two it is."""
    stats = psutil.net_if_stats().get(name)
    if stats is not None and stats.isup:
        return "on"
    status = _ps("(Get-NetAdapter -Name '%s' -ErrorAction SilentlyContinue).Status" % name) if SAFE_NAME.match(name or "") else ""
    return "off" if status == "Disabled" else "nocable" if status else "off"


def _task_adapter(on):
    """The adapter name written inside a task, or "" when the task isn't there."""
    done = subprocess.run(["schtasks", "/query", "/tn", FOLDER + TASKS[on], "/xml"], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=15, creationflags=NO_WINDOW)
    if done.returncode != 0:
        return ""
    m = re.search(r"-NetAdapter -Name '([^']+)'", done.stdout)
    return m.group(1) if m else ""


def installed():
    """The adapter both tasks switch, or "" when the setup hasn't been done (or one task is missing)."""
    a, b = _task_adapter(False), _task_adapter(True)
    return a if a and a == b else ""


SETUP = r"""
$ErrorActionPreference = 'Stop'
$user = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 2) -MultipleInstances IgnoreNew
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Highest
foreach ($t in @(@('Internet off', 'Disable'), @('Internet on', 'Enable'))) {
  $cmd = $t[1] + "-NetAdapter -Name 'ADAPTER' -Confirm:`$false"
  $action = New-ScheduledTaskAction -Execute 'conhost.exe' -Argument ('--headless powershell.exe -NoProfile -NonInteractive -WindowStyle Hidden -Command "' + $cmd + '"')
  Register-ScheduledTask -TaskPath '\Toolbelt\' -TaskName $t[0] -Action $action -Principal $principal -Settings $settings -Description 'Toolbelt internet switch: switches the network adapter ADAPTER off or on.' -Force | Out-Null
}
"""

REMOVE = r"""
foreach ($n in @('Internet off', 'Internet on')) { Unregister-ScheduledTask -TaskPath '\Toolbelt\' -TaskName $n -Confirm:$false -ErrorAction SilentlyContinue }
"""


def _elevated(script, timeout=180):
    """Runs a PowerShell script as administrator (Windows shows its admin prompt). True when it ran and finished."""
    tmp = Path(tempfile.mkdtemp(prefix="toolbelt-net-")) / "run.ps1"
    tmp.write_text(script, encoding="utf-8-sig")
    try:
        outer = ("try { $p = Start-Process powershell.exe -Verb RunAs -Wait -PassThru -WindowStyle Hidden "
                 "-ArgumentList '-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File','\"%s\"'; exit $p.ExitCode } catch { exit 1223 }" % tmp)
        done = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", outer], capture_output=True, timeout=timeout, creationflags=NO_WINDOW)
        return done.returncode
    finally:
        try:
            tmp.unlink()
            tmp.parent.rmdir()
        except OSError:
            pass


def setup(name=None):
    name = name or pick_adapter()
    if not SAFE_NAME.match(name or ""):
        return {"ok": False, "message": "Toolbelt couldn't find your network adapter."}
    code = _elevated(SETUP.replace("ADAPTER", name))
    if installed() == name:
        return {"ok": True, "message": "The internet switch is ready for %s. From now on it works without a prompt." % name, "adapter": name}
    return {"ok": False, "message": "Windows' admin prompt was turned down, so nothing was set up." if code == 1223 else "The setup didn't finish (code %s)." % code}


def remove():
    _elevated(REMOVE)
    gone = not installed()
    return {"ok": gone, "message": "The internet switch is removed from Task Scheduler." if gone else "It's still there (was the admin prompt turned down?)."}


def switch(on, wait=10.0):
    """Starts the task; then waits (up to `wait` s) until Windows shows the adapter on or off. Works offline."""
    name = installed()
    if not name:
        return {"ok": False, "message": "Set up the internet switch first (one admin prompt).", "setup": True}
    done = subprocess.run(["schtasks", "/run", "/tn", FOLDER + TASKS[bool(on)]], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=15, creationflags=NO_WINDOW)
    if done.returncode != 0:
        return {"ok": False, "message": "Windows didn't start the switch: " + (done.stderr or done.stdout).strip()[:160]}
    end = time.time() + wait
    now = state(name)
    while time.time() < end:
        if (now == "on") if on else (now == "off"):
            return {"ok": True, "state": now, "message": "Internet back on" if on else "Internet off"}
        time.sleep(0.4)
        now = state(name)
    if on and now == "nocable":                                   # switched on, but no link (yet): unplugged or router off
        return {"ok": True, "state": now, "message": "Switched on, but there's no connection yet: is the cable in and the router on?"}
    return {"ok": False, "state": now, "message": "Windows hasn't switched it yet; give it a moment."}
