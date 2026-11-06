import json
import logging
import os
import re
import shutil
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated
from urllib.parse import parse_qs, urlparse

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, Field, StringConstraints, ValidationError

# Apply the small-memory demo profile before loading the media/speech libraries.
FREE_DEMO = os.environ.get('CUTLINE_FREE_DEMO') == '1'
if FREE_DEMO:
    os.environ.update(CUTLINE_SPEECH_ENGINE='offline', CUTLINE_TEMPORARY_STORAGE='1',
                      OMP_NUM_THREADS='1', OPENCV_FOR_THREADS_NUM='1')

from . import editing, media, speech, store
from .access import PrivateSiteAuth

LOG = logging.getLogger(__name__)
POOL = ThreadPoolExecutor(max_workers=1, thread_name_prefix='cutline')
MAX_BYTES = 2*1024**3
ACTIVE={'queued','downloading','analyzing','transcribing','tracking','rendering'}
ROOT = Path(__file__).resolve().parents[1]

class Settings(BaseModel):
    mode: str = 'auto'
    start_time: float = Field(default=0,ge=0,le=7200,allow_inf_nan=False)
    end_time: float | None = Field(default=None,gt=0,le=7200,allow_inf_nan=False)
    target: int = Field(default=45, ge=15, le=120)
    count: int = Field(default=3, ge=1, le=6)
    captions: bool = True
    template: str = 'highlight'
    tracking: bool = True
    framing: str = 'auto'
    screen_layout: str = 'side_by_side'
    split_at: float = Field(default=.5,ge=.1,le=.9,allow_inf_nan=False)
    ratio: str = 'portrait'
    quality: str = '720p'
    language: str = 'auto'
    text: str = Field(default='',max_length=160)
    text_position: str = 'top'
    music_volume: float = Field(default=.15,ge=0,le=1,allow_inf_nan=False)
    voice_volume: float = Field(default=1,ge=0,le=1,allow_inf_nan=False)
    remove_music: bool = False

    def checked(self):
        if self.mode not in {'auto','range'} or self.framing not in {'auto','scene','speaker','stack'}:
            raise ValueError('Invalid clipping mode or framing.')
        if self.screen_layout not in {'side_by_side','top_bottom'}:
            raise ValueError('Choose side-by-side or top/bottom source screens.')
        if self.mode=='range' and (self.end_time is None or self.end_time-self.start_time < .25):
            raise ValueError('Choose an end time at least 0.25 seconds after the start time.')
        if self.template not in media.TEMPLATES or self.ratio not in media.RATIOS or self.text_position not in {'top','center','bottom'}:
            raise ValueError('Invalid caption style, framing, or text position.')
        if self.language not in {'auto','en','es','fr','de','pt','hi','ja','ko','it','si'}:
            raise ValueError('Unsupported transcription language.')
        if self.quality not in media.QUALITIES:
            raise ValueError('Choose 480p, 720p, or 1080p download quality.')
        return self.model_dump()


class ExportSettings(Settings):
    trim_start: float = Field(default=0, ge=0, le=7200, allow_inf_nan=False)
    trim_end: float | None = Field(default=None, gt=0, le=7200, allow_inf_nan=False)
    caption_edits: dict[str, Annotated[str, StringConstraints(max_length=120)]] = Field(default_factory=dict, max_length=20000)


def settings_from(raw, model=Settings):
    try: return model.model_validate_json(raw).checked()
    except ValidationError: raise HTTPException(422,'Check your clip settings and try again.')
    except ValueError as exc: raise HTTPException(422,str(exc))


def validate_range(config, info):
    if config.get('mode')=='range' and config['end_time'] > info['duration']:
        raise ValueError(f'The end time is beyond this video. Choose a time within its {info["duration"]:.2f} seconds.')


def prepare_framing(source, clip, config, metadata):
    frame_settings=media.resolve_framing(source,clip,config,metadata.get('auto_layout'))
    if config.get('framing')=='auto':
        metadata['auto_layout']={key:frame_settings[key] for key in ('framing','screen_layout','split_at') if key in frame_settings}
    return frame_settings


