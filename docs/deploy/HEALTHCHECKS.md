# Health Check Endpoints

## Web Service

### GET /health

Returns service health status.

**Response (200):**
```json
{
  "status": "healthy",
  "service": "web",
  "timestamp": "2026-04-05T00:00:00Z"
}
```

**Response (503):**
```json
{
  "status": "unhealthy",
  "service": "web",
  "error": "description of issue"
}
```

### Semantics

- 200: Service is ready to accept requests
- 503: Service is running but not ready (dependency failure)
- No response: Service is down (container not running)

## Worker Service

The worker service does not expose HTTP endpoints. Health is determined by:

1. LiveKit Cloud dashboard shows agent connected
2. Worker process is running (`SERVICE_TYPE=worker` in container)
3. STT/TTS adapters respond to test requests

## Health Check Integration

### Railway
Railway monitors container health via the process exit code. The `railway.toml` restart policy handles failures:
```toml
[deploy]
restartPolicyType = "on_failure"
restartPolicyMaxRetries = 3
```

### Programmatic Check
Use `scripts/runtime_healthcheck.py` to check health from outside:
```bash
python scripts/runtime_healthcheck.py --url https://your-app.railway.app/health
```

### Deployment Verification
Use `scripts/deploy_verify.py` for comprehensive post-deploy checks:
```bash
python scripts/deploy_verify.py --web-url https://web.railway.app --fast-brain-url https://fast-brain.modal.run
```
