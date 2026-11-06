# Put Cutline online: private test site

Publishing the **Codex environment** saves the development setup. It does not put the website online. The Windows launcher also runs only on your computer.

This guide covers a paid Render service with a persistent disk for videos and projects. For an experimental credit-limited cloud demo with English-only recognition and temporary files, use the [Railway Trial/Free guide](FREE-CLOUD-DEMO.md). Static website hosting alone cannot run the Python/FFmpeg processing. Check the host's current [pricing](https://render.com/pricing) before creating a paid service. Provider pricing, screens, and upload limits could not be verified from this development environment.

## What this deployment provides

The Dockerfile builds the website and installs Python, FFmpeg, Node, fonts, and the pinned Python packages. One server runs the website, API, and processing queue together. The browser asks for a username and password before opening the hosted site. Your Windows installation continues to work without a password unless you configure one.

**This is one private, shared workspace.** Everyone you give the password to can see, download, and delete the same projects. It does not provide public registration or separate private libraries for different users. A public service needs user accounts, project ownership checks, per-user storage/processing limits, and a durable queue before accepting general signups.

## Steps in your Windows browser

These are hosting settings in Render. You do not need to download the project again, rerun Windows setup, or change Codex's **Edit environment** screen for these steps.

1. Open [Render](https://render.com/) and create an account. Connect your GitHub account when asked.
2. Create a **Web Service** from the GitHub repository `wwwadeesaushen7/Cutline-Studio`. Choose the branch **`main`**. If the repository is missing, allow Render access to this repository in its GitHub connection settings.
3. Choose **Docker** as the runtime and leave the root directory empty. The Dockerfile is at the repository root. Choose a service name and a region near you. The built-in service address is enough for testing; you do not need to buy a domain yet.
4. Choose a **paid** instance. For longer videos, start with at least **4 GB RAM**; two CPU cores are preferable. This is a starting capacity recommendation, not a processing-time guarantee. Review the monthly estimate shown by the host before creating the service. Free services are unsuitable for this workload and persistent disk setup.
5. Add a **persistent disk**, initially around **20 GB** for a small trial. Set its mount path to **`/var/data`**. All uploads, clips, the database, and speech-model caches will be inside `/var/data/cutline`. Delete finished projects to free space. Do not rely on the container's temporary filesystem for videos.
6. In the service's environment variables, add the values below. Enter the password in the host's secret/environment settings, never in a GitHub file or chat.

   | Name | Value |
   | --- | --- |
   | `CUTLINE_SITE_USERNAME` | Your chosen username, for example `owner` (no colon) |
   | `CUTLINE_SITE_PASSWORD` | A long, unique password you choose |
   | `CUTLINE_REQUIRE_AUTH` | `1` |
   | `CUTLINE_DATA_DIR` | `/var/data/cutline` |

   The container deliberately refuses to start without both credentials. Keep password protection enabled on a hosted private site.

7. Set the health-check path to **`/api/health`**, keep **one instance**, and turn off automatic deployments if available. A deployment or restart interrupts any video currently processing, so update the site when the queue is idle. Do not add multiple server workers.
8. Create/deploy the service. The first build installs the processing tools and can take several minutes. When the host reports the service is running, open its **HTTPS** website address and enter your username and password in the browser prompt. Keep HTTPS enabled; the private-site password gate depends on it.

If the host asks for a port, use **8000**. When it provides `PORT` automatically, the Docker command uses that value. Leave any Docker command override empty.

## First test before sharing the link

Upload a small video, select **Clip a time range**, turn captions off, and export a short selection. Next, try a video longer than three minutes with automatic clips and captions. Verify a finished project remains after restarting the service while no work is running. This checks the persistent disk.

The app accepts uploads up to 2 GB, but the hosting provider or any proxy in front of it may enforce a smaller upload limit or timeout. Test your intended file size before choosing the service for production. If it cannot accept your uploads, use a host that supports them, or add direct uploads to object storage; the Dockerfile cannot change a provider's network limit.

YouTube may reject downloads from hosting providers' IP addresses even when the same video works on your computer. Keep file upload available. The first Whisper transcription downloads a model and can take longer; the downloaded model is cached on the disk. The English offline fallback remains available if model downloads fail.

## Later changes

- Once testing succeeds, optionally add your own domain using the host's custom-domain settings and the DNS records it gives you. Wait for HTTPS to become active before using the new address.
- Changing the site password revokes the old password. A browser may retain Basic-auth credentials; use a private browser window when testing a different login.
- Take backups of the persistent data while processing is idle. This deployment does not add automatic backups or automatic file retention. Deleting the persistent disk loses the stored projects.
- Keep the server to one instance while it uses SQLite and an in-process queue. Multiple independent users and higher capacity require changes to the application, not only a bigger hosting plan.
- For a private site, deploy manually from `main` after updates have been pushed, waiting for current processing to finish first.

## Running the same image on another host

Any Docker host with HTTPS, a persistent volume, suitable memory/CPU, and sufficient request-size/time limits can run this image. Build from the repository root with `docker build -t cutline-studio .`. Supply the four environment variables above and mount persistent storage at `/var/data`. Publish the container's port 8000 through the host's HTTPS proxy. Never expose the Docker engine or put passwords directly into a shared command history.

`/api/health` is intentionally available without credentials for host probes; pages, APIs, docs, and media require the private-site login. Health reports server/tool availability, not the completion of queued processing or the reachability of YouTube/model services.