def youtube_url(url):
    try:
        parsed=urlparse(url.strip())
        if parsed.scheme not in {'https','http'}: raise ValueError()
        if parsed.username or parsed.password or parsed.port: raise ValueError()
        host=(parsed.hostname or '').lower()
        if host in {'youtube.com','www.youtube.com','m.youtube.com'}:
            identifier = parse_qs(parsed.query).get('v',[''])[0] if parsed.path=='/watch' else parsed.path.split('/')[2] if re.fullmatch(r'/(shorts|live)/[^/]+',parsed.path) else ''
        elif host=='youtu.be': identifier=parsed.path.lstrip('/')
        else: raise ValueError()
        if not re.fullmatch(r'[A-Za-z0-9_-]{11}',identifier): raise ValueError()
        return f'https://www.youtube.com/watch?v={identifier}'
    except ValueError: raise HTTPException(422,'Paste a valid YouTube video link.')


def directory(job_id):
    if not re.fullmatch(r'[a-f0-9]{32}',job_id): raise HTTPException(404,'Project not found.')
    return store.DATA/job_id


def require_job(job_id):
    directory(job_id)
    job=store.get(job_id)
    if not job: raise HTTPException(404,'Project not found.')
    return job


def public_job(job):
    result = {k:v for k,v in job.items() if k not in {'source','youtube'}}
    result['can_retry'] = job['status']=='error' and bool(job.get('youtube') or (job.get('source') and Path(job['source']).is_file()))
    return result


@asynccontextmanager
async def lifespan(app):
    for job in store.all_jobs():
        if job['status'] in ACTIVE:
            store.update(job['id'],status='error',error='Processing was interrupted when the server stopped. Retry this project to continue with the saved video.')
        for clip in job.get('clips',[]):
            if clip.get('export_status')=='processing': store.update_clip(job['id'],clip['id'],export_status='error',export_error='Export was interrupted. Please export again.')
    yield

app=FastAPI(title='Cutline Studio',lifespan=lifespan)
app.add_middleware(PrivateSiteAuth)


@app.get('/api/health')
def health():
    return {'status':'ok','ffmpeg':bool(shutil.which('ffmpeg')),'speech_model':'Bundled English recognition' if FREE_DEMO else 'Whisper with bundled English fallback','min_duration':180,'temporary_storage':os.environ.get('CUTLINE_TEMPORARY_STORAGE')=='1','free_demo':FREE_DEMO}


@app.get('/api/jobs')
def jobs(): return [public_job(j) for j in store.all_jobs()]


@app.get('/api/jobs/{job_id}')
def job(job_id:str): return public_job(require_job(job_id))


async def save_upload(upload, path, maximum=MAX_BYTES):
    size=0
    try:
        with path.open('wb') as output:
            while chunk:=await upload.read(1024*1024):
                size+=len(chunk)
                if size>maximum: raise HTTPException(413,'This file is too large. Videos can be up to 2 GB; music up to 50 MB.')
                output.write(chunk)
        if not size: raise HTTPException(422,'This file is empty.')
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    finally: await upload.close()


@app.post('/api/jobs',status_code=202)
async def create_job(settings:str=Form('{}'),url:str=Form(''),file:UploadFile|None=File(None)):
    config=settings_from(settings)
    if bool(file)==bool(url.strip()): raise HTTPException(422,'Choose either a video file or a YouTube link.')
    canonical=youtube_url(url) if url.strip() else None
    job_id=uuid.uuid4().hex
    folder=directory(job_id)
    folder.mkdir()
    source=None
    try:
        if file:
            suffix=Path(file.filename or '').suffix.lower()
            if suffix not in {'.mp4','.mov','.mkv','.webm','.m4v','.avi'}: raise HTTPException(422,'Supported videos: MP4, MOV, MKV, WebM, M4V, and AVI.')
            source=folder/f'source{suffix}'
            await save_upload(file,source)
            try:
                info=await run_in_threadpool(media.validate_source,source,config['mode']=='auto')
                validate_range(config,info)
            except ValueError as exc:
                raise HTTPException(422,str(exc))
        title=Path(file.filename).name if file and file.filename else 'YouTube video'
        record={'id':job_id,'title':title,'created_at':datetime.now(timezone.utc).isoformat(),'status':'queued','progress':0,'message':'Waiting to begin','settings':config,'clips':[],'source':str(source) if source else None,'youtube':canonical,'duration':None,'error':None}
        store.save(record)
        POOL.submit(process,job_id)
        return public_job(record)
    except BaseException:
        shutil.rmtree(folder,ignore_errors=True)
        raise


