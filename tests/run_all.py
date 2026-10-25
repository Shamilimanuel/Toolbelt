"""Runs every Toolbelt test. No window ever appears: the page runs in an invisible Chrome and the real window starts hidden.

    python tests\\run_all.py        (-v shows each test's own lines)

A suite only counts as passed when it prints its own "ALL PASSED" line, so a crash can never look like a pass.
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
VENV = Path(os.environ["LOCALAPPDATA"]) / "Toolbelt" / "venv" / "Scripts" / "python.exe"
verbose = "-v" in sys.argv
failed = False
sys.stdout.reconfigure(encoding="utf-8", errors="replace")     # a suite's output may hold characters cp1252 can't print


def run(label, command):
    global failed
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
    good = result.returncode == 0 and "ALL PASSED" in result.stdout
    failed |= not good
    print(("PASS  " if good else "FAIL  ") + label)
    if verbose or not good:
        for line in (result.stdout + ("" if good else result.stderr)).strip().splitlines():
            print("    " + line)


run("test_engine.py (settings, jobs, engines)", [str(VENV), str(HERE / "test_engine.py")])
run("test_downloader.py (downloader, installer checks, Spotify, no internet)", [str(VENV), str(HERE / "test_downloader.py")])
run("test_cutout.py (cut-outs, backgrounds, Discord sizes, one real cut-out on the GPU)", [str(VENV), str(HERE / "test_cutout.py")])
run("test_home.py (Home: notes, projects, launch targets on this PC, adding apps)", [str(VENV), str(HERE / "test_home.py")])
run("test_colours.py (saved gradients, a picture's colours)", [str(VENV), str(HERE / "test_colours.py")])
run("test_brand.py (the logo, the .ico files, the Start-menu shortcut)", [str(VENV), str(HERE / "test_brand.py")])
run("test_playnite.py (Playnite's LiteDB v4 games.db, read-only)", [str(VENV), str(HERE / "test_playnite.py")])
run("test_games.py (Steam's files, HoYoPlay, merging, the jump list under a test identity)", [str(VENV), str(HERE / "test_games.py")])
run("test_page_popup.py (the tray pop-up page)", [sys.executable, str(HERE / "test_page_popup.py")])
run("test_gameart.py (game art in HD: which pictures, the cache, two real upscales in the background)", [str(VENV), str(HERE / "test_gameart.py")])
run("test_page_games.py (the game library screen, start to finish)", [sys.executable, str(HERE / "test_page_games.py")])
run("test_calc.py (the maths engine: exact fractions, roots, powers, tables, equations)", [sys.executable, str(HERE / "test_calc.py")])
run("test_page_calc.py (the Calculator screen, start to finish)", [sys.executable, str(HERE / "test_page_calc.py")])
run("test_page_calcpop.py (the floating mini calculator)", [sys.executable, str(HERE / "test_page_calcpop.py")])
run("test_check.py (fingerprints, signatures, compare, folder lists, what-is-it-really)", [str(VENV), str(HERE / "test_check.py")])
run("test_page_check.py (the Check a file screen)", [sys.executable, str(HERE / "test_page_check.py")])
run("test_pccare.py (installed programs, startup entries, restore points)", [str(VENV), str(HERE / "test_pccare.py")])
run("test_leftscan.py (Revo-style leftover scan: 3 modes, the rails, a real round trip with backups)", [str(VENV), str(HERE / "test_leftscan.py")])
run("test_hotkey.py (Win+T: the rules, the keyboard hook in and out)", [str(VENV), str(HERE / "test_hotkey.py")])
run("test_drivers_ping.py (drivers and the board from Windows, real pings, the lag verdict)", [str(VENV), str(HERE / "test_drivers_ping.py")])
run("test_page_pc.py (the Uninstall and PC care screens, start to finish)", [sys.executable, str(HERE / "test_page_pc.py")])
run("test_media.py (ffmpeg: convert, compress, clips, pictures; Real-ESRGAN: picture, GIF, video)", [str(VENV), str(HERE / "test_media.py")])
run("test_dialogs.py (every file picker's filter is one pywebview accepts)", [str(VENV), str(HERE / "test_dialogs.py")])
run("test_viewer.py (videos inside Toolbelt: byte ranges, only known files)", [str(VENV), str(HERE / "test_viewer.py")])
run("test_page_player.py (the player: cut while watching, full window, before / after, playable copy)", [sys.executable, str(HERE / "test_page_player.py")])
run("test_page_media.py (the Media screen, start to finish)", [sys.executable, str(HERE / "test_page_media.py")])
run("test_finish.py (rename many files, QR codes, crop / many pictures / HEIC, sound, subtitles with whisper.cpp, Wallpaper Engine, Fix all songs)", [str(VENV), str(HERE / "test_finish.py")])
run("test_page_finish.py (Handy tools, the new Media tabs, Fix all songs, the Wallpaper Engine picker)", [sys.executable, str(HERE / "test_page_finish.py")])
run("test_netswitch.py (the internet switch: the adapter, the two tasks, never switching anything)", [str(VENV), str(HERE / "test_netswitch.py")])
run("test_page_net.py (the internet switch's button: set up, off, on, no connection)", [sys.executable, str(HERE / "test_page_net.py")])
run("test_appguard.py (App guard for real on a hidden copy of cmd.exe: notice, checks, stop, quarantine, restore, trust)", [str(VENV), str(HERE / "test_appguard.py")])
run("test_guardscan.py (App guard scans: the checks, a worm shortcut, Defender on a folder, a new download, a USB stick)", [str(VENV), str(HERE / "test_guardscan.py")])
run("test_page_guard.py (the App guard screen and its warning window)", [sys.executable, str(HERE / "test_page_guard.py")])
run("test_page.py (the page, 3 looks, 2 window sizes)", [sys.executable, str(HERE / "test_page.py")])
run("test_page_colours.py (the Colours screen; codes identical to the prototype's)", [sys.executable, str(HERE / "test_page_colours.py")])
run("test_page_home.py (the Home screen, start to finish)", [sys.executable, str(HERE / "test_page_home.py")])
run("test_page_cutout.py (the Cut out screen, start to finish)", [sys.executable, str(HERE / "test_page_cutout.py")])
run("test_page_download.py (the Download screen, start to finish)", [sys.executable, str(HERE / "test_page_download.py")])

# the real window, started hidden: every screen opens, a job runs, and nothing listens on a port
out = Path(tempfile.gettempdir()) / "toolbelt_selftest.json"
out.unlink(missing_ok=True)
subprocess.run([str(VENV), str(ROOT / "main.py"), "--hidden", "--selftest", str(out)], cwd=ROOT, timeout=120)
result = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {"ok": False, "error": "no result"}
good = bool(result.get("ok")) and not result.get("errors")
failed |= not good
print(("PASS  " if good else "FAIL  ") + "hidden window (real pywebview, real Python side)")
if verbose or not good:
    print("    " + json.dumps(result, indent=2).replace("\n", "\n    "))

print()
print("SOME TESTS FAILED" if failed else "ALL SUITES PASSED")
sys.exit(1 if failed else 0)
