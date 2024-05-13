### Reference:
https://github.com/nektos/act
https://nektosact.com/usage/index.html

### Setup docker context:
If you use podman or rancher-desktop, your Docker Daemon might be located somewhere else.
If you get this error:

```bash
Error: Cannot connect to the Docker daemon at unix:///var/run/docker.sock. Is the docker daemon running?
```

Run this to set up your docker location for act properly:
```bash
export DOCKER_HOST=$(docker context inspect --format '{{.Endpoints.docker.Host}}')
```

Then run your act commands

```bash
act pull_request_review_comment --eventpath ./tests/payload.json -s GITHUB_TOKEN="$(gh auth token)" --env-file ./app/.env
```