def process(job_id):
    job=None
    try:
        job=store.get(job_id)
        folder=directory(job_id)
        source=Path(job['source']) if job['source'] else None
        config=job['settings']
        manual=config.get('mode')=='range'
        if job['youtube'] and (source is None or not source.is_file()):
            store.update(job_id,status='downloading',progress=5,message='Importing your YouTube video')
            import sys
            minimum=0 if manual else 180
            media.run([sys.executable,'-m','yt_dlp','--ignore-config','--no-playlist','--js-runtimes','node','--socket-timeout','20','--retries','1','--extractor-retries','1','--max-filesize','2G','--match-filter',f'duration > {minimum} & duration <= 7200 & !is_live','-f','bv*[height<=1080]+ba/b[height<=1080]','--merge-output-format','mp4','-o',str(folder/'source.%(ext)s'),'--write-info-json','--no-progress',job['youtube']],timeout=1200)
            source=next((p for p in folder.glob('source.*') if p.suffix in {'.mp4','.mkv','.webm','.mov'}),None)
            if not source: raise ValueError('YouTube import did not produce a video. Use a public, recorded video under 2 hours, or upload the file. Automatic highlights need over 3 minutes.')
            metadata=next(folder.glob('*.info.json'),None)
            title=json.loads(metadata.read_text(encoding='utf-8')).get('title','YouTube video') if metadata else 'YouTube video'
            store.update(job_id,source=str(source),title=title)
        if source is None or not source.is_file():
            raise ValueError('The source video is no longer on this server. Upload it again to create a new project.')
        store.update(job_id,status='analyzing',progress=12,message='Checking your video and audio')
        info=media.validate_source(source,automatic=not manual)
        validate_range(config,info)
        store.update(job_id,duration=info['duration'])
        if manual:
            start,end=config['start_time'],config['end_time']
            words=[]
            if config['captions'] and info['audio']:
                store.update(job_id,status='transcribing',progress=20,message='Adding captions to your selected time range')
                try:
                    transcript=speech.transcribe(source,folder/'transcript.json',config['language'],start=start,end=end)
                    words=[dict(w,start=max(start,w['start']),end=min(end,w['end'])) for w in transcript['words'] if w['end']>start and w['start']<end]
                    store.update(job_id,language=transcript['language'],speech_engine=transcript.get('engine','whisper'))
                except speech.NoSpeechError:
                    store.update(job_id,caption_notice='No speech was detected in this range. Your clip is available without captions.')
            elif config['captions']:
                store.update(job_id,caption_notice='This video has no audio track. Your clip is available without captions.')
            title=f'{start:g}s – {end:g}s'
            candidates=[{'start':start,'end':end,'title':title,'text':' '.join(w['text'] for w in words),'words':words}]
            store.update(job_id,progress=50,message='Your exact time range is ready to render')
        else:
            store.update(job_id,status='transcribing',progress=20,message='Listening for complete thoughts. First run may download the speech model.')
            transcript=speech.transcribe(source,folder/'transcript.json',config['language'])
            candidates=speech.select_clips(transcript['words'],config['target'],config['count'])
            store.update(job_id,language=transcript['language'],speech_engine=transcript.get('engine','whisper'),message=f'Found {len(candidates)} complete moments',progress=50)
        for index,candidate in enumerate(candidates):
            candidate['end']=min(candidate['end'],info['duration'])
            # A retry resumes unfinished moments and keeps clips already made.
            if any(abs(c['start']-candidate['start'])<.001 and abs(c['end']-candidate['end'])<.001
                   for c in store.get(job_id)['clips']):
                continue
            clip_id=uuid.uuid4().hex[:12]
            prefix=f'clip-{clip_id}'
            store.update(job_id,status='tracking',progress=50+int(index/len(candidates)*45),message=f'Preparing the framing for clip {index+1} of {len(candidates)}')
            metadata={'clip':candidate,'tracking':[],'tracking_version':0}
            frame_settings=prepare_framing(source,candidate,config,metadata)
            points=[]
            if frame_settings.get('tracking',True) and frame_settings.get('framing')=='speaker':
                points=media.track_speaker(source,candidate['start'],candidate['end'],words=candidate['words'] or None)
                metadata['tracking_version']=media.TRACKING_VERSION
            metadata['tracking']=points
            (folder/f'{prefix}.json').write_text(json.dumps(metadata),encoding='utf-8')
            store.update(job_id,status='rendering',message=f'Creating clip {index+1} of {len(candidates)}')
            clean=folder/f'{prefix}-clean.mp4'
            media.render(source,clean,candidate,frame_settings,points,clean=True)
            output=folder/f'{prefix}.mp4'
            if config['captions'] or config.get('text'):
                media.render(source,output,candidate,frame_settings,points)
            else: shutil.copyfile(clean,output)
            thumb=folder/f'{prefix}.jpg'
            media.thumbnail(clean,thumb,timestamp=min(1,(candidate['end']-candidate['start'])/2))
            clip={'id':clip_id,'kind':'range' if manual else 'auto','title':candidate['title'],'start':candidate['start'],'end':candidate['end'],'duration':round(candidate['end']-candidate['start'],3),'transcript':candidate['text'],'words':[dict(w,start=round(w['start']-candidate['start'],3),end=round(w['end']-candidate['start'],3)) for w in candidate['words']],'url':f'/media/{job_id}/{output.name}','clean_url':f'/media/{job_id}/{clean.name}','thumbnail':f'/media/{job_id}/{thumb.name}','tracked':bool(points),'export_status':'idle','settings':config}
            clip['resolved_framing']=frame_settings.get('framing','speaker')
            if candidate['words']:
                editing.write_srt(output.with_suffix('.srt'),candidate)
                clip['captions_url']=f'/media/{job_id}/{output.stem}.srt'
            current=store.get(job_id)
            store.update(job_id,clips=current['clips']+[clip])
        store.update(job_id,status='completed',progress=100,message='Your clips are ready')
    except Exception as exc:
        LOG.exception('Processing failed for %s',job_id)
        detail=str(exc)
        if 'huggingface' in detail.lower(): detail='The speech model could not be loaded. Check server network access to Hugging Face, then try again.'
        if job and job.get('youtube') and 'Tunnel connection failed' in detail: detail='This workspace cannot reach YouTube. Enable the YouTube domains in environment network settings, or upload the video file instead.'
        elif job and job.get('youtube') and ('Sign in' in detail or '403' in detail or 'not a bot' in detail): detail='YouTube blocked this download or requires sign-in. Please upload the video file instead.'
        store.update(job_id,status='error',error=detail[-700:],message='This video needs another try')


