# PR-Agent Kubernetes Deployment

This directory contains a minimal Kubernetes deployment for running PR-Agent as a GitHub App with the Codex CLI backend.

## Prerequisites

- A container image that includes this repository plus the `codex` CLI.
- A public HTTPS Ingress endpoint reachable by GitHub.
- A GitHub App installed on the target repositories.
- A Codex CLI auth file from a seat that can run `codex exec`.

## Build Image

Build and push an image that uses the GitHub App runtime and includes the Codex CLI. Replace the image in `deployment.yaml` before applying.

```bash
docker build -f docker/Dockerfile.github_app_codex -t your-registry/pr-agent-codex:latest .
docker push your-registry/pr-agent-codex:latest
```

## Create Secrets

Create the namespace first:

```bash
kubectl create namespace pr-agent
```

Create the GitHub App secret:

```bash
kubectl -n pr-agent create secret generic pr-agent-secret \
  --from-literal=GITHUB__APP_ID="123456" \
  --from-file=GITHUB__PRIVATE_KEY=./github-app-private-key.pem \
  --from-literal=GITHUB__WEBHOOK_SECRET="replace-me"
```

Create the Codex CLI auth secret:

```bash
kubectl -n pr-agent create secret generic codex-auth \
  --from-file=auth.json="$HOME/.codex/auth.json"
```

Do not commit real Secret manifests to git. `secret.template.yaml` is only a shape reference.

## Configure

Edit `configmap.yaml` for non-secret runtime settings:

- `CODEX__CLI_MODEL`
- `CODEX__CLI_REASONING_EFFORT`
- `CODEX__CLI_TIMEOUT`
- `GITHUB_APP__PR_COMMANDS`
- `PR_DESCRIPTION__OUTPUT_FORMAT`

Edit `deployment.yaml`:

- Replace `your-registry/pr-agent-codex:latest`.
- Adjust CPU and memory requests if needed.

Edit `ingress.yaml`:

- Replace `pr-agent.example.com`.
- Replace the TLS secret and ingress class values for your cluster.

## Deploy

```bash
kubectl apply -k k8s/pr-agent
kubectl -n pr-agent rollout status deployment/pr-agent
```

Verify the service:

```bash
kubectl -n pr-agent port-forward svc/pr-agent 3000:3000
curl http://127.0.0.1:3000/
```

Expected response:

```json
{"status":"ok"}
```

## GitHub App Webhook

Set the GitHub App webhook URL to:

```text
https://pr-agent.example.com/api/v1/github_webhooks
```

Then redeliver a recent pull request webhook from the GitHub App settings page and check the pod logs:

```bash
kubectl -n pr-agent logs deployment/pr-agent -f
```

## Scaling

Keep `replicas: 1` until webhook handling is moved to a durable queue. The current service accepts the webhook and runs the PR task as an in-process background job, so a pod restart can interrupt an active model run.
