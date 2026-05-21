import os

SRC_DIR = "/Users/erishen/Workspace/CNB/individular-invest/InvestKit/projects/stock-analyzer/src"

def fix_file(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    has_top_level_logger = False
    logger_lines = []

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped == "logger = logging.getLogger(__name__)":
            indent = len(line) - len(line.lstrip())
            if indent == 0:
                has_top_level_logger = True
            else:
                logger_lines.append(i)

    if has_top_level_logger:
        for i in reversed(logger_lines):
            if lines[i].strip() == "logger = logging.getLogger(__name__)":
                if i + 1 < len(lines) and lines[i + 1].strip() == "":
                    lines.pop(i + 1)
                lines.pop(i)
        with open(filepath, "w", encoding="utf-8") as f:
            f.writelines(lines)
        return

    if not logger_lines:
        return

    for i in reversed(logger_lines):
        if lines[i].strip() == "logger = logging.getLogger(__name__)":
            if i + 1 < len(lines) and lines[i + 1].strip() == "":
                lines.pop(i + 1)
            lines.pop(i)

    last_top_import = -1
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("import ") or stripped.startswith("from "):
            indent = len(line) - len(line.lstrip())
            if indent == 0:
                last_top_import = i

    if last_top_import >= 0:
        insert_pos = last_top_import + 1
        if insert_pos < len(lines) and lines[insert_pos].strip() == "":
            insert_pos += 1
        lines.insert(insert_pos, "\nlogger = logging.getLogger(__name__)\n")

    with open(filepath, "w", encoding="utf-8") as f:
        f.writelines(lines)

for root, dirs, files in os.walk(SRC_DIR):
    dirs[:] = [d for d in dirs if d != "tests"]
    for fname in files:
        if fname.endswith(".py"):
            fpath = os.path.join(root, fname)
            fix_file(fpath)

print("Done fixing logger positions (pass 2)")
