// Runs the built website against an isolated, deterministic media fixture.
import { chromium } from 'playwright';
import assert from 'node:assert/strict';
import { mkdtempSync, rmSync, renameSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { execFileSync, spawn } from 'node:child_process';
import { createServer } from 'node:net';

const root=resolve('..'), folder=mkdtempSync(join(tmpdir(),'cutline-editor-'));
const python=join(root,'.venv','bin','python');
const env={...process.env,CUTLINE_DATA_DIR:folder,CUTLINE_FREE_DEMO:'1',CUTLINE_REQUIRE_AUTH:'0',CUTLINE_SITE_USERNAME:'',CUTLINE_SITE_PASSWORD:''};
const seed=`
import importlib,json,uuid
from datetime import datetime,timezone
from backend import media,speech,store
api=importlib.import_module('backend.app')
job_id=uuid.uuid4().hex
folder=store.DATA/job_id
folder.mkdir()
source=folder/'source.mp4'
media.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=blue:s=320x180:r=10','-f','lavfi','-i','sine=frequency=440:sample_rate=16000','-t','3.5','-c:v','libx264','-threads','1','-c:a','aac',str(source)])
words=[{'start':.2,'end':.8,'text':'Wrong'},{'start':1,'end':1.5,'text':'word'},{'start':1.6,'end':2.2,'text':'remove'},{'start':2.5,'end':3,'text':'ending.'}]
speech.transcribe=lambda *a,**kw:dict(language='en',words=words)
config=api.Settings(mode='range',end_time=3.5,framing='scene',quality='480p').checked()
store.save(dict(id=job_id,title='Editor regression',created_at=datetime.now(timezone.utc).isoformat(),source=str(source),youtube=None,settings=config,status='queued',progress=0,clips=[]))
api.process(job_id)
job=store.get(job_id)
assert job['status']=='completed',job.get('error')
print(json.dumps(job))
`;
let server,browser;
try {
  const job=JSON.parse(execFileSync(python,['-c',seed],{cwd:root,env,encoding:'utf8'}));
  const socket=createServer(); await new Promise(resolve=>socket.listen(0,'127.0.0.1',resolve));
  const port=socket.address().port; await new Promise(resolve=>socket.close(resolve));
  server=spawn(python,['-m','uvicorn','backend.app:app','--host','127.0.0.1','--port',String(port),'--lifespan','on'],{cwd:root,env,stdio:'ignore'});
  const baseURL=`http://127.0.0.1:${port}`;
  let ready=false;
  for(let i=0;i<100;i++){try{ready=(await fetch(baseURL+'/api/health')).ok;}catch{}if(ready)break;await new Promise(r=>setTimeout(r,100));}
  assert(ready,'Isolated processing server started');
  browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
  const page=await browser.newPage({baseURL,viewport:{width:1440,height:1000}});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('/');
  await page.locator('.nav-item').filter({hasText:'My projects'}).click();
  const project=page.locator(`[data-project-id="${job.id}"]`);
  await project.getByRole('button',{name:'Make it yours'}).click();
  await page.getByText('Edit caption words',{exact:false}).click();
  await page.getByRole('textbox',{name:'Caption word 1',exact:true}).fill('Corrected');
  await page.getByRole('textbox',{name:'Caption word 3',exact:true}).fill('');
  await page.getByRole('button',{name:'Trim',exact:true}).click();
  await page.getByRole('spinbutton',{name:'Trim start',exact:true}).fill('2.6');
  await page.getByRole('spinbutton',{name:'Trim end',exact:true}).fill('2.5');
  assert(await page.getByRole('button',{name:'Export clip',exact:true}).isDisabled());
  await page.getByRole('spinbutton',{name:'Trim start',exact:true}).fill('0.5');
  await page.getByRole('button',{name:'Text',exact:true}).click();
  await page.getByRole('textbox',{name:'Your text',exact:false}).fill('My corrected clip');
  await page.getByRole('button',{name:'Export clip',exact:true}).click();
  assert(await page.getByRole('combobox',{name:'Download quality',exact:true}).isDisabled());
  await page.getByRole('link',{name:/Your MP4 is ready/}).waitFor({timeout:45000});
  const captionLink=page.getByRole('link',{name:'Download captions (.srt)',exact:true});
  const srt=await (await page.request.get(await captionLink.getAttribute('href'))).text();
  assert(srt.includes('Corrected word')&&!srt.includes('remove')&&!srt.includes('ending'));
  await page.getByRole('button',{name:'Exported video',exact:true}).click();
  await page.waitForFunction(()=>{const v=document.querySelector('.video-stage video');return v?.readyState>=1&&Math.abs(v.duration-2)<.15;});
  assert.equal(await page.locator('.live-caption,.custom-overlay').count(),0,'Export preview does not double-burn captions/text');
  assert.equal(await page.locator('.video-stage video').evaluate(v=>v.volume),1);
  for(const width of [320,390,768,1440]){
    await page.setViewportSize({width,height:900});
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`Editor overflow at ${width}`);
  }
  await page.keyboard.press('Escape');
  await project.getByRole('button',{name:'Make it yours'}).click();
  await page.getByRole('button',{name:'Trim',exact:true}).click();
  assert.equal(await page.getByRole('spinbutton',{name:'Trim start',exact:true}).inputValue(),'0.5');
  assert.equal(await page.getByRole('spinbutton',{name:'Trim end',exact:true}).inputValue(),'2.5');
  await page.getByRole('button',{name:'Captions',exact:true}).click();
  await page.getByText('Edit caption words',{exact:false}).click();
  assert.equal(await page.getByRole('textbox',{name:'Caption word 1',exact:true}).inputValue(),'Corrected');
  await page.getByRole('combobox',{name:'Download quality',exact:true}).selectOption('720p');
  await page.getByRole('button',{name:'Export clip',exact:true}).click();
  await page.getByRole('link',{name:/Your MP4 is ready/}).waitFor({timeout:45000});
  const downloadPromise=page.waitForEvent('download');
  await page.getByRole('link',{name:/Your MP4 is ready/}).click();
  const downloaded=join(folder,'verified.mp4');await (await downloadPromise).saveAs(downloaded);
  const info=JSON.parse(execFileSync('ffprobe',['-v','error','-show_format','-show_streams','-of','json',downloaded],{encoding:'utf8'}));
  assert.equal(info.streams.find(s=>s.codec_type==='video').width,720);
  assert(Math.abs(Number(info.format.duration)-2)<.15);
  await page.keyboard.press('Escape');
  await project.getByRole('button',{name:`Download ${job.clips[0].title}`,exact:true}).click();
  await page.getByRole('combobox',{name:'Download quality',exact:true}).selectOption('1080p');
  renameSync(job.source,job.source+'.saved');
  try {
    await page.getByRole('button',{name:'Prepare download',exact:true}).click();
    await page.getByRole('alert').filter({hasText:/No such file|not found/}).waitFor({timeout:30000});
    assert.equal(await page.getByRole('link',{name:/Download 1080p MP4/}).count(),0,'A failed export must not label the old download as the new quality');
  } finally {renameSync(job.source+'.saved',job.source);}
  await page.getByRole('button',{name:'Prepare download',exact:true}).click();
  await page.getByRole('link',{name:'Download 1080p MP4',exact:true}).waitFor({timeout:45000});
  await page.keyboard.press('Escape');
  // Turn only the isolated fixture into an interrupted project, then exercise Retry.
  execFileSync(python,['-c',`from backend import store; store.update('${job.id}',status='error',error='Interrupted test')`],{cwd:root,env});
  await project.getByRole('button',{name:'Retry processing'}).click({timeout:10000});
  await project.getByText('Ready to share',{exact:true}).waitFor({timeout:45000});
  const recovered=await (await page.request.get(`/api/jobs/${job.id}`)).json();
  assert.equal(recovered.clips.length,1);
  assert.equal(recovered.clips[0].export_settings.caption_edits['0'],'Corrected');
  assert.deepEqual(errors,[]);
  console.log('Advanced editor passed: word corrections, trimming, invalid range, SRT, real export preview/download, persistence, quality change, retry, and responsive widths.');
} finally {
  await browser?.close();
  if(server&&server.exitCode===null){server.kill('SIGTERM');await new Promise(resolve=>server.once('exit',resolve));}
  rmSync(folder,{recursive:true,force:true});
}
