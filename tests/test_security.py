import hashlib
import io
import json
import os
from pathlib import Path
from threading import Event

import pytest

from player import models
from player.jobs import Cancelled
from player.security import local_media_path
from player.storage import Store, read_json, read_transcript
from player import media


@pytest.mark.parametrize("value", ["https://example.com/a.mp4", "file://remote/a.wav",
    "file:////remote/a.wav", "concat:a.mp4|b.mp4", "\\\\host\\video.mp4", "a\x00.mp4"])
def test_remote_and_protocol_sources_are_rejected(value):
    with pytest.raises((ValueError,OSError)):
        local_media_path(value)


def test_disguised_playlist_never_reaches_decoder(tmp_path):
    path=tmp_path/"recording.mp4"
    path.write_text('#EXTM3U\nhttp://127.0.0.1:9/private\n')
    with pytest.raises(ValueError,match="Плейлисты"):
        local_media_path(path)
    path.write_bytes(b'\x00\x00\x00\x18ftypisom'+b'\0'*20)
    assert local_media_path(path.as_uri())==path


def test_cli_decoder_rejects_playlist_demuxer(tmp_path):
    path=tmp_path/'bad.m3u8'
    path.write_text('#EXTM3U\n#EXT-X-TARGETDURATION:5\n#EXTINF:5,\nhttp://127.0.0.1:9/private\n#EXT-X-ENDLIST\n')
    with pytest.raises(RuntimeError):
        media.process(['-i',str(path),'-f','null','-'],Event())


@pytest.mark.parametrize("value", [[],None,42,{"onboarded":"yes","recent":123,"asr_path":[],"semantic_model":False}])
def test_damaged_settings_do_not_crash_or_skip_onboarding(tmp_path,value):
    (tmp_path/'settings.json').write_text(json.dumps(value))
    store=Store(tmp_path)
    assert store.settings['onboarded'] is False
    assert store.settings['recent']==[]


def test_corrupt_transcript_and_large_json_are_ignored(tmp_path):
    path=tmp_path/'transcript.json'
    for row in [dict(start=-1,end=2,text='bad'),dict(start=0,end=float('nan'),text='bad'),dict(start=0,end=2,text=[])]:
        path.write_text(json.dumps(dict(complete=True,segments=[row])))
        assert read_transcript(path)=={}
    path.write_text('x'*20)
    assert read_json(path,{},max_bytes=10)=={}
    with pytest.raises(ValueError):Store(tmp_path).cache('../../outside','json')


class Response(io.BytesIO):
    def __init__(self,content,status=200,headers=None):
        super().__init__(content);self.status=status;self.headers=headers or {}


def artifact(monkeypatch):
    payload=b'a verified model with a fixed digest'
    monkeypatch.setattr(models,'FILES',{'model.int8.onnx':('remote.onnx',len(payload),hashlib.sha256(payload).hexdigest())})
    return payload


def test_download_resumes_only_a_verified_range(monkeypatch,tmp_path):
    payload=artifact(monkeypatch)
    folder=tmp_path/'models/gigaam-v3';folder.mkdir(parents=True)
    partial=folder/'model.int8.onnx.part';partial.write_bytes(payload[:8])
    class Opener:
        def open(self,request,timeout):
            assert request.get_header('Range')=='bytes=8-'
            assert request.full_url.startswith('https://')
            return Response(payload[8:],206,{'Content-Range':f'bytes 8-{len(payload)-1}/{len(payload)}'})
    monkeypatch.setattr(models.urllib.request,'build_opener',lambda *a:Opener())
    models.download(tmp_path,Event(),lambda _:None)
    assert (folder/'model.int8.onnx').read_bytes()==payload and not partial.exists()


@pytest.mark.parametrize('kind',['oversized','corrupted','range'])
def test_bad_download_is_never_published(monkeypatch,tmp_path,kind):
    payload=artifact(monkeypatch)
    class Opener:
        def open(self,*args,**kw):
            return (Response(payload,206,{'Content-Range':'bytes 5-9/100'}) if kind=='range'
                    else Response(payload+b'extra' if kind=='oversized' else b'x'*len(payload)))
    monkeypatch.setattr(models.urllib.request,'build_opener',lambda *a:Opener())
    with pytest.raises(ValueError):models.download(tmp_path,Event(),lambda _:None)
    assert not (tmp_path/'models/gigaam-v3/model.int8.onnx').exists()


