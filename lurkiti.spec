# PyInstaller spec for lurkiti (onedir). Built in CI by .github/workflows/release.yml.
# Pure-Python tray app: no libmpv/ffmpeg. It launches external players (mpv/vlc),
# which the user provides, so only Python-level dependencies are bundled.
from PyInstaller.utils.hooks import collect_all, collect_submodules

block_cipher = None

datas = [("src/lurkiti/resources", "lurkiti/resources")]
binaries = []
hiddenimports = (
  collect_submodules("lurkiti")
  + collect_submodules("streamlink")
  + collect_submodules("streamlink_cli")
)

# Packages that load submodules/backends dynamically need their data + hidden imports.
for pkg in ("streamlink", "streamlink_cli", "desktop_notifier", "pydantic"):
  pkg_datas, pkg_binaries, pkg_hidden = collect_all(pkg)
  datas += pkg_datas
  binaries += pkg_binaries
  hiddenimports += pkg_hidden

a = Analysis(
  ["packaging/pyinstaller/lurkiti_entry.py"],
  pathex=["src"],
  binaries=binaries,
  datas=datas,
  hiddenimports=hiddenimports,
  hookspath=[],
  runtime_hooks=[],
  excludes=["tkinter"],
  cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
  pyz,
  a.scripts,
  [],
  exclude_binaries=True,
  name="lurkiti",
  console=False,
  icon="src/lurkiti/resources/icons/app-icon.png",
)

coll = COLLECT(
  exe,
  a.binaries,
  a.datas,
  name="lurkiti",
)
