import ast, sys
with open('savesync_gui.py', encoding='utf-8') as f:
    src = f.read()
try:
    ast.parse(src)
    print('Syntax OK')
except SyntaxError as e:
    print(f'SyntaxError at line {e.lineno}: {e.msg}')
    print(repr(e.text))
