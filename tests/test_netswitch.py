"""The internet switch (17 Oct), without ever switching the internet: reading the adapter, the two tasks' contents,
names that could break out of the command are refused. The button: test_page_net.py."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "toolbelt"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import netswitch                                               # noqa: E402

failures = []


def expect(label, condition):
    print(("ok    " if condition else "FAIL  ") + label)
    if not condition:
        failures.append(label)


found = netswitch.adapters()
expect("the real adapters are read (%s)" % ", ".join(a["name"] + " " + a["status"] for a in found), len(found) >= 1)
name = netswitch.pick_adapter()
expect("the adapter in use is picked", name and any(a["name"] == name for a in found))
st = netswitch.state(name)
expect("its state is one of on / nocable / off (now: %s)" % st, st in ("on", "nocable", "off"))
expect("an adapter that doesn't exist counts as off, without an error", netswitch.state("No Such Adapter 9") == "off")
for bad in ("Ethernet'; Remove-Item C:\\x", "a\"b", "x;y", "", "a" * 81):
    expect("a name that could break the command is refused: %r" % bad[:30], not netswitch.SAFE_NAME.match(bad))
script = netswitch.SETUP.replace("ADAPTER", "Ethernet")
expect("the setup makes exactly the two tasks, with admin rights, in the Toolbelt folder",
       "'Internet off', 'Disable'" in script and "'Internet on', 'Enable'" in script and "-RunLevel Highest" in script and "-TaskPath '\\Toolbelt\\'" in script)
expect("the tasks' command holds the adapter name and no script file", "-NetAdapter -Name 'Ethernet'" in script and ".ps1" not in script)
inst = netswitch.installed()
print("info  set up on this PC for: %r" % inst)
if inst:
    expect("installed() reads the adapter back from both tasks", inst == name)

print("ALL PASSED" if not failures else "%d FAILED" % len(failures))
sys.exit(1 if failures else 0)
