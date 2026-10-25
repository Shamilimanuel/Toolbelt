"""Tests for check.py: fingerprints against known values, matching pasted codes, Windows' signature check on a signed system
file and an unsigned one, comparing files, a folder's fingerprint list, and what-is-it-really sniffing."""
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "toolbelt"))

import check                                                  # noqa: E402
from jobs import Jobs                                         # noqa: E402

failures = []
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def expect(label, condition):
    print(("ok    " if condition else "FAIL  ") + label)
    if not condition:
        failures.append(label)


jobs = Jobs()


def run(work):
    job = jobs.submit("t", "Check", work)
    while job.state in ("waiting", "running"):
        time.sleep(0.05)
    return job


with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    hello = root / "hello.txt"
    hello.write_bytes(b"hello")
    h = check.hashes(None, hello)
    expect("the four fingerprints of 'hello' are the known ones", h["md5"] == "5d41402abc4b2a76b9719d911017c592" and h["sha1"] == "aaf4c61ddcc5e8a2dabede0f3b482cd9aea9434d"
           and h["sha256"] == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824" and h["sha512"].startswith("9b71d224bd62f378"))
    big = root / "big.bin"
    big.write_bytes(os.urandom(9 * 1024 * 1024))
    j = run(lambda job: check.hashes(job, big))
    expect("a bigger file reports progress and finishes", j.state == "done" and j.progress == 100 and len(j.result["sha256"]) == 64)
    expect("match: a pasted SHA-256 is recognised and compared", check.match(h, " 2CF24DBA-5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824 ")["ok"] and check.match(h, h["md5"])["algo"] == "md5")
    expect("match: a wrong code says DIFFERENT, a half code says what's wrong", "DIFFERENT" in check.match(h, "0" * 64)["message"] and "characters" in check.match(h, "abc")["message"] and not check.match(h, "")["ok"])

    # signatures: Windows' own notepad is signed by Microsoft; a fresh file isn't
    s = check.signature(Path(os.environ["SystemRoot"]) / "System32" / "notepad.exe")
    expect("notepad.exe is signed by Microsoft: %s" % s.get("title"), s["ok"] and s["status"] == "Valid" and s["level"] == "ok" and "Microsoft" in s["signer"] and s["until"])
    s = check.signature(hello)
    expect("a text file can't carry a signature, and says so", s["ok"] and s["status"] == "NotSignable" and s["level"] == "info" and "fingerprints" in s["why"])
    s = check.signature(Path(sys.executable).parent / "pip.exe")
    expect("an unsigned program (the venv's pip.exe) is 'Not signed'", s["ok"] and s["status"] == "NotSigned" and s["level"] == "warn")

    # compare
    copy = root / "hello copy.txt"
    shutil.copy(hello, copy)
    other = root / "other.txt"
    other.write_bytes(b"hellO")
    j = run(lambda job: check.compare(job, hello, copy))
    expect("two identical files compare as the same", j.result["same"] and "safely delete" in j.result["why"])
    j = run(lambda job: check.compare(job, hello, other))
    expect("same size, different content: not the same", not j.result["same"] and "differ" in j.result["why"])
    expect("different sizes are caught before reading", not run(lambda job: check.compare(job, hello, big)).result["same"])

    # a folder's list
    folder = root / "pack"
    (folder / "sub").mkdir(parents=True)
    (folder / "a.txt").write_text("A", encoding="utf-8")
    (folder / "sub" / "b.txt").write_text("B", encoding="utf-8")
    j = run(lambda job: check.folder_make(job, folder))
    listing = Path(j.result["path"])
    expect("a .sha256 list is written next to the folder, one line per file", listing.name == "pack.sha256" and j.result["files"] == 2 and "*sub/b.txt" in listing.read_text(encoding="utf-8"))
    j = run(lambda job: check.folder_verify(job, folder))
    expect("verifying right away: all good", j.result["ok"] and j.result["checked"] == 2)
    (folder / "a.txt").write_text("changed", encoding="utf-8")
    (folder / "sub" / "b.txt").unlink()
    (folder / "new.txt").write_text("N", encoding="utf-8")
    j = run(lambda job: check.folder_verify(job, folder))
    expect("changed, missing and new files are listed", j.result["changed"] == ["a.txt"] and j.result["missing"] == ["sub/b.txt"] and j.result["new"] == ["new.txt"] and not j.result["ok"])
    expect("verifying without a list is explained", run(lambda job: check.folder_verify(job, root / "nowhere")).state == "failed")

    # what is it really
    png = root / "photo.jpg"
    png.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 20)
    r = check.sniff(png)
    expect("a PNG called .jpg: warn, rename to .png", r["verdict"] == "warn" and r["real"] == "PNG picture" and ".png" in r["advice"])
    fake = root / "invoice.pdf.exe"
    fake.write_bytes(b"MZ" + b"\x00" * 60)
    r = check.sniff(fake)
    expect("invoice.pdf.exe: danger (a program with a fake ending)", r["verdict"] == "danger")
    fake2 = root / "invoice.pdf"
    fake2.write_bytes(b"MZ" + b"\x00" * 60)
    expect("a program called .pdf: danger", check.sniff(fake2)["verdict"] == "danger" and "pretending" in check.sniff(fake2)["advice"])
    expect("real text is fine; a real EXE is fine", check.sniff(hello)["verdict"] == "ok" and check.sniff(Path(os.environ["SystemRoot"]) / "System32" / "notepad.exe")["verdict"] == "ok")
    mp4 = root / "clip.mov"
    mp4.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 20)
    expect("MP4-family endings (.mov) are accepted", check.sniff(mp4)["verdict"] == "ok" and "MP4" in check.sniff(mp4)["real"])
    docx = root / "letter.docx"
    docx.write_bytes(b"PK\x03\x04" + b"\x00" * 30)
    expect("a .docx is a ZIP inside and that's fine", check.sniff(docx)["verdict"] == "ok" and check.sniff(docx)["real"] == "Word document")
    webp = root / "pic.png"
    webp.write_bytes(b"RIFF\x00\x00\x00\x00WEBPVP8 " + b"\x00" * 20)
    expect("a WebP called .png is noticed", check.sniff(webp)["verdict"] == "warn" and check.sniff(webp)["want"] == ".webp")

print()
if failures:
    print("%d FAILED: %s" % (len(failures), ", ".join(failures)))
    sys.exit(1)
print("ALL PASSED (test_check)")
