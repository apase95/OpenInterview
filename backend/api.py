from fastapi import FastAPI
from fastapi.responses import JSONResponse

from backend.database import ping

app = FastAPI()


@app.get('/health')
def health():
    """Liveness only; does not check DB or providers."""
    return {'status': 'ok', 'service': 'api'}


@app.get('/ready')
def ready():
    try:
        ping()
    except Exception:
        return JSONResponse({'status': 'unavailable'}, status_code=503)
    return {'status': 'ready', 'service': 'api'}
