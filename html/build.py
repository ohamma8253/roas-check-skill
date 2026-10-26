# html/index.html + data.js + app.js → dashboard/ROAS_점검_지도.html (한 파일)
from pathlib import Path
root = Path(__file__).parent
html = (root / "index.html").read_text(encoding="utf-8")
for name in ("data.js", "checks.js", "app.js"):
    js = (root / name).read_text(encoding="utf-8")
    html = html.replace(f'<script src="{name}"></script>', f"<script>\n{js}\n</script>")
out = root.parent / "dashboard" / "ROAS_점검_지도.html"
out.parent.mkdir(exist_ok=True)
out.write_text(html, encoding="utf-8")
print(out)
