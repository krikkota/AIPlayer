"""Build on the target OS. No ASR or Ollama weights enter the bundle."""
from pathlib import Path
import argparse
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
import tarfile
import tempfile

root = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--archive", action="store_true", help="Also create a release ZIP on macOS.")
args = parser.parse_args()
outputs = root / "outputs"
outputs.mkdir(exist_ok=True)
environment = dict(os.environ, PYINSTALLER_CONFIG_DIR=str(root / "work/pyinstaller-cache"))

def build_into(destination):
    subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
                    "--distpath", str(destination), "--workpath", str(root / "work/build"),
                    str(root / "AIPlayer.spec")], cwd=root, env=environment, check=True)


def verify_links(bundle):
    bundle = bundle.resolve()
    for path in bundle.rglob("*"):
        if path.is_symlink() and (not path.exists() or not path.resolve().is_relative_to(bundle)):
            raise RuntimeError(f"Invalid application link: {path}")

if sys.platform == "darwin":
    bundle = outputs / "AIPlayer.app"
    with tempfile.TemporaryDirectory(prefix=".aiplayer-build-", dir=outputs) as folder:
        stage = Path(folder)
        build_into(stage)
        candidate = stage / bundle.name
        verify_links(candidate)
        subprocess.run(["codesign", "--verify", "--deep", "--strict", str(candidate)], check=True)
        previous = stage / "previous.app"
        if bundle.exists() or bundle.is_symlink():
            bundle.rename(previous)
        try:
            candidate.rename(bundle)
        except OSError:
            if previous.exists() or previous.is_symlink():
                previous.rename(bundle)
            raise
    print(f"Updated application: {bundle}")
    if not args.archive:
        sys.exit(0)
else:
    build_into(outputs)
    bundle = outputs / "AIPlayer"
    verify_links(bundle)

version = tomllib.loads((root/"pyproject.toml").read_text())["project"]["version"]
system = {"darwin":"macOS", "win32":"Windows"}.get(sys.platform,"Linux")
machine = platform.machine().lower()
arch = "arm64" if machine in ("arm64","aarch64") else "x64" if machine in ("x86_64","amd64") else machine
if sys.platform=="win32":
    arch = "x64" if sysconfig.get_platform()=="win-amd64" else "arm64" if sysconfig.get_platform()=="win-arm64" else "x86"
extension = "tar.gz" if system == "Linux" else "zip"
archive = root/"outputs"/f"AIPlayer-{version}-{system}-{arch}.{extension}"
archive.unlink(missing_ok=True)
if sys.platform=="darwin":
    subprocess.run(["ditto","-c","-k","--sequesterRsrc","--keepParent",str(bundle),str(archive)],check=True)
elif system == "Linux":
    with tarfile.open(archive, "w:gz", compresslevel=6) as output:
        output.add(bundle, arcname="AIPlayer")
else:
    with zipfile.ZipFile(archive,"w",zipfile.ZIP_DEFLATED,compresslevel=6) as output:
        for path in sorted(bundle.rglob("*")):
            if path.is_file():
                output.write(path,path.relative_to(bundle.parent))
if extension == "zip":
    with zipfile.ZipFile(archive) as result:
        if result.testzip() is not None:
            raise RuntimeError("Release archive is corrupted")
with archive.open("rb") as stream:
    digest = hashlib.file_digest(stream,"sha256").hexdigest()
latest = root/"outputs"/f"AIPlayer-{system}-{arch}.{extension}"
latest.unlink(missing_ok=True)
try:
    os.link(archive, latest)
except OSError:
    shutil.copy2(archive, latest)
(root/"outputs/SHA256SUMS.txt").write_text(f"{digest}  {archive.name}\n")
(root/"outputs/release.json").write_text(json.dumps(dict(version=version,archive=archive.name,
    bytes=archive.stat().st_size,sha256=digest,models_bundled=False,platform=system,architecture=arch),indent=2)+"\n")
print(f"Verified release: {archive}")

