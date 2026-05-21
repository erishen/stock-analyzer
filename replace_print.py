import os
import re

SRC_DIR = "/Users/erishen/Workspace/CNB/individular-invest/InvestKit/projects/stock-analyzer/src"

ERROR_KEYWORDS = [
    "错误", "error", "失败", "fail", "exception", "❌",
    "警告", "warning", "⚠️", "traceback", "traceback",
]
DEBUG_KEYWORDS = ["调试", "debug"]

SKIP_FILES = set()

def determine_log_level(content):
    content_lower = content.lower()
    for kw in ERROR_KEYWORDS:
        if kw.lower() in content_lower:
            return "error"
    for kw in DEBUG_KEYWORDS:
        if kw.lower() in content_lower:
            return "debug"
    return "info"

def find_print_calls(lines):
    calls = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.lstrip()
        if re.match(r'^print\s*\(', stripped) and not re.match(r'^\s*#\s*print', line):
            depth = 0
            start_line = i
            combined = ""
            for j in range(i, len(lines)):
                current = lines[j]
                if j == i:
                    before_print = line[:line.index("print")]
                    combined += current
                else:
                    combined += "\n" + current
                depth += current.count("(") - current.count(")")
                if depth <= 0:
                    calls.append((start_line, j, combined, before_print))
                    i = j + 1
                    break
            else:
                i += 1
        else:
            i += 1
    return calls

def replace_print_call(combined, indent):
    inner_match = re.match(r'^(\s*)print\s*\((.*)\)\s*$', combined, re.DOTALL)
    if not inner_match:
        inner_match = re.match(r'^(\s*)print\s*\((.*)\)\s*,?\s*$', combined, re.DOTALL)
    if not inner_match:
        return None

    orig_indent = inner_match.group(1)
    inner = inner_match.group(2).strip()

    if not inner:
        return orig_indent + "logger.info('')"

    level = determine_log_level(inner)

    if inner.count("(") > inner.count(")"):
        return None

    return orig_indent + f"logger.{level}({inner})"

def process_file(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    lines = content.split("\n")

    has_import_logging = "import logging" in content
    has_logger = "logger = logging.getLogger" in content

    calls = find_print_calls(lines)
    if not calls:
        return 0

    replacements = []
    for start, end, combined, indent in calls:
        new_text = replace_print_call(combined, indent)
        if new_text is not None:
            replacements.append((start, end, new_text))

    if not replacements:
        return 0

    for start, end, new_text in reversed(replacements):
        lines[start:end + 1] = [new_text]

    if not has_import_logging:
        import_line = "import logging"
        insert_pos = 0
        for i, line in enumerate(lines):
            if line.startswith("import ") or line.startswith("from "):
                insert_pos = i
                break
        lines.insert(insert_pos, import_line)

    if not has_logger:
        logger_line = "logger = logging.getLogger(__name__)"
        if not has_import_logging:
            insert_pos = 1
            for i, line in enumerate(lines):
                if not (line.startswith("import ") or line.startswith("from ")):
                    insert_pos = i
                    break
            lines.insert(insert_pos, logger_line)
        else:
            for i, line in enumerate(lines):
                if line.strip() == "" or (not line.startswith("import ") and not line.startswith("from ")):
                    if i > 0:
                        lines.insert(i, logger_line)
                    break

    new_content = "\n".join(lines)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(new_content)

    return len(replacements)

total_replaced = 0
for root, dirs, files in os.walk(SRC_DIR):
    dirs[:] = [d for d in dirs if d != "tests"]
    for fname in files:
        if fname.endswith(".py") and fname not in SKIP_FILES:
            fpath = os.path.join(root, fname)
            count = process_file(fpath)
            if count > 0:
                rel = os.path.relpath(fpath, SRC_DIR)
                print(f"  {rel}: {count} 处替换")
                total_replaced += count

print(f"\n总计替换: {total_replaced} 处")
