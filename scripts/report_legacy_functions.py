from pathlib import Path
import ast

path = Path("app/legacy_app.py")

if not path.exists():
    print("legacy_app.py remaining top-level functions: 0")
    print("-" * 80)
    print("app/legacy_app.py not found")
    raise SystemExit(0)

text = path.read_text(encoding="utf-8")
tree = ast.parse(text)

items = []
for node in tree.body:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        kind = "async" if isinstance(node, ast.AsyncFunctionDef) else "def"
        items.append((node.lineno, kind, node.name))

print(f"legacy_app.py remaining top-level functions: {len(items)}")
print("-" * 80)
for lineno, kind, name in items:
    print(f"{lineno:5d}  {kind:<5}  {name}")
