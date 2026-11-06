import React, { useState } from 'react';
import { RotateCcw, Scissors, Search } from 'lucide-react';
import './editing.css';

export function captionWords(clip, settings) {
  return (clip.words || []).map((word, index) => ({...word,
    text: (settings.caption_edits?.[index] ?? word.text).trim()
  })).filter(word => word.text && word.end > (settings.trim_start || 0)
    && word.start < (settings.trim_end ?? clip.duration));
}

export function TrimControls({clip, settings, patch, current, seek}) {
  const start = settings.trim_start || 0, end = settings.trim_end ?? clip.duration;
  function change(key, value) {
    patch(key, Math.round(Math.max(0, Math.min(clip.duration, Number(value))) * 1000) / 1000);
  }
  return <div className="trim-controls">
    <h3><Scissors size={18}/> Fine-tune this clip</h3>
    <p>Times below are seconds from the start of this clip. Keep at least 0.25 seconds. Your original clip stays available.</p>
    <label>Start at (seconds)<input aria-label="Trim start" type="number" min="0" max={clip.duration} step="0.01" value={start} onChange={e=>change('trim_start', e.target.value)}/></label>
    <input aria-label="Trim start slider" type="range" min="0" max={clip.duration} step="0.01" value={start} onChange={e=>change('trim_start', e.target.value)}/>
    <button className="text-button" onClick={()=>change('trim_start', current)}>Set start here</button>
    <label>End at (seconds)<input aria-label="Trim end" type="number" min="0" max={clip.duration} step="0.01" value={end} onChange={e=>change('trim_end', e.target.value)}/></label>
    <input aria-label="Trim end slider" type="range" min="0" max={clip.duration} step="0.01" value={end} onChange={e=>change('trim_end', e.target.value)}/>
    <button className="text-button" onClick={()=>change('trim_end', current)}>Set end here</button>
    {end-start < .25 ? <p className="trim-error" role="alert">Keep at least 0.25 seconds. Move the start before the end.</p> : <p><strong>{(end-start).toFixed(2)} seconds</strong> selected · source {(clip.start+start).toFixed(2)}–{(clip.start+end).toFixed(2)}s</p>}
    <div className="trim-actions"><button className="browse-button" disabled={end-start<.25} onClick={()=>seek(start)}>Go to start</button><button className="text-button" onClick={()=>{patch('trim_start',0);patch('trim_end',null);}}><RotateCcw size={14}/>Restore full clip</button></div>
  </div>;
}

export function CaptionEditor({clip, settings, patch, seek}) {
  const [query, setQuery] = useState(''), [limit, setLimit] = useState(40);
  const edits = settings.caption_edits || {};
  const words = (clip.words || []).map((word,index)=>({...word,index})).filter(word=>
    `${word.text} ${edits[word.index] || ''}`.toLowerCase().includes(query.toLowerCase()));
  function correct(index, text) {
    const next = {...edits};
    if (text === clip.words[index].text) delete next[index]; else next[index] = text;
    patch('caption_edits', next);
  }
  return <details className="caption-editor"><summary>Edit caption words <span>{Object.keys(edits).length ? `${Object.keys(edits).length} edited` : ''}</span></summary>
    <p>Correct a word or clear it to hide it. Timing stays matched to the speech. Export to save your changes.</p>
    {!clip.words?.length ? <p>No speech was recognized in this clip. Create it with captions enabled to recognize speech, or use the Text tab.</p> : <>
      <label className="caption-search"><Search size={14}/><input aria-label="Find caption words" placeholder="Find a word…" value={query} onChange={e=>{setQuery(e.target.value);setLimit(40);}}/></label>
      <div className="caption-word-list">{words.slice(0,limit).map(word=><div key={word.index} className="caption-word-row">
        <button title="Seek to word" aria-label={`Seek to word ${word.index+1}`} onClick={()=>seek(word.start)}>{word.start.toFixed(2)}s</button>
        <input aria-label={`Caption word ${word.index+1}`} maxLength={120} value={edits[word.index] ?? word.text} onChange={e=>correct(word.index,e.target.value)}/>
      </div>)}</div>
      {!words.length&&<p>No matching words.</p>}
      {words.length>limit&&<button className="text-button" onClick={()=>setLimit(n=>n+40)}>Show more words</button>}
      {!!Object.keys(edits).length&&<button className="text-button" onClick={()=>patch('caption_edits',{})}><RotateCcw size={14}/>Restore recognized words</button>}
    </>}
  </details>;
}
