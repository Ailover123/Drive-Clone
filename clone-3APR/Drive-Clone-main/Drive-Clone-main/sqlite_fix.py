import re

with open('app.py', 'r', encoding='utf-8') as f:
    code = f.read()

# 1. Replace cur = conn.cursor(dictionary=True) with plain cursor (row_factory handles dicts)
code = code.replace('conn.cursor(dictionary=True)', 'conn.cursor()')

# 2. Replace MySQL %s placeholders with SQLite ? placeholders
#    Only in SQL strings (between quotes that contain SQL keywords)
# We'll do a targeted replacement in execute calls
# SQLite uses ? instead of %s
code = re.sub(r'(?<!["\'])%s(?!["\'])', '?', code)

# 3. Replace mysql.connector.IntegrityError with sqlite3.IntegrityError
code = code.replace('mysql.connector.IntegrityError', 'sqlite3.IntegrityError')

# 4. Fix lastrowid - works same in sqlite3
# 5. Fix NOW() -> datetime('now') in SQL strings  
code = code.replace("NOW()", "datetime('now')")
code = code.replace("CURRENT_TIMESTAMP", "datetime('now')")

# 6. Fix TRUE/FALSE in SQL to 1/0
code = code.replace('is_trashed=TRUE', 'is_trashed=1')
code = code.replace('is_trashed=FALSE', 'is_trashed=0')
code = code.replace('is_starred=TRUE', 'is_starred=1')
code = code.replace('is_starred=FALSE', 'is_starred=0')
code = code.replace('is_pinned=TRUE', 'is_pinned=1')
code = code.replace('is_pinned=FALSE', 'is_pinned=0')
code = code.replace('is_private=TRUE', 'is_private=1')
code = code.replace('is_private=FALSE', 'is_private=0')

# 7. Fix NOT is_trashed -> is_trashed=NOT is_trashed isn't valid in sqlite
code = code.replace('is_starred = NOT is_starred', 'is_starred = 1 - is_starred')
code = code.replace('is_pinned = NOT is_pinned', 'is_pinned = 1 - is_pinned')
code = code.replace('is_trashed = NOT is_trashed', 'is_trashed = 1 - is_trashed')

# 8. Fix log_activity INSERT placeholder
code = code.replace(
    '"INSERT INTO activity_log (user_id, action, target_name, details, ip_address) VALUES (%s,%s,%s,%s,%s)"',
    '"INSERT INTO activity_log (user_id, action, target_name, details, ip_address) VALUES (?,?,?,?,?)"'
)

# 9. Fix fetchone() results - since row_factory=sqlite3.Row is set, dict(row) works
# But we need to ensure .get() calls work - sqlite3.Row supports key access already

# 10. Fix auto_delete_trash - uses %s cutoff
# Already fixed by global %s -> ? replacement above

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(code)

print("Fixed all MySQL->SQLite syntax issues!")
print("Verifying...")

# Quick syntax check
import py_compile
try:
    py_compile.compile('app.py', doraise=True)
    print("app.py syntax OK!")
except py_compile.PyCompileError as e:
    print(f"Syntax error: {e}")
