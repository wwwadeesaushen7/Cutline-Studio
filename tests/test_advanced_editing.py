import asyncio
import importlib
import json
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend import editing, media, speech, store

api = importlib.import_module('backend.app')


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.setattr(store, 'DATA', tmp_path / 'data')
    store.DATA.mkdir()
    monkeypatch.setattr(api.POOL, 'submit', lambda fn, *args: fn(*args))
    monkeypatch.setattr(speech, 'transcribe', lambda *a, **kw: {'language':'en', 'words':[
        {'start':.2, 'end':.8, 'text':'Wrong'}, {'start':1, 'end':1.5, 'text':'word'},
        {'start':1.6, 'end':2.2, 'text':'hide'}, {'start':2.5, 'end':3, 'text':'ending.'}]})
    source = tmp_path / 'sample.mp4'
    media.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=blue:s=160x90:r=10',
               '-f','lavfi','-i','sine=frequency=440:sample_rate=16000','-t','3.5',
               '-c:v','libx264','-threads','1','-c:a','aac',str(source)])
    with TestClient(api.app) as client:
        response = client.post('/api/jobs', files={'file':('sample.mp4',source.read_bytes())},
            data={'settings':json.dumps({'mode':'range','start_time':0,'end_time':3.5,
                                        'framing':'scene','quality':'480p'})})
        assert response.status_code == 202
        job = store.get(response.json()['id'])
        assert job['status'] == 'completed', job.get('error')
        yield client, job, job['clips'][0]


def test_edits_survive_quality_change_and_preserve_original(project):
    client, job, original = project
    settings = dict(original['settings'], trim_start=.5, trim_end=2.5,
                    caption_edits={'0':'Corrected', '2':''}, text='My title')
    for quality in ['480p','720p']:
        settings['quality'] = quality
        response = client.post(f"/api/jobs/{job['id']}/clips/{original['id']}/export",
                               data={'settings':json.dumps(settings)})
        assert response.status_code == 202, response.text
        clip = client.get('/api/jobs/'+job['id']).json()['clips'][0]
        assert clip['export_status'] == 'completed', clip.get('export_error')
        assert clip['export_duration'] == 2
        assert clip['words'] == original['words']
        assert clip['url'] == original['url']
        assert clip['export_settings']['caption_edits'] == settings['caption_edits']
        path = api.directory(job['id']) / Path(clip['export_url']).name
        info = media.probe(path)
        assert info['duration'] == pytest.approx(2, abs=.1)
        assert info['video']['width'] == int(quality[:-1])
        ass = path.with_suffix('.ass').read_text()
        assert 'Corrected' in ass and 'My title' in ass
        assert 'Wrong' not in ass and 'hide' not in ass and 'ending.' not in ass
        result = client.get(clip['export_captions_url']+'?download=true')
        assert result.status_code == 200
        assert 'attachment' in result.headers['content-disposition']
        assert '00:00:00,000 --> 00:00:01,120' in result.text
        assert 'Corrected word' in result.text


@pytest.mark.parametrize('change',[
    {'trim_start':3,'trim_end':1}, {'trim_end':4}, {'trim_start':float('nan')},
    {'caption_edits':{'100':'unknown'}}, {'caption_edits':{'-1':'unknown'}},
    {'caption_edits':{'0':'a'*121}}, {'music_volume':float('nan')}
])
def test_bad_edits_leave_clip_available(project,change):
    client, job, clip = project
    response=client.post(f"/api/jobs/{job['id']}/clips/{clip['id']}/export",
                         data={'settings':json.dumps(dict(clip['settings'],**change))})
    assert response.status_code == 422
    assert store.get(job['id'])['clips'][0]['export_status'] == 'idle'


def test_retry_keeps_finished_clips_and_does_not_redownload(project,monkeypatch):
    client, job, clip = project
    store.update(job['id'],status='error',error='Interrupted',youtube='https://youtu.be/abcdefghijk')
    real_run = media.run
    def forbid_download(args, **kwargs):
        assert 'yt_dlp' not in args
        return real_run(args,**kwargs)
    monkeypatch.setattr(media,'run',forbid_download)
    assert client.get('/api/jobs/'+job['id']).json()['can_retry']
    response=client.post(f"/api/jobs/{job['id']}/retry")
    assert response.status_code == 202
    result=store.get(job['id'])
    assert result['status'] == 'completed'
    assert result['clips'] == [clip]
    assert client.post(f"/api/jobs/{job['id']}/retry").status_code == 409


def test_retry_missing_upload_explains_recovery(project):
    client, job, clip = project
    Path(job['source']).unlink()
    store.update(job['id'],status='error')
    assert not client.get('/api/jobs/'+job['id']).json()['can_retry']
    assert client.post(f"/api/jobs/{job['id']}/retry").status_code == 409


def test_export_claim_blocks_second_request_and_delete_while_uploading(project,monkeypatch):
    _, job, clip = project
    class Upload:
        filename='broken.wav'
    async def check():
        started, resume = asyncio.Event(), asyncio.Event()
        async def upload(*args):
            started.set()
            await resume.wait()
            raise HTTPException(422,'Invalid music')
        monkeypatch.setattr(api,'save_upload',upload)
        task=asyncio.create_task(api.export(job['id'],clip['id'],music=Upload(),settings='{}'))
        await started.wait()
        with pytest.raises(HTTPException) as duplicate:
            await api.export(job['id'],clip['id'],music=None,settings='{}')
        assert duplicate.value.status_code == 409
        with pytest.raises(HTTPException) as deletion:
            api.delete_job(job['id'])
        assert deletion.value.status_code == 409
        resume.set()
        with pytest.raises(HTTPException):
            await task
        assert store.get(job['id'])['clips'][0]['export_status'] == 'idle'
    asyncio.run(check())


def test_trim_path_never_interpolates_across_speaker_cut():
    points=[{'time':0,'x':.2},{'time':1,'x':.8,'cut':True},{'time':2,'x':.9}]
    path=editing.trim_tracking(points,.5,1.5)
    assert path == [{'time':0,'x':.2,'cut':False},{'time':.5,'x':.8,'cut':True}]
    assert editing.trim_tracking(points,1,2)[0]['x'] == .8


def test_caption_time_carry_and_silence_boundaries(tmp_path):
    assert media.ass_time(59.999) == '0:01:00.00'
    assert editing.srt_time(3599.9999) == '01:00:00,000'
    clip={'start':0,'end':10,'words':[{'start':0,'end':1,'text':'First'},
                                   {'start':8,'end':9,'text':'Last'}]}
    srt=tmp_path/'captions.srt'
    editing.write_srt(srt,clip)
    assert '00:00:00,000 --> 00:00:01,120' in srt.read_text()
    assert '00:00:08,000 --> 00:00:09,120' in srt.read_text()
