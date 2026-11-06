# Cutline Studio

[Download the complete Windows package](https://github.com/wwwadeesaushen7/Cutline-Studio/raw/refs/heads/main/downloads/Cutline-Studio-Windows.zip)

This ZIP includes the whole website, the latest improvements, the built interface, **1 - Setup.bat**, **2 - Open Cutline.bat**, and a Windows guide. No earlier download is needed. Extract All, open the **Cutline Studio** folder, run **1 - Setup**, wait for **SETUP COMPLETE**, then run **2 - Open Cutline**. Setup needs internet to install missing tools and packages. See [START-HERE.txt](START-HERE.txt).

If you already have projects, close Cutline and copy the extracted contents into your existing folder, replacing matching files. Keep your `.data`, `.tools`, and `.venv` folders. Run setup again, then open the website.

A complete React + FastAPI video-clipping workspace. Upload a long video or import a public YouTube link, turn spoken passages into clips, then add captions, text, and your own music.

The saved [editing preferences](docs/EDITING-PREFERENCES.md) specify direct cuts between speakers and top/bottom output for two source screens.

## Run

Requirements: Python 3.12+, Node 22+, FFmpeg/FFprobe with libx264 and libass. On Debian/Ubuntu: `apt-get install ffmpeg`.

```sh
./scripts/setup.sh
./scripts/dev.sh
```

The Vite development server uses port 5173 and proxies `/api` and `/media` to the Python server on port 8000. Use the existing checkout; cloud tasks already run in an isolated workspace and do not need a Git worktree.

For a single production-style process, build first with `cd frontend && npm run build`, then run from the repository root:

```sh
.venv/bin/python -m uvicorn backend.app:app --host 0.0.0.0 --port 8000
```

For automated checks: `./scripts/check.sh`. After building, `cd frontend && npm run test:editor` runs the new editor workflow in Chromium against an isolated temporary server and deterministic media fixture. Runtime/development Python packages are pinned in `requirements.lock.txt`; the frontend uses `npm ci` with `package-lock.json`.

## Publish online

For the credit-limited cloud demo selected for this project, follow the [Railway Trial/Free browser guide](docs/FREE-CLOUD-DEMO.md). Railway's official documentation currently lists a one-time $5 trial grant for up to 30 days, followed by a $0 Free plan with $1 of resource credit each month. Availability is limited by credits and resources; this is not an unlimited hosting allowance. Set the site username/password and `CUTLINE_FREE_DEMO=1`, and deploy from `main`. No files need uploading manually. `railway.json` selects the Dockerfile and health check.

This profile uses lighter English-only speech recognition and defaults to one clip. Native English recognition runs in a child process so it cannot hold the web server's Python interpreter during a long utterance. Your computer can be off; projects and videos use temporary storage and can disappear after a restart/rebuild. The interface explains these limits. This is an experimental demo for small videos, with no processing-time guarantee.

The [paid-hosting guide](docs/PUBLISHING.md) covers the root Dockerfile with a persistent disk instead. Both deployments require `CUTLINE_SITE_USERNAME` and `CUTLINE_SITE_PASSWORD`, protecting one shared workspace without separate user accounts. Publishing a Codex environment does not publish the website.

Hugging Face's current documentation requires a paid plan to create Docker Spaces, even though CPU Basic has no hourly compute charge. It is not the zero-cost deployment path for this app.

## What works

- Upload MP4, MOV, WebM, MKV, M4V, or AVI, up to 2 GB and two hours. **Automatic highlights** require video and audio and a source strictly longer than 180 seconds. **Clip a time range** also accepts short or silent videos. Both the browser (where it can read metadata) and server validate the selected times.
- Import public YouTube watch, shortened, shorts, or live-recording links. Downloads use yt-dlp, FFmpeg, and the installed Node runtime. Live streams, playlists, private/sign-in videos, and restricted downloads are not supported. YouTube can reject downloads even when a video is publicly viewable; file upload is the alternative.
- Transcribe timestamped words; group complete detected sentences or spoken passages ending at pauses; select non-overlapping passages. Clip length is a target, **not a hard timer**. A long uninterrupted passage may produce a longer clip or fewer clips than requested. Ranking uses transcript structure and simple keyword signals; there is no fabricated virality score.
- Choose **Clip a time range** in the main interface or sidebar, upload a file or paste a YouTube link, and enter start/end times (for example `00:30` → `01:15`). Uploaded files have a source player, playhead shortcuts, and selected-range preview. This creates one clip using the requested boundaries, without automatic passage selection. Frame-based video cuts are accurate to the source frame grid. Turn captions off to skip speech recognition; when enabled, only the selected range is transcribed. Silent/no-speech ranges still export, with a caption notice when applicable. A selected range must be at least 0.25 seconds and within the source duration. YouTube times are validated after download.
- **Auto** is the default framing. It looks for a persistent side-by-side divider and stacks detected screens; shared wide-camera conversations with multiple detected faces use speaker cuts; other scenes keep the complete picture. Detection is conservative and can be wrong. Select **Two screens** explicitly to control the source orientation and divider position, or **Full scene** to retain all people, demonstrations, and objects over a soft background.
- **Speaker cuts** switches directly between detected speakers, without a slide, pan, zoom, dissolve, or added transition delay. A bundled YuNet detector locates faces and landmarks; aligned lip movement is compared separately from head/lighting changes, and face identities survive brief detection gaps. Face size does not count as speech activity. Face/mouth motion is sampled at 4 Hz; recognized word timestamps gate silent intervals when available. Two consecutive observations confirm a change retrospectively at its first observed sample. Detected source-camera cuts reset tracking, are refined to the source frame grid, and never inherit the old shot's crop. Median filtering, a hold area, and bounded camera movement operate only within a shot. Neither smoothing nor interpolation crosses a speaker or source-camera cut. The timing and speaker identity remain approximate visual estimates, not audio diarization. Existing clips receive the new analysis when re-exported with Speaker cuts.
- **Two screens** puts the complete left panel on top and the right panel below, preserving the original combined audio. Manual controls also support sources already arranged top/bottom and unequal panel sizes. Panels are fitted without stretching or cropping away their content. Choose portrait, square, or landscape; the default 720p sizes are 720×1280, 720×720, and 1280×720.
- Optional burned-in word-timed captions in Spotlight, Studio, Pop, and Minimal templates. Spotlight highlights the active word.
- **Fine-tune existing clips:** open Make it yours → Trim, set start/end in seconds or use the playhead. Edits are non-destructive and must retain at least 0.25 seconds within the generated clip. Re-exporting at another quality keeps your trim.
- **Correct captions:** Captions → Edit caption words lets you search, correct, or hide recognized words without losing their timing. Export saves corrections and provides an optional UTF-8 `.srt` subtitle download. Restore recognized words reverses corrections; clips without recognized speech can still use custom text.
- **Review the result:** switch between Edit preview and Exported video to watch the actual saved framing, captions, and mixed audio. Controls lock during export; closing with unexported changes asks before discarding them.
- **Recover interrupted work:** failed projects with a saved source (or YouTube link) offer Retry processing. Completed clips stay intact and an already downloaded source is reused. Missing uploads must be uploaded again; retries cannot bypass unavailable source sites or fix unclear speech.
- Clip editor with video preview, seeking, captions, a custom text overlay (top/center/bottom), music upload, original/music volume sliders, framing, and tracking controls. Export renders an actual H.264/AAC MP4. Audio loops to match the clip, while speech audio is preserved at the selected volume.
- **Download quality** offers 480p (smaller file), 720p HD (balanced, default), and 1080p Full HD (higher quality). Click a clip's download icon to choose quality, prepare the MP4, and download it; the same selector is available above Export clip in the editor. Each new export uses the original source, keeps saved edits/music, scales captions and text, and saves the selected quality for next time. Portrait sizes are 480×854, 720×1280, and 1080×1920; landscape reverses these dimensions and square uses 480, 720, or 1080 on both sides. Higher quality also uses gentler video compression and a higher AAC audio bitrate. Higher resolution cannot recover detail absent from the source, and larger exports take more CPU, memory, time, and disk.
- Persistent projects, progress polling, searchable library, downloads, and deletion. Files and SQLite metadata stay in `.data/` until project deletion. Server restart marks interrupted processing/exports as failed rather than pretending they finished.

## Speech engines and network access

The default `CUTLINE_SPEECH_ENGINE=auto` tries local CPU Whisper (`WHISPER_MODEL=tiny`) and falls back to PocketSphinx's bundled **English-only** model if the Whisper model cannot load. The offline engine requires no keys or external model download, but has lower recognition accuracy and infers boundaries from pauses rather than linguistic punctuation. Review captions before publishing. Use `CUTLINE_SPEECH_ENGINE=offline` to skip the download attempt, or `CUTLINE_SPEECH_ENGINE=whisper` to require Whisper rather than falling back.

Whisper receives mono 16 kHz float32 audio decoded by FFmpeg. This uses faster-whisper's supported NumPy input API, avoiding the `metadata_errors` incompatibility between faster-whisper 1.2.1 and PyAV 19. YouTube metadata, transcript caches, and export metadata are read and written explicitly as UTF-8 on every platform.

Set `WHISPER_MODEL` to a pre-downloaded faster-whisper model directory for fully offline Whisper, or allow the following model-download domains: `huggingface.co`, `*.huggingface.co`, `*.hf.co`, and `*.xethub.hf.co`. Multilingual recognition requires Whisper. Models are cached under `.data/models`.

YouTube imports need outbound HTTPS to `youtube.com`, `www.youtube.com`, `m.youtube.com`, `youtu.be`, `youtubei.googleapis.com`, `*.googlevideo.com`, and `*.ytimg.com`. The onboarding environment currently blocks these and external model downloads. Network additions are saved in the environment draft; review and save them in environment settings to apply the policy, then publish the environment when satisfied. Saving a draft does not itself change the running network policy.

## Practical limits

Processing is local and CPU-based, with one worker to keep memory use bounded. Runtime depends on source length, resolution, and number of clips; a few minutes cannot be guaranteed. Speech recognition and sentence detection can be wrong. Visual active-speaker selection is a heuristic, not a speaker-diarization or lip-sync model: occlusions, camera motion, multiple moving mouths, and profile faces can confuse it. Full-scene framing keeps all source content visible; it does not infer which object is being discussed or generate editorial cutaways. New framing and tracking are applied during export; the editor previews the clean generated clip with live style overlays.

This is a **single shared workspace**, without accounts, tenant isolation, quotas, billing, or a durable distributed job queue. Do not expose it as a public multiuser service without those additions. There is no automatic posting to social networks.

## Layout

- `backend/app.py`: upload/import/export API and background processing
- `backend/speech.py`: Whisper/offline transcription, boundaries, and passage selection
- `backend/media.py`: probing, face tracking, ASS captions, audio mix, MP4 rendering
- `backend/faces.py`, `backend/models`: local face/landmark detection, stable identities, aligned mouth activity, and the small bundled detector with its licenses
- `backend/store.py`: SQLite-backed project persistence
- `docs/EDITING-PREFERENCES.md`: saved owner requirements for speaker cuts, stacked screens, and context
- `frontend/src`: responsive workspace and editor
- `tests/test_pipeline.py`: duration rules, URL validation, sentence boundaries, tracking rendering, safe captions, and API behavior

Sample portraits are **style illustrations**, never generated projects. The Lin-Manuel Miranda reference is sourced from [face_recognition's example image](https://github.com/ageitgey/face_recognition/blob/master/examples/lin-manuel-miranda.png). The Grace Hopper portrait is the US Navy public-domain image distributed in [Matplotlib's sample data](https://github.com/matplotlib/matplotlib/blob/main/lib/matplotlib/mpl-data/sample_data/grace_hopper.jpg). Replace these samples with your own brand imagery as needed.

With the development servers running, run `cd frontend && npm run test:ui` for browser smoke tests. They use `/usr/bin/chromium` by default; set `CHROMIUM_PATH` for another installed Chromium browser. The tests validate duration metadata, responsive layouts, framing choices, range validation/preview, and a real range upload/export. They create a synthetic test project and delete that project afterward; existing projects are left alone.

## Windows download

Download the `main` branch with GitHub's **Code → Download ZIP**, extract into a new folder, run `1 - Setup.bat` once, then use `2 - Open Cutline.bat` to open the app. Setup version 2 works without WinGet, Microsoft Store, or App Installer. It reuses supported Python 3.12/3.13, or installs a signed 64-bit Python 3.13 installer from python.org after verifying its pinned SHA-256 hash and publisher signature.

Missing Node.js and FFmpeg are downloaded as portable ZIPs into the local `.tools` directory. Their SHA-256 hashes are pinned from Node.js's release checksums and Microsoft's official WinGet package manifests. The Microsoft C++ runtime is installed when missing, with its Authenticode signature and Microsoft publisher verified. TLS, signatures, and checksums remain enabled. Portable binaries are added to the app process's PATH; no permanent PATH changes are required. The app environment and built website are then prepared automatically.

`WINDOWS-GUIDE.txt` contains the beginner walkthrough. Sources and checksum pins are recorded in `scripts/windows-downloads.json`. `.tools`, cached installers, `.venv`, and projects remain local and are excluded from Git and source downloads. The local launcher binds to loopback, opens the browser after a health check, and discovers the saved portable tools.

To update an existing Windows installation, first stop Cutline by closing its running terminal. Download and extract the updated ZIP, then copy the **contents** of the extracted app folder into your existing app folder and choose **Replace the files in the destination**. Copying the source files keeps your existing `.data`, `.tools`, and `.venv` folders. Run `1 - Setup.bat` again to build the updated interface; existing tools are reused. Wait for `SETUP COMPLETE`, then open `2 - Open Cutline.bat`. Existing clips can use the new framing by opening **Make it yours → Frame**, choosing a framing mode, and exporting again.

Windows setup is for 64-bit Windows 10/11. Download integrity, archive extraction, tool paths, media rendering under Windows-style folder names, and launcher logic have been checked here, but the native Windows installers cannot be executed on this Linux host. To refresh the packaged ZIP, build the frontend and run `python3 scripts/package_windows.py`.
