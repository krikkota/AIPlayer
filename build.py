"""Build on the target OS. No ASR or Ollama weights enter the bundle."""
from pathlib import Path
import os
import subprocess
import sys
import hashlib
import json
import platform
import zipfile
import shutil
import tomllib
import sysconfig

root = Path(__file__).resolve().parent
environment = dict(os.environ, PYINSTALLER_CONFIG_DIR=str(root / "work/pyinstaller-cache"))
subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
                "--distpath", str(root / "outputs"), "--workpath", str(root / "work/build"),
                str(root / "AIPlayer.spec")], cwd=root, env=environment, check=True)

if sys.platform == "darwin":
    bundle = (root / "outputs/AIPlayer.app").resolve()
    for path in bundle.rglob("*"):
        if path.is_symlink() and (not path.exists() or not path.resolve().is_relative_to(bundle)):
            raise RuntimeError(f"Invalid application link: {path}")
    subprocess.run(["codesign", "--verify", "--deep", "--strict", str(bundle)], check=True)

else:
    bundle = root/"outputs/AIPlayer"
    for path in bundle.rglob("*"):
        if path.is_symlink() and (not path.exists() or not path.resolve().is_relative_to(bundle.resolve())):
            raise RuntimeError(f"Invalid application link: {path}")

version = tomllib.loads((root/"pyproject.toml").read_text())["project"]["version"]
system = {"darwin":"macOS", "win32":"Windows"}.get(sys.platform,"Linux")
machine = platform.machine().lower()
arch = "arm64" if machine in ("arm64","aarch64") else "x64" if machine in ("x86_64","amd64") else machine
if sys.platform=="win32":
    arch = "x64" if sysconfig.get_platform()=="win-amd64" else "arm64" if sysconfig.get_platform()=="win-arm64" else "x86"
archive = root/"outputs"/f"AIPlayer-{version}-{system}-{arch}.zip"
archive.unlink(missing_ok=True)
if sys.platform=="darwin":
    subprocess.run(["ditto","-c","-k","--sequesterRsrc","--keepParent",str(bundle),str(archive)],check=True)
else:
    with zipfile.ZipFile(archive,"w",zipfile.ZIP_DEFLATED,compresslevel=6) as output:
        for path in sorted(bundle.rglob("*")):
            if path.is_file():
                output.write(path,path.relative_to(bundle.parent))
with zipfile.ZipFile(archive) as result:
    if result.testzip() is not None:
        raise RuntimeError("Release archive is corrupted")
with archive.open("rb") as stream:
    digest = hashlib.file_digest(stream,"sha256").hexdigest()
latest = root/"outputs"/f"AIPlayer-{system}-{arch}.zip"
latest.unlink(missing_ok=True)
try:
    os.link(archive, latest)
except OSError:
    shutil.copy2(archive, latest)
(root/"outputs/SHA256SUMS.txt").write_text(f"{digest}  {archive.name}\n")
(root/"outputs/release.json").write_text(json.dumps(dict(version=version,archive=archive.name,
    bytes=archive.stat().st_size,sha256=digest,models_bundled=False,platform=system,architecture=arch),indent=2)+"\n")
if sys.platform=="darwin":
    shutil.rmtree(root/"outputs/AIPlayer")
print(f"Verified release: {archive}")

