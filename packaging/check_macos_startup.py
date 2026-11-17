"""Mount the release DMG, copy its app, and check native first launch."""
import argparse
import json
import os
from pathlib import Path
import plistlib
import struct
import subprocess


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dmg", required=True)
    parser.add_argument("--report-root", required=True)
    parser.add_argument("--media")
    args = parser.parse_args()
    report = Path(args.report_root).resolve()
    report.mkdir(parents=True, exist_ok=True)
    mount = report / "mounted-image"
    mount.mkdir(exist_ok=True)
    app = report / "Установка плеера/AIPlayer.app"
    if app.exists():
        raise RuntimeError("Use a fresh report directory to test a clean install")
    subprocess.run(["hdiutil", "attach", "-readonly", "-nobrowse", "-mountpoint",
                    str(mount), str(Path(args.dmg).resolve())], check=True)
    try:
        assert (mount / "Applications").is_symlink()
        subprocess.run(["ditto", str(mount / "AIPlayer.app"), str(app)], check=True)
    finally:
        subprocess.run(["hdiutil", "detach", str(mount)], check=True)
    subprocess.run(["codesign", "--verify", "--deep", "--strict", str(app)], check=True)
    with (app / "Contents/Info.plist").open("rb") as stream:
        version = plistlib.load(stream)["CFBundleShortVersionString"]
    results = {"version": version, "cases": []}
    for name in ["first-launch", "finder-launch"] + (["playback"] if args.media else []):
        folder = report / name
        folder.mkdir()
        data = folder / "Чистые настройки"
        data.mkdir()
        if name == "playback":
            (data / "settings.json").write_text(json.dumps({"onboarded": True}))
        env = {**os.environ, "QT_QPA_PLATFORM": "cocoa", "AIPLAYER_STARTUP_CHECK": "1",
               "AIPLAYER_STARTUP_LOG": str(folder / "startup.log")}
        options = ["--data-dir", str(data), "--quit-after", "6500", "--mute"]
        if name != "finder-launch":
            options += ["--screenshot", str(folder / "first-window.png")]
            command = [str(app / "Contents/MacOS/AIPlayer"), *options]
        else:
            command = ["open", "-n", "-W", "--env", "QT_QPA_PLATFORM=cocoa",
                       "--env", "AIPLAYER_STARTUP_CHECK=1", "--env",
                       "AIPLAYER_STARTUP_LOG=" + str(folder / "startup.log"),
                       "--stdout", str(folder / "app-stdout.log"),
                       "--stderr", str(folder / "app-stderr.log"),
                       str(app), "--args", *options]
        if name == "playback":
            command.append(str(Path(args.media).resolve()))
        with (folder / "stdout.log").open("wb") as out, (folder / "stderr.log").open("wb") as err:
            process = subprocess.run(command, env=env, stdout=out, stderr=err, timeout=45)
        log = (folder / "startup.log").read_text()
        assert process.returncode == 0 and "EXIT 0" in log, f"{name}: launch failed; see {folder}"
        assert "Traceback" not in log and "QQmlApplicationEngine failed" not in log
        item = dict(name=name, exit_code=process.returncode)
        if name != "finder-launch":
            header = (folder / "first-window.png").read_bytes()[:24]
            assert header[:8] == b"\x89PNG\r\n\x1a\n"
            item["dimensions"] = struct.unpack(">II", header[16:24])
            assert min(item["dimensions"]) >= 300
        if name == "playback":
            import ast
            output = (folder / "stdout.log").read_text()
            state = ast.literal_eval(output.split("PLAYER_STATE ", 1)[1].splitlines()[0])
            assert state["hasVideo"] == "True" and state["errorString"] == "", state
            assert int(state["duration"]) > 0 and int(state["position"]) > 0, state
            item["player"] = state
        results["cases"].append(item)
    results["passed"] = True
    (report / "result.json").write_text(json.dumps(results, indent=2))
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
