"""Tests for viewer.py without a window: the byte ranges a video player asks for, and that only files Toolbelt was
given have an address (the real WebView2 answering is checked by the hidden self-test, tests/playcheck.py)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "toolbelt"))

import viewer                                                 # noqa: E402

failures = []


def expect(label, condition):
    print(("ok    " if condition else "FAIL  ") + label)
    if not condition:
        failures.append(label)


size = 1000
expect("'bytes=0-99' is the first 100 bytes", viewer.parse_range("bytes=0-99", size) == (0, 99))
expect("'bytes=100-' is from 100 to the end", viewer.parse_range("bytes=100-", size) == (100, 999))
expect("'bytes=-200' is the last 200 bytes", viewer.parse_range("bytes=-200", size) == (800, 999))
expect("a range past the end is cut at the end", viewer.parse_range("bytes=900-5000", size) == (900, 999))
expect("starting after the end can't be answered (416)", viewer.parse_range("bytes=1000-", size)[0] > viewer.parse_range("bytes=1000-", size)[1])
expect("no header or nonsense = the whole file", viewer.parse_range("", size) is None and viewer.parse_range("bytes=-", size) is None and viewer.parse_range("items=1-2", size) is None)
viewer._files["0123456789abcdef"] = "C:/x/clip.mp4"
expect("a known id gives its file", viewer.path_of(viewer.PREFIX + "0123456789abcdef/clip.mp4") == "C:/x/clip.mp4")
expect("an unknown id or another site gives nothing", viewer.path_of(viewer.PREFIX + "ffffffffffffffff/clip.mp4") is None and viewer.path_of("https://evil.example/0123456789abcdef/x") is None)
expect("the address is made up and never leaves the window (.example is reserved, never a real site)", viewer.HOST.endswith(".example"))

print()
if failures:
    print("%d FAILED: %s" % (len(failures), ", ".join(failures)))
    sys.exit(1)
print("ALL PASSED (test_viewer)")