@app.post('/api/jobs/{job_id}/retry',status_code=202)
def retry_job(job_id:str):
    with store.LOCK:
        job=require_job(job_id)
        if job['status']!='error' or any(c.get('export_status')=='processing' for c in job['clips']):
            raise HTTPException(409,'Only a failed project with no active exports can be retried.')
        if not public_job(job)['can_retry']:
            raise HTTPException(409,'The source video is no longer on this server. Upload it again.')
        store.update(job_id,status='queued',progress=0,error=None,caption_notice=None,message='Queued to resume with your saved video')
        try:
            POOL.submit(process,job_id)
        except Exception:
            store.update(job_id,status='error',error='The worker is unavailable. Restart the server and retry.')
            raise HTTPException(503,'The worker is unavailable. Restart the server and retry.')
        return public_job(store.get(job_id))


@app.post('/api/jobs/{job_id}/clips/{clip_id}/export',status_code=202)
async def export(job_id:str,clip_id:str,settings:str=Form('{}'),music:UploadFile|None=File(None)):
    config=settings_from(settings,ExportSettings)
    with store.LOCK:
        job=require_job(job_id)
        clip=next((c for c in job['clips'] if c['id']==clip_id),None)
        if not clip: raise HTTPException(404,'Clip not found.')
        if job['status'] in ACTIVE: raise HTTPException(409,'Wait for this project to finish processing before exporting.')
        if clip.get('export_status')=='processing': raise HTTPException(409,'This clip is already exporting.')
        try:
            # Public word timestamps are relative to the original clip.
            editing.apply_edits({'start':0,'end':clip['end']-clip['start'],'words':clip['words']},config)
        except ValueError as exc:
            raise HTTPException(422,str(exc))
        previous={key:clip.get(key) for key in ('export_status','export_error')}
        # Claim before the first await; uploading music must also block a
        # second export or deletion of the project.
        store.update_clip(job_id,clip_id,export_status='processing',export_error=None)
    music_path=None
    music_name=None
    try:
        if music:
            music_name=Path(music.filename or 'Your soundtrack').name
            suffix=Path(music_name).suffix.lower()
            if suffix not in {'.mp3','.wav','.m4a','.aac','.ogg','.flac','.webm'}: suffix='.audio'
            music_path=directory(job_id)/f'music-{uuid.uuid4().hex}{suffix}'
            await save_upload(music,music_path,50*1024**2)
            try:
                if not (await run_in_threadpool(media.probe,music_path))['audio']:
                    raise ValueError('Choose a music file with an audio track.')
            except ValueError:
                raise HTTPException(422,'This music file could not be read. Choose a valid MP3, WAV, or other audio file.')
        elif clip.get('music_file') and not config['remove_music']:
            music_path=directory(job_id)/clip['music_file']
            music_name=clip.get('music_name','Your soundtrack')
        POOL.submit(render_export,job_id,clip_id,config,music_path,music_name)
    except BaseException:
        if music and music_path:
            music_path.unlink(missing_ok=True)
        store.update_clip(job_id,clip_id,**previous)
        raise
    return {'status':'processing'}


