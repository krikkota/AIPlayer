"""Package the native macOS application in a drag-to-Applications disk image."""
from pathlib import Path
import hashlib
import json
import plistlib
import subprocess
import sys
import tempfile
import tomllib


def main():
    if sys.platform != "darwin":
        raise SystemExit("Build the macOS disk image on a Mac.")
    root = Path(__file__).resolve().parents[1]
    version = tomllib.loads((root / "pyproject.toml").read_text())["project"]["version"]
    app = root / "outputs/AIPlayer.app"
    with (app / "Contents/Info.plist").open("rb") as stream:
        info = plistlib.load(stream)
    if info["CFBundleShortVersionString"] != version:
        raise RuntimeError("Application and package versions differ")
    architectures = subprocess.check_output(
        ["lipo", "-archs", str(app / "Contents/MacOS/AIPlayer")], text=True
    ).split()
    architecture = {("arm64",): "arm64", ("x86_64",): "x64",
                    ("arm64", "x86_64"): "universal2"}.get(tuple(sorted(architectures)))
    if architecture is None:
        raise RuntimeError(f"Unsupported application architecture: {architectures}")
    subprocess.run(["codesign", "--verify", "--deep", "--strict", str(app)], check=True)
    target = root / "outputs" / f"AIPlayer-{version}-macOS-{architecture}.dmg"
    with tempfile.TemporaryDirectory(prefix="macos-dmg-", dir=root / "work") as folder:
        stage = Path(folder) / "AIPlayer"
        stage.mkdir()
        subprocess.run(["ditto", str(app), str(stage / app.name)], check=True)
        (stage / "Applications").symlink_to("/Applications", target_is_directory=True)
        (stage / "Установка.txt").write_text(
            "AIPlayer " + version + "\n\n"
            "Перетащите AIPlayer в Applications (Программы), затем откройте его оттуда.\n"
            "Модель распознавания загружается при первом запуске.\n\n"
            "Приложение пока без Developer ID и нотариальной проверки Apple.\n"
            "Если macOS блокирует запуск, информация и инструкция доступны на странице релиза:\n"
            "https://github.com/krikkota/AIPlayer/releases/tag/v" + version + "\n",
            encoding="utf-8",
        )
        subprocess.run(["hdiutil", "create", "-ov", "-format", "UDZO", "-volname",
                        "AIPlayer", "-srcfolder", str(stage), str(target)], check=True)
    subprocess.run(["hdiutil", "verify", str(target)], check=True)
    with target.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    metadata = dict(version=version, file=target.name, bytes=target.stat().st_size,
                    sha256=digest, platform="macOS", architecture=architecture,
                    minimum_os=info["LSMinimumSystemVersion"], signature="ad-hoc",
                    notarized=False, runtime_tested=False, models_bundled=False)
    (root / "outputs/macos-installer.json").write_text(json.dumps(metadata, indent=2) + "\n")
    (root / "outputs" / f"AIPlayer-{version}-macOS-{architecture}-SHA256.txt").write_text(
        f"{digest}  {target.name}\n"
    )
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
