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
