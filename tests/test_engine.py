"""Tests for the Python side: settings, the job runner and the engine list. Uses a temporary folder, never AppData."""
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "toolbelt"))

import engines
from jobs import Jobs
from settings import Settings, check

failures = []


def expect(label, condition):
    print(("ok    " if condition else "FAIL  ") + label)
    if not condition:
        failures.append(label)


def wait_for(jobs, job_id, states, seconds=5):
    deadline = time.time() + seconds
    while time.time() < deadline:
        job = next(j for j in jobs.list() if j["id"] == job_id)
        if job["state"] in states:
            return job
        time.sleep(0.05)
    return job


with tempfile.TemporaryDirectory() as tmp:
    # ---------- settings ----------
    s = Settings(tmp)
    expect("defaults: Cartridge look", s.get()["look"] == "cartridge")
    expect("look can change", s.set("look", "glassdark")["ok"] and s.get()["look"] == "glassdark")
    expect("unknown look refused", not s.set("look", "neon")["ok"] and s.get()["look"] == "glassdark")
    expect("accent must be #RRGGBB", not s.set("accent", "red")["ok"] and s.set("accent", "#ffcf3f")["settings"]["accent"] == "#FFCF3F")
    expect("accent can go back to the look's own", s.set("accent", "")["ok"])
    expect("switches only take on/off", not s.set("animations", "yes")["ok"] and s.set("animations", False)["ok"])
    expect("save folder must be a full path", not s.set("save_to", "Downloads")["ok"] and s.set("save_to", "C:\\Temp\\TB")["ok"])
    expect("name pattern needs {ext}", not s.set("name_pattern", "{title}")["ok"])
    expect("name pattern refuses \\ / : * ? \" < > |", not s.set("name_pattern", "a:b.{ext}")["ok"])
    expect("unknown setting refused", not s.set("colour_of_sky", "blue")["ok"])
    again = Settings(tmp)
    expect("settings survive a restart", again.get()["look"] == "glassdark" and again.get()["animations"] is False and again.get()["save_to"] == "C:\\Temp\\TB")
    (Path(tmp) / "settings.json").write_text('{"look": "neon", "animations": "maybe", "extra": 1, "accent": "#00FF00"}', encoding="utf-8")
    broken = Settings(tmp).get()
    expect("a broken file falls back to defaults per value", broken["look"] == "cartridge" and broken["animations"] is True and broken["accent"] == "#00FF00" and "extra" not in broken)
    (Path(tmp) / "settings.json").write_text("not json at all", encoding="utf-8")
    expect("an unreadable file gives the defaults", Settings(tmp).get()["look"] == "cartridge")
    expect("check() explains what's wrong", check("name_pattern", "x")[1].startswith("Keep {ext}"))

    # ---------- jobs ----------
    jobs = Jobs(at_once=1)

    def counting(job):
        for i in range(10):
            job.check()
            time.sleep(0.02)
            job.report((i + 1) * 10, "step %d" % (i + 1))
        return "made.txt"

    a = jobs.submit("Count", "Test", counting)
    done = wait_for(jobs, a.id, ("done", "failed"))
    expect("a job runs to done with its result", done["state"] == "done" and done["progress"] == 100 and done["result"] == "made.txt")

    def slow(job):
        for _ in range(200):
            job.check()
            time.sleep(0.02)

    b = jobs.submit("Slow", "Test", slow)
    time.sleep(0.1)
    expect("cancel answers", jobs.cancel(b.id)["ok"])
    expect("a cancelled job stops", wait_for(jobs, b.id, ("cancelled",))["state"] == "cancelled")

    def broken_job(job):
        raise ValueError("the file was gone")

    c = jobs.submit("Broken", "Test", broken_job)
    failed = wait_for(jobs, c.id, ("failed",))
    expect("a failing job reports, not crashes", failed["state"] == "failed" and "file was gone" in failed["message"])

    d = jobs.submit("Second slow", "Test", slow)
    e = jobs.submit("Waits for a free slot", "Test", counting)
    time.sleep(0.1)
    expect("only one runs at a time here", next(j for j in jobs.list() if j["id"] == e.id)["state"] == "waiting")
    jobs.cancel(e.id)
    jobs.cancel(d.id)
    wait_for(jobs, d.id, ("cancelled",))
    expect("a waiting job can be cancelled", next(j for j in jobs.list() if j["id"] == e.id)["state"] == "cancelled")
    expect("newest job first", jobs.list()[0]["id"] == e.id)
    jobs.clear_finished()
    expect("clear finished empties the list", jobs.list() == [])
    expect("cancelling an unknown job says so", not jobs.cancel(999)["ok"])

    # ---------- engines ----------
    base = Path(tmp) / "engines"
    listing = engines.list_engines(base)
    expect("five engines listed, none installed", len(listing["engines"]) == 5 and not any(x["installed"] for x in listing["engines"]) and listing["total"] == 0)
    (base / "yt-dlp").mkdir(parents=True)
    (base / "yt-dlp" / "yt-dlp.exe").write_bytes(b"x" * 2048)
    (base / "yt-dlp" / "version.txt").write_text("2026.09.30", encoding="utf-8")
    listing = engines.list_engines(base)
    yt = listing["engines"][0]
    expect("an installed engine is found with size and version", yt["installed"] and yt["size"] >= 2048 and yt["version"] == "2026.09.30")
    expect("the total adds up", listing["total"] == yt["size"])

expect("graphics cards are read from Windows (a list)", isinstance(engines.gpus(), list))

print()
if failures:
    print("%d FAILED: %s" % (len(failures), ", ".join(failures)))
    sys.exit(1)
print("ALL PASSED (test_engine)")
