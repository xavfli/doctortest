"""Print brace depth at every top-level function definition."""
import re
import sys

path = sys.argv[1]
raw = open(path, encoding="utf-8").read()
text = re.sub(r"/\*.*?\*/", "", raw, flags=re.S)
text = re.sub(r"//[^\n]*", "", text)
text = re.sub(r'"(?:\\.|[^"\\])*"', '""', text)
text = re.sub(r"'(?:\\.|[^'\\])*'", "''", text)
text = re.sub(r"`(?:\\.|[^`\\])*`", "``", text)

depth = 0
for n, line in enumerate(text.splitlines(), 1):
    before = depth
    depth += line.count("{") - line.count("}")
    stripped = line.strip()
    if stripped.startswith("function ") or stripped.startswith("global."):
        print("%4d depth %d->%d  %s" % (n, before, depth, stripped[:60]))
print("final depth:", depth)
