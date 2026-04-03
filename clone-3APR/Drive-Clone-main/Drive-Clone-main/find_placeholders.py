with open('app.py', 'r', encoding='utf-8') as f:
    code = f.read()

# Find all %s occurrences
import re
matches = [(m.start(), code[max(0,m.start()-50):m.start()+50]) for m in re.finditer(r'%s', code)]
for pos, ctx in matches:
    print(f"pos={pos}: ...{ctx}...")
    
if not matches:
    print("No %s found")
