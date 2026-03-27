import sys
from pathlib import Path
# ensure project root is on sys.path so we can import app when running from scripts/
proj_root = str(Path(__file__).resolve().parents[1])
if proj_root not in sys.path:
    sys.path.insert(0, proj_root)

from app import normalize_name

def run_checks():
    cases = [
        ("joão da silva", "João Da Silva"),
        ("ANNA-maria o'neill", "Anna-Maria O'neill"),
        ("  pedro   alves  ", "Pedro Alves"),
        ("mARIA-CLARA dos santos", "Maria-Clara Dos Santos"),
        ("", ""),
        (None, ""),
        ("léia", "Léia"),
    ]
    ok = True
    for raw, expected in cases:
        out = normalize_name(raw)
        status = 'OK' if out == expected else 'FAIL'
        print(f"IN: {raw!r} -> OUT: {out!r} | expected: {expected!r} | {status}")
        if status != 'OK':
            ok = False
    return 0 if ok else 2

if __name__ == '__main__':
    rc = run_checks()
    if rc == 0:
        print('ALL OK')
    raise SystemExit(rc)
