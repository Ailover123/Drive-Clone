import re

with open('app.js', 'r', encoding='utf-8') as f:
    code = f.read()

# Strip /api/ from all api calls
code = re.sub(r"api\('([^']+)', '/api/([^']+)'", r"api('\1', '/\2'", code)
# Also handle preview images logic where `/api/files/` is used directly in HTML/DOM
code = re.sub(r"src=\"/api/files/([^/]+)/preview\"", r"src=\"/files/\1/preview\"", code)
code = re.sub(r"window.open\(`/api/files/", r"window.open(`/files/", code)

# Map Create Folder specifically
code = re.sub(r"api\('POST', '/folders'", r"api('POST', '/create-folder'", code)

with open('app.js', 'w', encoding='utf-8') as f:
    f.write(code)

print("Updated app.js routes!")
