"""App guard (his ask, 18 Oct; prototype docs/appguard.html, "Good, build it"): watches for programs starting that it
hasn't seen before, checks them, and asks him: Trust it / Just this time / Stop it.

How it works:
- Every second it compares the running programs with the ones it saw last time (psutil; no admin, no driver). A new
  program's file is checked in a worker thread while the program keeps running: App guard warns, it can't stop a
  program *before* it starts (that needs a kernel driver; Smart App Control does that part).
- Checks: who signed it (Windows' own signature check, check.signature), a disguised name like invoice.pdf.exe
  (check.sniff), where it came from (the "Mark of the Web" Windows writes on downloads: Zone.Identifier), and a
  Microsoft Defender scan of that one file (MpCmdRun, no admin).
- Left alone: Windows' own folder, Toolbelt's own folder in AppData (its engines are fingerprint-checked), programs
  already running when App guard first started (the baseline), programs he trusted, and (setting) validly signed ones.
- Stop it = end the program (and its children), then move its file to %LOCALAPPDATA%/Toolbelt/quarantine with
  ".blocked" added, so it can't be started by accident. Restore puts it back; Delete sends it to the Recycle Bin.
Everything is kept in %LOCALAPPDATA%/Toolbelt/guard.json. Nothing is uploaded.
"""
import json
import os
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path

import psutil

from settings import DATA

NO_WINDOW = 0x08000000
DATA_FILE = DATA / "guard.json"
QUARANTINE = DATA / "quarantine"
WINDIR = Path(os.environ.get("SystemRoot", r"C:\Windows")).resolve()
DEFENDER = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Windows Defender" / "MpCmdRun.exe"
LOG_KEEP = 300


def now():
    return time.strftime("%Y-%m-%d %H:%M")


def mark_of_the_web(path):
    """Where a download came from: Windows writes a hidden note (Zone.Identifier) on files from the internet."""
    try:
        text = Path(str(path) + ":Zone.Identifier").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {"internet": False, "site": ""}
    zone = re.search(r"ZoneId=(\d)", text)
    url = re.search(r"(?:HostUrl|ReferrerUrl)=(\S+)", text)
    site = ""
    if url:
        m = re.match(r"https?://([^/]+)", url.group(1))
        site = m.group(1) if m else ""
    return {"internet": bool(zone and zone.group(1) in ("3", "4")), "site": site}


def defender_scan(path, timeout=120):
    """Microsoft Defender's verdict on one file: {"ran": bool, "threat": name or ""}. Nothing is removed by this scan."""
    if not DEFENDER.exists():
        return {"ran": False, "threat": ""}
    try:
        done = subprocess.run([str(DEFENDER), "-Scan", "-ScanType", "3", "-File", str(path), "-DisableRemediation"], capture_output=True,
                              text=True, encoding="utf-8", errors="replace", timeout=timeout, creationflags=NO_WINDOW)
    except (OSError, subprocess.TimeoutExpired):
        return {"ran": False, "threat": ""}
    if done.returncode == 2:
        m = re.search(r"Threat\s*:\s*(.+)", done.stdout)
        return {"ran": True, "threat": (m.group(1).strip() if m else "a known threat")[:120]}
    return {"ran": done.returncode == 0, "threat": ""}


def inspect(path, scan=True, signature=None, sniff=None):
    """The checks for one program file and a verdict: safe / unknown / danger. signature / sniff can be passed in (tests)."""
    import check
    sig = (signature or check.signature)(path)
    sn = (sniff or check.sniff)(path)
    web = mark_of_the_web(path)
    dv = defender_scan(path) if scan else {"ran": False, "threat": ""}
    checks = []
    status = sig.get("status", "")
    if status == "Valid":
        checks.append(["ok", "Signed by %s (valid)" % (sig.get("signer") or "a known publisher")])
    elif status in ("HashMismatch", "NotTrusted"):
        checks.append(["bad", sig.get("title", "Signature problem")])
    else:
        checks.append(["warn", "Not signed" + ("" if web["internet"] else " (normal for your own programs)")])
    if sn.get("verdict") == "danger":
        checks.append(["bad", sn.get("advice") or "Its name is a disguise"])
    else:
        checks.append(["ok", "Name and file type match"])
    if web["internet"]:
        checks.append(["warn", "Downloaded from " + (web["site"] or "the internet")])
    else:
        checks.append(["ok", "Not downloaded (made or copied on this PC)"])
    if dv["threat"]:
        checks.append(["bad", "Defender: " + dv["threat"]])
    elif dv["ran"]:
        checks.append(["ok", "Defender: nothing found"])
    else:
        checks.append(["warn", "Defender scan skipped"])
    if any(c[0] == "bad" for c in checks):
        verdict = "danger"
    elif status == "Valid":
        verdict = "safe"
    else:
        verdict = "unknown"
    return {"verdict": verdict, "checks": checks, "signed": status == "Valid", "signer": sig.get("signer", ""), "threat": dv["threat"]}


