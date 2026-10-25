"""Every file picker's filter in main.py must be one pywebview accepts: "Description (*.a;*.b)", where the description
holds only letters, digits and spaces. A comma ("Pictures, GIFs and short videos") made pywebview refuse before the
dialog even opened: + File in the artwork editor and Media's Pick a file did nothing (his report, 15 Oct)."""
import re
import sys
from pathlib import Path

from webview.util import parse_file_type

failures = []


def expect(label, condition):
    print(("ok    " if condition else "FAIL  ") + label)
    if not condition:
        failures.append(label)


src = (Path(__file__).resolve().parent.parent / "main.py").read_text(encoding="utf-8")
filters = [(src[:m.start()].count("\n") + 1, m.group(1)) for m in re.finditer(r'"([^"]*\(\*\.[^"]*\))"', src)]
expect("the file pickers' filters are found (%d)" % len(filters), len(filters) >= 8)
for line, text in filters:
    try:
        parse_file_type(text)
        good = True
    except ValueError:
        good = False
    expect("main.py line %d: pywebview accepts '%s'" % (line, text[:50]), good)
try:
    parse_file_type("Pictures, GIFs (*.png)")
    caught = False
except ValueError:
    caught = True
expect("a comma in the description is refused (so this test would catch it)", caught)

print()
if failures:
    print("%d FAILED: %s" % (len(failures), ", ".join(failures)))
    sys.exit(1)
print("ALL PASSED (test_dialogs)")
