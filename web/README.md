Web UI for Open-AutoGLM

Run:

```bash
pip install -r requirements.txt
python web/server.py
```

Open http://localhost:5000

Notes:
- Config is stored in `web/config.json`.
- The `/api/run` endpoint runs `PhoneAgent.run` synchronously — consider adapting to background workers for production.