def _key(path):
    return str(path).lower()


class Guard:
    """The watcher. settings() returns Toolbelt's settings; on_ask() is called when a question is waiting."""

    def __init__(self, settings, on_ask=None, data_file=DATA_FILE, quarantine=QUARANTINE, skip_dirs=(), inspector=inspect):
        self._settings, self._on_ask, self._file, self._qdir = settings, on_ask, Path(data_file), Path(quarantine)
        self._inspect = inspector
        self._skip = [WINDIR] + [Path(d).resolve() for d in skip_dirs]
        self._lock = threading.Lock()
        self._seen_pids, self._once, self._busy = set(), set(), set()
        self.pending = []                                      # questions waiting for him, oldest first
        self._ids = 0
        self._stop = threading.Event()
        self._thread = None
        self.data = self._load()

    # ---------- the record ----------
    def _load(self):
        try:
            data = json.loads(self._file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        return {"known": dict(data.get("known") or {}), "trusted": list(data.get("trusted") or []), "quarantine": list(data.get("quarantine") or []),
                "log": list(data.get("log") or []), "baseline": bool(data.get("baseline")),
                "scans": dict(data.get("scans") or {}), "downloads": list(data.get("downloads") or [])}

    def _save(self):
        self._file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._file.with_suffix(".tmp")
        with self._lock:
            tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, self._file)

    def log(self, what):
        with self._lock:
            self.data["log"].insert(0, {"t": now(), "what": what})
            del self.data["log"][LOG_KEEP:]

    # ---------- watching ----------
    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="appguard")
        self._thread.start()

    def stop(self):
        self._stop.set()

    def running(self):
        return bool(self._thread and self._thread.is_alive() and not self._stop.is_set())

    def _run(self):
        self._seen_pids = set(psutil.pids())
        if not self.data["baseline"]:                          # first start ever: what runs now is his normal, never asked about
            for pid in self._seen_pids:
                path = self._exe(pid)
                if path and not self._skipped(path):
                    self.data["known"][_key(path)] = {"how": "baseline", "when": now()}
            self.data["baseline"] = True
            self.log("App guard started: %d programs that were already running count as known" % len(self.data["known"]))
            self._save()
        tick = 0
        while not self._stop.wait(1.0):
            try:
                pids = set(psutil.pids())
            except Exception:
                continue
            for pid in pids - self._seen_pids:
                path = self._exe(pid)
                if path:
                    self.consider(pid, path)
            self._seen_pids = pids
            tick += 1
            if tick % 2 == 0:                                   # every 2 s: new downloads and USB sticks (18 Oct)
                try:
                    self._watch_downloads()
                    self._watch_drives()
                except Exception as error:                     # a watcher hiccup must never stop App guard
                    self.log("watcher hiccup: %s" % str(error)[:80])

    # ---------- Downloads and USB sticks (18 Oct) ----------
    def _watch_downloads(self):
        import guardscan
        if not self._settings().get("guard_downloads", True):
            return
        folder = getattr(self, "_dl_folder", None) or guardscan.known_folder("downloads")
        self._dl_folder = folder
        if not folder or not Path(folder).is_dir():
            return
        now_files = {}
        for entry in os.scandir(folder):
            if entry.is_file(follow_symlinks=False) and Path(entry.name).suffix.lower() not in guardscan.PARTIAL:
                try:
                    st = entry.stat()
                    now_files[entry.path] = (st.st_size, st.st_mtime)
                except OSError:
                    pass
        before = getattr(self, "_dl_seen", None)
        if before is None:                                     # first look: what's there already isn't new
            self._dl_seen, self._dl_wait = now_files, {}
            return
        for path, sig in now_files.items():
            if before.get(path) == sig:
                continue
            if self._dl_wait.get(path) == sig:                 # unchanged for 2 s: the download is complete
                self._dl_wait.pop(path, None)
                before[path] = sig
                threading.Thread(target=self._check_download, args=(path,), daemon=True).start()
            else:
                self._dl_wait[path] = sig
        for path in list(before):
            if path not in now_files:
                before.pop(path)

    def _check_download(self, path):
        import check
        import guardscan
        p = Path(path)
        try:
            sniff = check.sniff(p)
            web = mark_of_the_web(p)
            dv = defender_scan(p)
            sig = guardscan.signatures([p]).get(str(p)) if p.suffix.lower() in guardscan.SIGNABLE else None
        except OSError:
            return
        checks = []
        if dv["threat"]:
            checks.append(["bad", "Defender: " + dv["threat"]])
        if sniff.get("verdict") == "danger":
            checks.append(["bad", sniff.get("advice") or "Its name is a disguise"])
        elif sniff.get("verdict") == "warn":
            checks.append(["warn", sniff.get("advice")])
        if sig:
            checks.append(["ok", "Signed by %s" % (sig["signer"] or "a known publisher")] if sig["status"] == "Valid" else ["warn", "A program that isn't signed"])
        checks.append(["warn" if web["internet"] else "ok", ("From " + web["site"]) if web["site"] else "Downloaded" if web["internet"] else "Not from the internet"])
        if dv["ran"] and not dv["threat"]:
            checks.append(["ok", "Defender: nothing found"])
        verdict = "danger" if any(c[0] == "bad" for c in checks) else "unknown" if sig and sig["status"] != "Valid" else "safe"
        rec = {"path": str(p), "name": p.name, "verdict": verdict, "checks": checks, "when": now(), "site": web["site"]}
        with self._lock:
            self.data["downloads"].insert(0, rec)
            del self.data["downloads"][100:]
        self.log("Download %s · %s" % (p.name, {"danger": "DANGER", "unknown": "a program that isn't signed", "safe": "looks fine"}[verdict]))
        if verdict == "danger":
            self.notice("Risky download: " + p.name, checks, "danger", path=str(p), actions=["quarantine", "keep"])
        self._save()

    def _watch_drives(self):
        import guardscan
        if not self._settings().get("guard_usb", True):
            return
        drives = set(guardscan.removable_drives())
        before = getattr(self, "_drives", None)
        self._drives = drives
        if before is None:
            return                                             # sticks already in when App guard started aren't "plugged in"
        for root in sorted(drives - before):
            threading.Thread(target=self.scan_usb, args=(root,), daemon=True).start()

    def scan_usb(self, root, job=None):
        """A stick was plugged in: its old tricks, App guard's checks on its programs, and a Defender scan that reports."""
        import guardscan
        label = guardscan.drive_label(root)
        self.log("USB stick %s (%s) plugged in · checking it" % (root, label))
        findings = guardscan.usb_tricks(root)
        files = [("USB stick", f) for f in guardscan._walk(root, 4, 20000) if guardscan.interesting(f)]
        more, fine = guardscan.check_files(job, files, self, scan=False, label="USB stick", span=50)
        findings += more
        dv = guardscan.defender(job, "folder", root, remediate=False)
        for t in dv["threats"]:
            for f in t["files"] or [root]:
                findings.insert(0, {"path": f, "name": Path(f).name, "place": "USB stick", "verdict": "danger", "size": 0, "checks": [["bad", "Defender: " + t["name"]]]})
        self.save_scan("usb", {"label": "USB stick %s (%s)" % (root, label), "findings": findings, "fine": fine, "threats": dv["threats"], "seconds": dv["seconds"]})
        bad = sum(1 for f in findings if f["verdict"] == "danger")
        lines = [["bad" if bad else "ok", "%d risky thing%s found" % (bad, "" if bad == 1 else "s") if bad else "Nothing risky found"],
                 ["ok", "%d program%s checked" % (len(files), "" if len(files) == 1 else "s")], ["ok" if not dv["threats"] else "bad", "Defender: " + ("nothing found" if not dv["threats"] else ", ".join(t["name"] for t in dv["threats"]))]]
        self.notice("USB stick %s (%s) checked" % (root, label), lines, "danger" if bad else "safe", actions=["show", "ok"])
        return findings

    # ---------- scans, notices, and acting on what a scan found ----------
    def save_scan(self, kind, result):
        result = dict(result, when=now(), kind=kind)
        with self._lock:
            self.data["scans"][kind] = result
        self.log("%s · %d to look at" % (result.get("label") or kind, len(result.get("findings") or [])))
        self._save()

    def notice(self, title, lines, verdict, path="", actions=("show", "ok")):
        """Something to tell him (not a running program): shown in the same window, with its own buttons."""
        with self._lock:
            self._ids += 1
            self.pending.append({"id": self._ids, "kind": "notice", "name": title, "path": path, "verdict": verdict, "checks": lines,
                                 "actions": list(actions), "when": now()})
        if self._on_ask:
            self._on_ask()

    def trust_path(self, path):
        p = Path(path)
        if any(_key(t["path"]) == _key(p) for t in self.data["trusted"]):
            return {"ok": True, "message": "%s was already trusted." % p.name}
        self.data["trusted"].insert(0, {"path": str(p), "name": p.name, "signed": False, "when": now()})
        self._drop_finding(p)
        self.log("%s · trusted from a scan" % p.name)
        self._save()
        return {"ok": True, "message": "%s is trusted." % p.name}

    def quarantine_path(self, path, why="you stopped it from a scan"):
        p = Path(path)
        if not p.is_file():
            return {"ok": False, "message": "That file isn't there any more."}
        msg = self._stop_and_quarantine({"name": p.name, "path": str(p), "checks": [["bad", why]]})
        self._drop_finding(p)
        self._save()
        return {"ok": True, "message": msg}

    def _drop_finding(self, p):
        with self._lock:
            for scan in self.data["scans"].values():
                scan["findings"] = [f for f in scan.get("findings") or [] if _key(f["path"]) != _key(p)]

    @staticmethod
    def _exe(pid):
        try:
            return psutil.Process(pid).exe() or ""
        except (psutil.Error, OSError):
            return ""                                         # gone already, or a protected system process: not ours to judge

    def _skipped(self, path):
        try:
            p = Path(path).resolve()
        except OSError:
            return True
        return any(p.is_relative_to(d) for d in self._skip)

    def consider(self, pid, path):
        """A new process: decide whether it needs a look (quick), then check it in its own thread."""
        key = _key(path)
        if self._skipped(path) or key in self._once or key in self._busy:
            return False
        if key in self.data["known"] or any(_key(t["path"]) == key for t in self.data["trusted"]):
            return False
        self._busy.add(key)
        threading.Thread(target=self._check, args=(pid, path), daemon=True).start()
        return True

    def _check(self, pid, path):
        key = _key(path)
        try:
            s = self._settings()
            result = self._inspect(path, scan=s.get("guard_scan", True))
            name = Path(path).name
            if result["verdict"] == "safe" and s.get("guard_signed", True):
                self.data["known"][key] = {"how": "signed", "signer": result["signer"], "when": now()}
                self.log("%s · signed by %s · let through by itself" % (name, result["signer"] or "a known publisher"))
                self._save()
                return
            with self._lock:
                self._ids += 1
                self.pending.append({"id": self._ids, "pid": pid, "path": str(path), "name": name, "verdict": result["verdict"], "checks": result["checks"],
                                     "signed": result["signed"], "when": now()})
            self.log("%s · %s · asked you" % (name, {"danger": "DANGER", "unknown": "unknown"}.get(result["verdict"], result["verdict"])))
            self._save()
            if self._on_ask:
                self._on_ask()
        finally:
            self._busy.discard(key)

    # ---------- his answers ----------
    def decide(self, ask_id, action):
        with self._lock:
            q = next((p for p in self.pending if p["id"] == ask_id), None)
            if q:
                self.pending.remove(q)
        if not q:
            return {"ok": False, "message": "That question was already answered."}
        if q.get("kind") == "notice":                          # a note (a USB stick, a risky download): its own answers
            if action == "quarantine" and q.get("path"):
                return self.quarantine_path(q["path"], why=next((c[1] for c in q["checks"] if c[0] == "bad"), "a risky download"))
            if action == "keep":
                self.log("%s · kept (your choice)" % Path(q.get("path") or q["name"]).name)
                self._save()
            return {"ok": True, "message": "", "show": action == "show"}
        key = _key(q["path"])
        if action == "trust":
            self.data["trusted"].insert(0, {"path": q["path"], "name": q["name"], "signed": q["signed"], "when": now()})
            self.data["known"].pop(key, None)
            self.log("%s · trusted, never asked again" % q["name"])
            msg = "%s is trusted." % q["name"]
        elif action == "once":
            self._once.add(key)
            self.log("%s · allowed this time" % q["name"])
            msg = "%s is allowed until Toolbelt restarts." % q["name"]
        elif action == "stop":
            msg = self._stop_and_quarantine(q)
        else:
            return {"ok": False, "message": "Unknown answer."}
        self._save()
        return {"ok": True, "message": msg}

    def _stop_and_quarantine(self, q):
        name, src = q["name"], Path(q["path"])
        ended = 0
        for proc in psutil.process_iter(["pid", "exe"]):              # every copy of it, and what it started
            try:
                if _key(proc.info.get("exe") or "") == _key(src):
                    for child in proc.children(recursive=True):
                        child.kill()
                    proc.kill()
                    ended += 1
            except (psutil.Error, OSError):
                pass
        time.sleep(0.5)                                         # Windows lets go of the file a moment after the program ends
        self._qdir.mkdir(parents=True, exist_ok=True)
        stored = self._qdir / ("%s-%s.blocked" % (time.strftime("%Y%m%d-%H%M%S"), name))
        try:
            shutil.move(str(src), str(stored))
        except OSError as error:
            self.log("%s · ended, but its file couldn't be moved: %s" % (name, str(error)[:80]))
            return "%s was ended, but its file couldn't be moved (%s)." % (name, str(error)[:80])
        with self._lock:
            self._ids += 1
            self.data["quarantine"].insert(0, {"id": "q%d-%d" % (int(time.time()), self._ids), "name": name, "original": str(src), "stored": str(stored),
                                               "when": now(), "why": next((c[1] for c in q["checks"] if c[0] == "bad"), "you stopped it")})
        self.log("%s · stopped and moved to quarantine" % name)
        return "%s was stopped and moved to quarantine." % name if ended else "%s had already closed; its file is in quarantine now." % name

    def forget(self, path):
        key = _key(path)
        before = len(self.data["trusted"])
        self.data["trusted"] = [t for t in self.data["trusted"] if _key(t["path"]) != key]
        if len(self.data["trusted"]) == before:
            return {"ok": False, "message": "It wasn't trusted."}
        self.log("%s · no longer trusted (asked again next time)" % Path(path).name)
        self._save()
        return {"ok": True, "message": "%s will be asked about again." % Path(path).name}

    def _quarantined(self, qid):
        return next((x for x in self.data["quarantine"] if x["id"] == qid), None)

    def restore(self, qid):
        q = self._quarantined(qid)
        if not q:
            return {"ok": False, "message": "That one isn't in quarantine any more."}
        target = Path(q["original"])
        if target.exists():
            target = target.with_name("%s (restored)%s" % (target.stem, target.suffix))
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(q["stored"], str(target))
        except OSError as error:
            return {"ok": False, "message": "Couldn't put it back: %s" % str(error)[:120]}
        self.data["quarantine"].remove(q)
        self.data["known"].pop(_key(target), None)              # it gets asked about again when it starts
        self.log("%s · restored to %s" % (q["name"], target.parent))
        self._save()
        return {"ok": True, "message": "%s is back in %s. It will be asked about when it starts." % (target.name, target.parent)}

    def delete(self, qid):
        q = self._quarantined(qid)
        if not q:
            return {"ok": False, "message": "That one isn't in quarantine any more."}
        import leftscan
        code = leftscan.recycle(q["stored"]) if Path(q["stored"]).exists() else 0
        if code != 0:
            return {"ok": False, "message": "Windows couldn't move it to the Recycle Bin (code %s)." % code}
        self.data["quarantine"].remove(q)
        self.log("%s · deleted (in the Recycle Bin)" % q["name"])
        self._save()
        return {"ok": True, "message": "%s is in the Recycle Bin." % q["name"]}

    def status(self):
        with self._lock:
            return {"running": self.running(), "trusted": list(self.data["trusted"]), "quarantine": list(self.data["quarantine"]),
                    "log": list(self.data["log"][:120]), "known": len(self.data["known"]), "pending": len(self.pending),
                    "scans": json.loads(json.dumps(self.data["scans"])), "downloads": list(self.data["downloads"][:60])}
