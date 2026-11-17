import threading
import subprocess

import numpy as np
import pytest
import soundfile as sf

from player.media import export_clip, prepare_audio, ffmpeg
from player.storage import media_key


def test_exact_audio_export_does_not_overwrite_source_or_destination(tmp_path):
    source=tmp_path/"исходник.wav"
    sf.write(source,np.sin(np.arange(48000)*.1),16000)
    before=media_key(source)
    target=tmp_path/"фрагмент.wav"
    export_clip(source,target,.4,1.65,False,threading.Event(),lambda _:None)
    with sf.SoundFile(target) as result:
        assert result.frames/result.samplerate == pytest.approx(1.25,abs=.005)
    assert media_key(source)==before
    with pytest.raises(ValueError,match="существует"):
        export_clip(source,target,0,1,False,threading.Event(),lambda _:None)
    with pytest.raises(ValueError,match="новый файл"):
        export_clip(source,source,0,1,False,threading.Event(),lambda _:None)


def test_silent_audio_waveform_has_no_nan(tmp_path):
    source=tmp_path/"silence.wav"
    sf.write(source,np.zeros(16000),16000)
    result=prepare_audio(source,tmp_path/"prepared.wav",threading.Event(),lambda _:None)
    assert result["duration"]==pytest.approx(1)
    assert len(result["waveform"])==900
    assert np.isfinite(result["waveform"]).all()
    assert max(result["waveform"])==0


def test_video_cut_starts_on_requested_frame_between_keyframes(tmp_path):
    source = tmp_path / "длинный-gop.mp4"
    target = tmp_path / "точный-фрагмент.mp4"
    subprocess.run([ffmpeg(), "-nostdin", "-v", "error", "-f", "lavfi", "-i",
                    "testsrc2=size=96x64:rate=25:duration=3", "-f", "lavfi", "-i",
                    "sine=frequency=440:sample_rate=48000:duration=3", "-c:v", "libx264",
                    "-g", "250", "-sc_threshold", "0", "-c:a", "aac", str(source)], check=True)
    before = media_key(source)
    export_clip(source, target, .44, 1.76, True, threading.Event(), lambda _: None)
    def frames(path, select=None):
        args = [ffmpeg(), "-nostdin", "-v", "error", "-i", str(path), "-an"]
        if select:
            args += ["-vf", select, "-frames:v", "1"]
        raw = subprocess.check_output([*args, "-pix_fmt", "rgb24", "-f", "rawvideo", "-"])
        return np.frombuffer(raw, dtype=np.uint8).reshape(-1, 64, 96, 3)
    result = frames(target)
    expected_first = frames(source, "select=eq(n\\,11)")[0]
    assert len(result) == 33  # 1.32 seconds at 25 fps, including the exact first frame.
    assert np.abs(result[0].astype(float) - expected_first.astype(float)).mean() < 4
    audio = subprocess.check_output([ffmpeg(), "-nostdin", "-v", "error", "-i", str(target),
                                     "-vn", "-ac", "1", "-ar", "48000", "-f", "f32le", "-"])
    assert len(audio) / 4 / 48000 == pytest.approx(1.32, abs=.03)
    assert media_key(source) == before
    assert not list(tmp_path.glob(".*.export*"))

