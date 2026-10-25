"""App guard (18 Oct) for real, on harmless stand-ins in a temporary folder: a copy of Windows' own cmd.exe started
hidden plays "a new program". The watcher must notice it, the checks must read signatures, disguised names and
downloads correctly, and Stop it must end the program and quarantine the file (then Restore / Delete).
Uses its own guard.json and quarantine folder; Toolbelt's real ones are never touched."""
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

failures = []


def expect(label, condition):
    print(("ok    " if condition else "FAIL  ") + label)
    if not condition:
        failures.append(label)


tmp = Path(tempfile.mkdtemp(prefix="toolbelt-guard-"))
cmd = Path(r"C:\Windows\System32\cmd.exe")
prog = tmp / "newtool.exe"
shutil.copy(cmd, prog)
procs = []


def launch(path):
    """A hidden copy of cmd.exe that waits ~30 s (no window: CREATE_NO_WINDOW)."""
    p = subprocess.Popen([str(path), "/c", "ping -n 30 127.0.0.1 >nul"], creationflags=0x08000000)
    procs.append(p)
    return p


try:
    # ---------- the checks, on real files ----------
    signed = appguard.inspect(Path(sys.executable).with_name("pythonw.exe"), scan=False)
    expect("a validly signed program looks safe (pythonw.exe: %s)" % signed["signer"], signed["verdict"] == "safe" and signed["signed"])
    fake = tmp / "invoice.pdf.exe"
    shutil.copy(cmd, fake)
    r = appguard.inspect(fake, scan=False)
    expect("a disguised name (invoice.pdf.exe) is DANGER even when signed", r["verdict"] == "danger" and any(c[0] == "bad" and ".pdf" in c[1] for c in r["checks"]))
    (Path(str(prog) + ":Zone.Identifier")).write_text("[ZoneTransfer]\nZoneId=3\nHostUrl=https://files.example.test/newtool.exe\n", encoding="utf-8")
    web = appguard.mark_of_the_web(prog)
    expect("the Mark of the Web says where a download came from", web == {"internet": True, "site": "files.example.test"})
    expect("a file made on this PC has no Mark of the Web", appguard.mark_of_the_web(fake)["internet"] is False)
    clean = tmp / "clean.txt"
    clean.write_text("hello", encoding="utf-8")
    d = appguard.defender_scan(clean)
    expect("Defender scans one file without admin and finds nothing", d == {"ran": True, "threat": ""})

    # ---------- the watcher, for real ----------
    asked = []
    unsigned = {"verdict": "unknown", "checks": [["warn", "Not signed"]], "signed": False, "signer": "", "threat": ""}
    settings = {"guard_scan": False, "guard_signed": True}
    g = appguard.Guard(lambda: settings, on_ask=lambda: asked.append(1), data_file=tmp / "guard.json", quarantine=tmp / "quarantine",
                       inspector=lambda path, scan=True: unsigned)
    g.start()
    time.sleep(2.5)
    expect("first start: what already runs becomes the known baseline (%d programs)" % len(g.data["known"]), g.data["baseline"] and len(g.data["known"]) > 5)
    expect("Windows' own programs are never judged", not any(k.startswith(str(appguard.WINDIR).lower()) for k in g.data["known"]))
    p = launch(prog)
    end = time.time() + 8
    while time.time() < end and not g.pending:
        time.sleep(0.2)
    expect("a new program is noticed within seconds and a question waits", len(g.pending) == 1 and g.pending[0]["name"] == "newtool.exe" and asked)
    q = g.pending[0]
    r = g.decide(q["id"], "stop")
    time.sleep(0.5)
    expect("Stop it ends the program", p.poll() is not None)
    expect("and moves its file to quarantine with .blocked added", not prog.exists() and len(g.data["quarantine"]) == 1 and g.data["quarantine"][0]["stored"].endswith(".blocked"))
    r = g.restore(g.data["quarantine"][0]["id"])
    expect("Restore puts it back where it was", r["ok"] and prog.exists() and not g.data["quarantine"])
    p = launch(prog)
    end = time.time() + 8
    while time.time() < end and not g.pending:
        time.sleep(0.2)
    expect("after Restore it's asked about again", len(g.pending) == 1)
    g.decide(g.pending[0]["id"], "trust")
    p2 = launch(prog)
    time.sleep(2.5)
    expect("Trust it: started again, no question", not g.pending and g.data["trusted"][0]["name"] == "newtool.exe")
    expect("Forget makes it a question again", g.forget(str(prog))["ok"] and not g.data["trusted"])
    for x in procs:
        x.kill()
    signed_inspector = {"verdict": "safe", "checks": [["ok", "Signed"]], "signed": True, "signer": "Someone Inc.", "threat": ""}
    g._inspect = lambda path, scan=True: signed_inspector
    other = tmp / "signedtool.exe"
    shutil.copy(cmd, other)
    launch(other)
    time.sleep(2.5)
    expect("a signed program goes through by itself and is logged", not g.pending and any("signedtool.exe" in l["what"] and "let through" in l["what"] for l in g.data["log"]))
    g.stop()
    g2 = appguard.Guard(lambda: settings, data_file=tmp / "guard.json", quarantine=tmp / "quarantine")
    expect("everything is remembered in guard.json", g2.data["baseline"] and any("signedtool" in k for k in g2.data["known"]))
    # delete from quarantine goes to the Recycle Bin: tested on a stand-in record so nothing real is binned
    q2 = tmp / "quarantine" / "x.blocked"
    q2.parent.mkdir(exist_ok=True)
    q2.write_text("x", encoding="utf-8")
    g.data["quarantine"].append({"id": "qtest", "name": "x.exe", "original": str(tmp / "x.exe"), "stored": str(q2), "when": "", "why": ""})
    import leftscan
    binned, real_recycle = [], leftscan.recycle
    leftscan.recycle = lambda path: (binned.append(path), Path(path).unlink(), 0)[2]   # a stand-in: his real Recycle Bin stays as it is
    try:
        r = g.delete("qtest")
    finally:
        leftscan.recycle = real_recycle
    expect("Delete hands the quarantined file to the Recycle Bin", r["ok"] and binned == [str(q2)] and not g._quarantined("qtest"))
finally:
    for x in procs:
        try:
            x.kill()
        except OSError:
            pass
    time.sleep(0.5)
    shutil.rmtree(tmp, ignore_errors=True)

print("ALL PASSED" if not failures else "%d FAILED" % len(failures))
sys.exit(1 if failures else 0)