def render_export(job_id,clip_id,config,music,music_name=None):
    output=None
    try:
        job=store.get(job_id)
        folder=directory(job_id)
        metadata=json.loads((folder/f'clip-{clip_id}.json').read_text(encoding='utf-8'))
        source=Path(job['source'])
        frame_settings=prepare_framing(source,metadata['clip'],config,metadata)
        points=metadata['tracking']
        if frame_settings.get('tracking',True) and frame_settings.get('framing')=='speaker' and metadata.get('tracking_version')!=media.TRACKING_VERSION:
            points=media.track_speaker(source,metadata['clip']['start'],metadata['clip']['end'],words=metadata['clip']['words'] or None)
            metadata['tracking']=points
            metadata['tracking_version']=media.TRACKING_VERSION
        (folder/f'clip-{clip_id}.json').write_text(json.dumps(metadata),encoding='utf-8')
        edited=editing.apply_edits(metadata['clip'],config)
        offset=edited['start']-metadata['clip']['start']
        points=editing.trim_tracking(points,offset,edited['end']-metadata['clip']['start'])
        output=folder/f'export-{clip_id}-{config["quality"]}-{uuid.uuid4().hex[:8]}.mp4'
        media.render(source,output,edited,frame_settings,points,music=music)
        captions_url=None
        if edited['words']:
            editing.write_srt(output.with_suffix('.srt'),edited)
            captions_url=f'/media/{job_id}/{output.stem}.srt'
        store.update_clip(job_id,clip_id,export_status='completed',export_url=f'/media/{job_id}/{output.name}',export_settings=config,export_framing=frame_settings.get('framing','speaker'),export_duration=round(edited['end']-edited['start'],3),export_captions_url=captions_url,export_error=None,music_file=music.name if music else None,music_name=music_name,music_url=f'/media/{job_id}/{music.name}' if music else None)
    except Exception as exc:
        LOG.exception('Export failed')
        if output:
            for path in (output,output.with_suffix('.ass'),output.with_suffix('.tracking.txt'),output.with_suffix('.srt')):
                path.unlink(missing_ok=True)
        store.update_clip(job_id,clip_id,export_status='error',export_error=str(exc)[-600:])


@app.delete('/api/jobs/{job_id}',status_code=204)
def delete_job(job_id:str):
    with store.LOCK:
        job=require_job(job_id)
        if job['status'] in ACTIVE or any(c.get('export_status')=='processing' for c in job.get('clips',[])): raise HTTPException(409,'Wait for processing to finish before deleting this project.')
        shutil.rmtree(directory(job_id),ignore_errors=True)
        store.delete(job_id)


@app.get('/media/{job_id}/{filename}')
def media_file(job_id:str,filename:str,download:bool=False):
    require_job(job_id)
    if not re.fullmatch(r'[a-zA-Z0-9_.-]+',filename) or Path(filename).suffix not in {'.mp4','.jpg','.mp3','.wav','.m4a','.aac','.ogg','.flac','.webm','.audio','.srt'}: raise HTTPException(404,'Media not found.')
    path=directory(job_id)/filename
    if not path.is_file(): raise HTTPException(404,'Media not found.')
    return FileResponse(path,filename=filename if download else None,content_disposition_type='attachment' if download else 'inline')

DIST=ROOT/'frontend'/'dist'
if DIST.exists():
    app.mount('/',StaticFiles(directory=DIST,html=True),name='website')
