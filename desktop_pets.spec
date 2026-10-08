# PyInstaller-Spezifikation: erzeugt dist/DesktopPets.exe (eine Datei, ohne Konsole)
#   pip install -r requirements-dev.txt
#   pyinstaller desktop_pets.spec
# -*- mode: python ; coding: utf-8 -*-

datas = [
    ("desktop_pets/pets", "desktop_pets/pets"),
    ("desktop_pets/assets", "desktop_pets/assets"),
    ("desktop_pets/themes", "desktop_pets/themes"),
    ("desktop_pets/win/share_signatures.json", "desktop_pets/win"),
]

a = Analysis(
    ["run_desktop_pets.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=["PySide6.QtMultimedia"],
    excludes=["tkinter", "PySide6.QtWebEngineCore", "PySide6.QtQml", "PySide6.QtQuick", "PySide6.Qt3DCore"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="DesktopPets",
    debug=False,
    strip=False,
    upx=False,
    console=False,
    icon="desktop_pets/assets/app.ico",
)
