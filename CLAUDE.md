# Environment

## Execution Context
This project runs inside a Docker container on a **remote machine**, not locally.
Local files are mounted via Samba, but commands must NOT be run locally.

## How to run commands
Always SSH into the remote machine before running any script or docker command:

sudo /usr/sbin/sshd -d
**Remote host:** `blas@blas.local:8532`
**Container name:** Get if from docker-compose.yml

To run a command inside the container:
```bash
ssh -p 8532 blas@blas.local "/usr/local/bin/docker exec ..."
```

To check if the container is running:
```bash
ssh blas@blas.local "/usr/local/bin/docker ps --filter name=my_app_container"
```

To run a Python script:
```bash
ssh blas@blas.local "/usr/local/bin/docker exec my_app_container python /home/app/..."
```

## Rules
- Never run `python`, `pip`, `pytest`, or app commands locally.
- Never commit or push any change.
- Always verify the container is running before executing commands.
- File paths inside the container start at `/home/app/` (Check docker-compose.yml).
- Never restart any docker compose service or call django manage runserver or vite dev server mode. Always ask to restart the services if needed.

# Coding

## Standards
Please always use the `STANDARDS.md` content as the rules for coding.

You can validate the `backend` code using the `shell/do.sh file_path_inside_container` to black and get the pylint report of a file.

For `frontend` you can use `yarn lint` and `yarn lint --fix`.

## Rules
- Remeber to run any command using the proper ssh and docker wrapper.

# Testing
Only call tests for the resources being changed.
Never run the whole test suit.

# chrome-devtools MCP

The `chrome-devtools` MCP server (`.mcp.json`) runs `chrome-mcp:latest` — a locally-built image (amd64-only, runs under emulation on Apple Silicon), not the stock `nullrunner/chrome-mcp-docker`. It speaks CDP to a separate headless Chrome container and does not launch Chrome itself.

**Why a custom image:** the stock image only exposes `navigate`/`screenshot`/`click`/`type`/`scroll`/`wait_for_selector`/`get_computed_styles`/`get_network_errors`/`get_console_logs`/`mobile_mode` — no way to read page content as text, only as a screenshot (which then has to be read via vision, one viewport at a time — painfully slow for anything document-like, e.g. reading SAP's help pages). `docker/chrome-mcp/` in this repo adds three tools on top: `get_html`, `get_text` (prefer this one — clean rendered text, no markup noise), and `evaluate` (arbitrary JS, JSON-serialized result). See `docker/chrome-mcp/index.js` for the diff and `docker/chrome-mcp/Dockerfile` for the build (`FROM nullrunner/chrome-mcp-docker:latest`, just overlays the patched `index.js` — reproducible on any machine that can pull the base image, unlike a hand-committed image).

Rebuild after editing `docker/chrome-mcp/index.js`:

```bash
docker build --platform linux/amd64 -t chrome-mcp:latest docker/chrome-mcp/
```

Then restart the `chrome-devtools` MCP server (Restart action or `/mcp reconnect all`) to pick up the new image — a running container keeps using whatever image it started with.

Setup is two containers, connected via `--network container:chrome-persistent` (network-namespace sharing), not by IP or hostname:

- `chrome-persistent` (`zenika/alpine-chrome`, arm64-native) — the actual browser, publishes `9222` to the host for our own debugging.
- `chrome-devtools` (from `.mcp.json`) — the MCP proxy, launched with `--network container:chrome-persistent` so it shares that container's network namespace, then talks to `CHROME_HOST=localhost`.

**Why network-namespace sharing instead of an IP or a container-name/alias:** Chrome's DevTools HTTP endpoint (`/json/version` etc.) rejects any request whose `Host` header isn't literally `localhost` or an IP address — DNS-rebinding protection with no override flag. A container hostname/alias (`chrome`, `host.docker.internal`) fails this check with `500: Host header is specified and is not an IP address or localhost.`. A hardcoded IP works but is fragile (ties `.mcp.json` to one machine's Docker network state) — ruled out. `--network container:<name>` sidesteps both problems: the proxy container shares `chrome-persistent`'s network stack directly, so `localhost` is literally true localhost, and the only thing referenced is the container's **name**, which is portable across machines.

Before using any `mcp__chrome-devtools__*` tool, verify the chain is up:

```bash
docker ps --filter "name=chrome-persistent" --format "table {{.Names}}\t{{.Status}}"
curl -s http://localhost:9222/json/version   # should return JSON with "Browser": "HeadlessChrome/..."
```

If `chrome-persistent` isn't running, recreate it:

```bash
docker run -d --name chrome-persistent --restart unless-stopped \
  -p 9222:9222 --shm-size=2g \
  zenika/alpine-chrome \
  --no-sandbox --remote-debugging-address=0.0.0.0 \
  --remote-debugging-port=9222 --disable-gpu --headless
```

Note: use the bare `zenika/alpine-chrome` tag, not `:with-puppeteer` — the puppeteer variant overrides `ENTRYPOINT` to `tini --` with no default `CMD`, so passing Chrome CLI flags directly fails with `exec --no-sandbox failed: No such file or directory`. The base tag's entrypoint is `chromium-browser --headless`, which correctly appends the flags.

The container must be named exactly `chrome-persistent` — `.mcp.json`'s `--network container:chrome-persistent` references it by that name.

After starting/recreating `chrome-persistent`, restart the `chrome-devtools` MCP server (via the editor's Restart action or `/mcp reconnect all`) so it picks up a live connection — it won't retry on its own if it started while Chrome was down.
