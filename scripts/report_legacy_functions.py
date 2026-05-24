from pathlib import Path
import ast

path = Path("app/legacy_app.py")
tree = ast.parse(path.read_text(encoding="utf-8"))

items = []

for node in tree.body:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        items.append({
            "line": node.lineno,
            "type": "async" if isinstance(node, ast.AsyncFunctionDef) else "def",
            "name": node.name,
        })

print(f"legacy_app.py remaining top-level functions: {len(items)}")
print("-" * 80)

for item in items:
    print(f"{item['line']:>5}  {item['type']:<5}  {item['name']}")
