"""App guard's scans (18 Oct) for real, on made-up files in a temporary folder with its own guard.json: the checks on a
disguised program, a worm-style shortcut, an unsigned download and a signed program; Defender scanning a folder; a
new download being noticed; a "USB stick" (a folder) being checked; Trust / Quarantine from a scan."""
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "toolbelt"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import appguard                                                # noqa: E402
import guardscan                                               # noqa: E402

failures = []


def expect(label, condition):
    print(("ok    " if condition else "FAIL  ") + label)
    if not condition:
        failures.append(label)


tmp = Path(tempfile.mkdtemp(prefix="toolbelt-gscan-"))
cmd = Path(r"C:\Windows\System32\cmd.exe")
try:
    box = tmp / "box"
    box.mkdir()
    shutil.copy(cmd, box / "photo.jpg.exe")
    import brand                                               # an unsigned program: Python's launcher with an icon written in breaks its signature
    shutil.copy(Path(sys.executable).with_name("pythonw.exe"), box / "tool.exe")
    brand._put_icon(box / "tool.exe", brand.icon_path("cartridge"))
    Path(str(box / "tool.exe") + ":Zone.Identifier").write_text("[ZoneTransfer]\nZoneId=3\nHostUrl=https://dl.example.test/tool.exe\n", encoding="utf-8")
    shutil.copy(Path(sys.executable).with_name("pythonw.exe"), box / "signed.exe")
    (box / "notes.txt").write_text("just text", encoding="utf-8")
    subprocess.run(["powershell", "-NoProfile", "-Command", "$s=(New-Object -ComObject WScript.Shell).CreateShortcut('%s'); $s.TargetPath='%s'; $s.Save()" % (box / "Holiday photos.lnk", cmd)],
                   check=True, creationflags=0x08000000)
    files = [("Test", f) for f in guardscan._walk(box, 2, 100) if guardscan.interesting(f)]
    expect("only programs, shortcuts and disguised files are looked at (not notes.txt)", sorted(f.name for _, f in files) == ["Holiday photos.lnk", "photo.jpg.exe", "signed.exe", "tool.exe"])
    found, fine = guardscan.check_files(None, files)
    by = {f["name"]: f for f in found}
    expect("a disguised program (photo.jpg.exe) is DANGER", by.get("photo.jpg.exe", {}).get("verdict") == "danger")
    expect("a shortcut that starts cmd.exe is DANGER (the USB worm trick)", by.get("Holiday photos.lnk", {}).get("verdict") == "danger" and "cmd.exe" in by["Holiday photos.lnk"]["checks"][0][1])
    expect("an unsigned program from the internet is listed, with its site", by.get("tool.exe", {}).get("verdict") == "unknown" and any("dl.example.test" in c[1] for c in by["tool.exe"]["checks"]))
    expect("a validly signed program counts as fine (%d fine)" % fine, "signed.exe" not in by and fine >= 1)
    sig = guardscan.signatures([box / "signed.exe", box / "tool.exe"])
    expect("signatures for many files in one go", sig[str(box / "signed.exe")]["status"] == "Valid" and sig[str(box / "tool.exe")]["status"] != "Valid")
    sample = ("Scanning C:\\x found 1 threats.\n<===========================LIST OF DETECTED THREATS==========================>\n"
              "----------------------------- Threat information ------------------------------\nThreat                  : Virus:DOS/EICAR_Test_File\n"
              "Resources               : 1 total\n    file                : C:\\x\\eicar.com\n")
    expect("Defender's threat list is read (name and file)", guardscan.parse_threats(sample) == [{"name": "Virus:DOS/EICAR_Test_File", "files": ["C:\\x\\eicar.com"]}])
    dv = guardscan.defender(None, "folder", box, remediate=False)
    expect("Defender scans a folder without admin and reports (clean here, %d s)" % dv["seconds"], dv["clean"] and not dv["threats"])

    # the watchers and the scans inside App guard, with its own record
    settings = {"guard_scan": False, "guard_signed": True, "guard_downloads": True, "guard_usb": True}
    asked = []
    g = appguard.Guard(lambda: settings, on_ask=lambda: asked.append(1), data_file=tmp / "guard.json", quarantine=tmp / "quarantine")
    dl = tmp / "Downloads"
    dl.mkdir()
    (dl / "old.zip").write_bytes(b"PK\x03\x04old")
    g._dl_folder = dl
    g._watch_downloads()
    expect("files already in Downloads aren't new", g.data["downloads"] == [])
    shutil.copy(cmd, dl / "invoice.pdf.exe")
    (dl / "big.crdownload").write_bytes(b"x")
    g._watch_downloads()
    g._watch_downloads()
    end = time.time() + 20
    while time.time() < end and not g.data["downloads"]:
        time.sleep(0.3)
    d = g.data["downloads"][0] if g.data["downloads"] else {}
    expect("a new download is checked once it's complete (a half download is skipped)", d.get("name") == "invoice.pdf.exe" and len(g.data["downloads"]) == 1)
    expect("a risky download raises a note with Quarantine / Keep it", d.get("verdict") == "danger" and g.pending and g.pending[-1]["kind"] == "notice" and g.pending[-1]["actions"] == ["quarantine", "keep"])
    r = g.decide(g.pending[-1]["id"], "quarantine")
    expect("Quarantine from the note moves the download away", r["ok"] and not (dl / "invoice.pdf.exe").exists() and g.data["quarantine"])
    stick = tmp / "stick"
    stick.mkdir()
    (stick / "autorun.inf").write_text("[autorun]\nopen=run.exe\n", encoding="utf-8")
    shutil.copy(cmd, stick / "song.mp3.exe")
    finds = g.scan_usb(str(stick))
    names = {f["name"] for f in finds}
    expect("a USB stick: autorun.inf and the disguised program are found", {"autorun.inf", "song.mp3.exe"} <= names)
    expect("its result is kept as the USB stick scan and a note says so", g.data["scans"]["usb"]["findings"] and g.pending and g.pending[-1]["kind"] == "notice" and "show" in g.pending[-1]["actions"])
    r = g.decide(g.pending[-1]["id"], "show")
    expect("Show on the note asks Toolbelt to open the Scan tab", r.get("show") is True)
    g.save_scan("program", {"label": "Program check", "findings": found, "fine": fine})
    r = g.trust_path(str(box / "tool.exe"))
    expect("Trust from a scan: trusted, and gone from the results", r["ok"] and not any(f["name"] == "tool.exe" for f in g.data["scans"]["program"]["findings"]))
    r = g.quarantine_path(str(box / "photo.jpg.exe"))
    expect("Quarantine from a scan moves the file", r["ok"] and not (box / "photo.jpg.exe").exists())
    expect("removable drives can be listed", isinstance(guardscan.removable_drives(), list))
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print("ALL PASSED" if not failures else "%d FAILED" % len(failures))
sys.exit(1 if failures else 0)
