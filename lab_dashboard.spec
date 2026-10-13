# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.building.build_main import Analysis, PYZ, EXE, COLLECT
from PyInstaller.utils.hooks import collect_all

ONE_FILE = False          # پوشه‌ای: شروع سریع‌تر و پایدارتر
CONSOLE = False           # بدون پنجرهٔ سیاه

datas = [("app.py", ".")]
binaries = []
hiddenimports = []

for pkg in ["streamlit", "pandas", "numpy", "altair",
            "pyarrow", "openpyxl", "xlsxwriter"]:
    try:
        d, b, h = collect_all(pkg)
        datas += d; binaries += b; hiddenimports += h
        print(f"[OK]  {pkg}")
    except Exception as exc:
        print(f"[SKIP] {pkg} -> {exc}")

a = Analysis(
    ["runner.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["IPython", "jupyter", "matplotlib", "scipy",
              "pytest", "notebook", "nbformat", "nbconvert"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(pyz, a.scripts, [], exclude_binaries=True,
          name="LabDashboard", debug=False,
          bootloader_ignore_signals=False, strip=False,
          upx=False, console=CONSOLE)

coll = COLLECT(exe, a.binaries, a.datas, strip=False,
               upx=False, name="LabDashboard")