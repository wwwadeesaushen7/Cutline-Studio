# Cloud demo with Railway Trial/Free credits

This option runs Cutline while your Windows computer is off. It uses a free resource allowance, so availability is limited by credits and usage. It is not unlimited always-on hosting.

Railway's current official documentation lists:

- A new-account trial with **$5 of one-time credit, expiring after up to 30 days**.
- A **$0/month Free plan with $1 of resource credit per month** after the trial. Monthly credit does not roll over.
- A Free service limit of **0.5 GB RAM**, **1 GB temporary disk**, and a **4 GB maximum image size**. The Trial allows more memory; this demo profile is tested within 512 MiB.
- A trial available without a payment card. GitHub verification determines Full versus Limited Trial access. Limited Trial has outbound-network restrictions and may prevent YouTube imports.

Sources checked on 17 October 2026: Railway's official [trial docs](https://github.com/railwayapp/docs/blob/166e6d1b1eb53fa7a2ca551e9b3c1e5097ab72ed/content/docs/pricing/free-trial.md), [plans and limits](https://github.com/railwayapp/docs/blob/166e6d1b1eb53fa7a2ca551e9b3c1e5097ab72ed/content/docs/pricing/plans.md), and [free-tier comparison](https://github.com/railwayapp/docs/blob/166e6d1b1eb53fa7a2ca551e9b3c1e5097ab72ed/content/docs/platform/compare-to-northflank.md). Check the allowance shown in your dashboard before deployment. Remain on **Trial/Free** for this route; **Hobby is paid**. If your account only offers paid plans, share that screen instead of upgrading.

The demo uses lighter **English-only** offline recognition, with lower accuracy than Whisper, and defaults to one clip. It downloads no speech model. Exact time-range clips still accept videos in any language with captions off. Start with short, low-resolution sources and one clip. Projects and videos are temporary and can disappear after a restart/rebuild.

## 1. Create the account and connect the repository

1. Open [Railway](https://railway.com/) and sign in using GitHub.
2. Check that your account shows **Trial credit** or the **Free** allowance described above. No paid subscription is needed for this guide.
3. Create a **New Project** and choose **Deploy from GitHub repo**, or add a GitHub Repository service to an empty project.
4. If GitHub asks, allow Railway to access **`wwwadeesaushen7/Cutline-Studio`**. Select **Cutline-Studio**; access to other repositories is unnecessary.
5. Select the repository, then open service **Settings → Source** and set its branch to **`main`**. If a branch selector appears during creation, choose it there.
6. Leave the root directory empty and use the root **Dockerfile**. Railway detects it automatically. The included `railway.json` configures Docker and `/api/health`; no custom build/start command is needed. Keep one service instance with no persistent volume for this temporary demo.

## 2. Add three service variables

Open the app service's **Variables** tab and add these entries. Enter the password only in Railway's settings, never in GitHub or chat:

| Name — copy exactly | Value |
| --- | --- |
| `CUTLINE_SITE_USERNAME` | A username you choose, for example `owner` (no colon) |
| `CUTLINE_SITE_PASSWORD` | A long, unique password you choose for Cutline |
| `CUTLINE_FREE_DEMO` | `1` |

The container requires both credentials. The free-demo flag selects English recognition, temporary-storage notices, and small native-library thread counts. Recognition runs in a child process so long native decoder calls cannot stall the web server. Missing credentials cause a clear startup error; add them and redeploy if an initial automatic deployment started too early.

The Docker command listens on Railway's provided `PORT`. If the domain dialog asks for a target port and no `PORT` has been assigned, use **8000**. These site credentials are separate from your Railway/GitHub login.

## 3. Deploy and get the website link

1. Save the branch/variable changes and choose **Deploy** or **Redeploy**. The first build installs the video tools and can take several minutes. Railway's docs say builds do not consume runtime compute credit.
2. When the app reports **Active/Running**, open service **Settings → Networking → Public Networking**.
3. Click **Generate Domain** to obtain a Railway-provided HTTPS website address. You do not need to buy a custom domain.
4. Open that HTTPS address and enter the Cutline username/password you created. Confirm the interface shows **Free demo · English recognition**. If absent, check `CUTLINE_FREE_DEMO=1` and redeploy before testing transcription.
5. Optionally enable **Serverless/App Sleeping** in service settings and redeploy to apply it. The provider sleeps an idle service and wakes it for a new request. The first request can be slow or show a temporary 502; retry after it wakes.

These are Railway service settings. No Windows installation, downloaded app files, or Codex **Edit environment** changes are needed. Changing files in this repository does not create a cloud account, service, domain, or subscription.

## 4. Test and keep within the allowance

First upload a small video, choose **Clip a time range**, switch **Auto captions** off, and export a few seconds. Then try an English source just over three minutes with **one** automatic clip and captions. Review recognized words before sharing. Speaker cuts, two-screen framing, text, music, and aspect-ratio controls remain available.

Keep the page open while processing. Progress polling keeps traffic flowing; a background job can be interrupted if the service sleeps or restarts after you close the page. After downloading clips and ending processing, close idle app tabs so polling stops and the service can sleep. Check remaining credit in Railway. Credits do not guarantee a whole month of availability for this workload. This guide does not subscribe you to a paid plan.

**Download finished clips immediately and delete completed test projects.** A recycle/rebuild can erase the library, sources, outputs, and caches. Free temporary disk is only 1 GB; use small files, preferably below 100 MB and 360p/480p for initial tests. The app's general 2 GB upload ceiling is not a promise that such a file fits this deployment. Provider disk, memory, upload-time, and credit limits apply first.

Railway's current networking docs require request bodies to finish uploading within five minutes. Test intended file sizes on the actual service. Large files can fail or exhaust the temporary disk. YouTube may reject hosting IP addresses or be blocked by Limited Trial networking, so file upload is the primary test path. Offline English recognition requires no external model service or paid AI API key.

Everyone with the site password shares one project library and can see, download, or delete its projects. This demo does not add public registration, private per-user libraries, quotas, permanent storage, or a durable job queue.

## Hosting eligibility

Render only offered paid plans for the user's account. Hugging Face's current [official Spaces docs](https://github.com/huggingface/hub-docs/blob/main/docs/hub/spaces-overview.md) require a paid plan to create Docker Spaces, despite CPU Basic having no hourly compute charge. Its free ZeroGPU exception is for eligible older accounts using the Gradio SDK. Neither is the selected zero-subscription route for this Docker app.

The source and container are tested here. Actual account eligibility, remaining allowance, dashboard labels, the generated website address, and a first hosted upload/export still need checking in your Railway account. No live deployment was created from this environment.

## Updating and reproducing the resource test

Wait for processing to finish, then manually deploy the latest `main` branch. Disable automatic GitHub deployments if available to avoid interrupting active jobs on each code push. Temporary projects can be lost on an update. Leave `CUTLINE_FREE_DEMO=1` enabled.

Developers can build `docker build -t cutline-studio:free-test .` and run `.venv/bin/python scripts/check_free_demo.py` on Linux with Docker/cgroup v2 and FFmpeg's flite filter. The manual check creates and removes only synthetic data and its own container. It tests English recognition, captions, clipping, editing, and protected downloads under 512 MiB/no-swap/0.1-CPU limits, records memory and response times, and is separate from the fast unit suite. The [paid-hosting guide](PUBLISHING.md) remains available for larger servers with durable storage.