def test_cancelled_download_can_be_resumed_without_network(monkeypatch,tmp_path):
    payload=artifact(monkeypatch);cancel=Event()
    class Opener:
        def open(self,*a,**kw):return Response(payload)
    monkeypatch.setattr(models.urllib.request,'build_opener',lambda *a:Opener())
    with pytest.raises(Cancelled):models.download(tmp_path,cancel,lambda _:cancel.set())
    assert models.download_status(tmp_path)['setupCanResume']
    class NoNetwork:
        def open(self,*a,**kw):raise AssertionError('verified partial must not be downloaded twice')
    monkeypatch.setattr(models.urllib.request,'build_opener',lambda *a:NoNetwork())
    models.download(tmp_path,Event(),lambda _:None)
    assert (tmp_path/'models/gigaam-v3/model.int8.onnx').read_bytes()==payload


@pytest.mark.skipif(os.name=='nt',reason='symbolic links require Windows privileges')
def test_download_does_not_follow_staging_symlink(monkeypatch,tmp_path):
    artifact(monkeypatch)
    outside=tmp_path/'private';outside.write_text('keep')
    folder=tmp_path/'models/gigaam-v3';folder.mkdir(parents=True)
    (folder/'model.int8.onnx.part').symlink_to(outside)
    with pytest.raises(ValueError,match='ссылк'):models.download(tmp_path,Event(),lambda _:None)
    assert outside.read_text()=='keep'


def test_decoder_runtime_does_not_allow_network_protocols():
    assert os.environ['QT_MEDIA_BACKEND']=='ffmpeg'
    assert os.environ['QT_FFMPEG_PROTOCOL_WHITELIST']=='file'


def test_concurrent_model_download_has_an_exclusive_lock(monkeypatch,tmp_path):
    from PySide6.QtCore import QLockFile
    artifact(monkeypatch)
    folder=tmp_path/'models';folder.mkdir()
    lock=QLockFile(str(folder/'gigaam-download.lock'));assert lock.tryLock(0)
    try:
        if os.name!='nt':
            os.utime(folder/'gigaam-download.lock',(1,1))  # a long-running download is still the live owner
        with pytest.raises(ValueError,match='другом окне'):
            models.download(tmp_path,Event(),lambda _:None)
    finally:
        lock.unlock()


def test_export_race_does_not_overwrite_another_file(monkeypatch,tmp_path):
    source=tmp_path/'source.wav';source.write_bytes(b'original')
    target=tmp_path/'clip.wav'
    def other_program_writes(arguments,cancel):
        Path(arguments[-1]).write_bytes(b'encoded')
        target.write_bytes(b'created by another program')
    monkeypatch.setattr(media,'process',other_program_writes)
    with pytest.raises(FileExistsError):
        media.export_clip(source,target,0,1,False,Event(),lambda _:None)
    assert source.read_bytes()==b'original'
    assert target.read_bytes()==b'created by another program'
    assert not list(tmp_path.glob('.aiplayer-*'))


def test_model_is_reverified_before_inference(monkeypatch,tmp_path):
    from player import asr
    monkeypatch.setattr(asr,'resolve_files',lambda _: {'model.int8.onnx':tmp_path/'untrusted.onnx'})
    monkeypatch.setattr(asr,'verify',lambda *a:False)
    calls=[]
    monkeypatch.setattr(asr.ort,'InferenceSession',lambda *a,**kw:calls.append(True))
    with pytest.raises(ValueError,match='Модель'):
        asr.transcribe(tmp_path/'audio.wav',tmp_path,Event(),lambda _:None)
    assert not calls


def test_windowed_build_delivers_errors_without_console(monkeypatch):
    import sys
    from player.jobs import Job
    def fail(*a):raise ValueError('recoverable download error')
    job=Job(fail);errors=[];finished=[]
    job.events.error.connect(errors.append)
    job.events.finished.connect(lambda:finished.append(True))
    monkeypatch.setattr(sys,'stderr',None)
    job.run()
    assert errors==['recoverable download error'] and finished
