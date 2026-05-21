import os
import re

SRC_DIR = "/Users/erishen/Workspace/CNB/individular-invest/InvestKit/projects/stock-analyzer/src"

def fix_file(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    changed = False

    if lines and lines[0].strip() == "logger = logging.getLogger(__name__)":
        lines.pop(0)
        changed = True

    if not changed:
        return

    has_logger = any("logger = logging.getLogger(__name__)" in line for line in lines)

    last_import_idx = -1
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("import ") or stripped.startswith("from "):
            last_import_idx = i

    if not has_logger and last_import_idx >= 0:
        indent = ""
        for ch in lines[last_import_idx]:
            if ch in (" ", "\t"):
                indent += ch
            else:
                break
        lines.insert(last_import_idx + 1, "\n" + indent + "logger = logging.getLogger(__name__)\n")
    elif not has_logger:
        lines.insert(0, "import logging\n\nlogger = logging.getLogger(__name__)\n")

    with open(filepath, "w", encoding="utf-8") as f:
        f.writelines(lines)

for root, dirs, files in os.walk(SRC_DIR):
    dirs[:] = [d for d in dirs if d != "tests"]
    for fname in files:
        if fname.endswith(".py"):
            fpath = os.path.join(root, fname)
            fix_file(fpath)

print("Done fixing logger positions")
