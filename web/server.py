from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, request, send_from_directory, Response
import queue
import sys
from flask_cors import CORS

from phone_agent.device_factory import DeviceType, get_device_factory, set_device_type
from phone_agent.model import ModelConfig
from phone_agent.agent import AgentConfig, PhoneAgent

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config.json"
DEFAULT_CONFIG = {
    "base_url": os.getenv("PHONE_AGENT_BASE_URL", "http://localhost:8000/v1"),
    "model": os.getenv("PHONE_AGENT_MODEL", "autoglm-phone-9b"),
    "api_key": os.getenv("PHONE_AGENT_API_KEY", "EMPTY"),
    "device_type": os.getenv("PHONE_AGENT_DEVICE_TYPE", "adb"),
    "device_id": os.getenv("PHONE_AGENT_DEVICE_ID", None),
    "max_steps": int(os.getenv("PHONE_AGENT_MAX_STEPS", "100")),
    "lang": os.getenv("PHONE_AGENT_LANG", "cn"),
}

app = Flask(__name__, static_folder=str(ROOT / "static"), static_url_path="")
CORS(app)

# Ensure config file exists
if not CONFIG_PATH.exists():
    CONFIG_PATH.write_text(json.dumps(DEFAULT_CONFIG, ensure_ascii=False, indent=2))


def load_config() -> dict[str, Any]:
    return json.loads(CONFIG_PATH.read_text())


def save_config(cfg: dict[str, Any]) -> None:
    CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2))


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/api/config", methods=["GET", "POST"])
def api_config():
    if request.method == "GET":
        return jsonify(load_config())

    data = request.json or {}
    cfg = load_config()
    cfg.update(data)
    save_config(cfg)
    return jsonify({"ok": True, "config": cfg})


@app.route("/api/devices", methods=["GET"])
def api_devices():
    cfg = load_config()
    device_type = DeviceType.ADB if cfg.get("device_type", "adb") == "adb" else DeviceType.HDC
    set_device_type(device_type)

    factory = get_device_factory()
    try:
        devices = factory.list_devices()
        out = []
        for d in devices:
            out.append({
                "device_id": getattr(d, "device_id", str(d)),
                "status": getattr(d, "status", ""),
                "connection_type": getattr(d, "connection_type", None).value if getattr(d, "connection_type", None) else None,
                "model": getattr(d, "model", None),
            })
        return jsonify({"devices": out})
    except Exception as e:
        return jsonify({"devices": [], "error": str(e)}), 500


@app.route("/api/connect", methods=["POST"])
def api_connect():
    data = request.json or {}
    address = data.get("address")
    cfg = load_config()
    device_type = DeviceType.ADB if cfg.get("device_type", "adb") == "adb" else DeviceType.HDC
    set_device_type(device_type)

    factory = get_device_factory()
    Connection = factory.get_connection_class()
    conn = Connection()

    if not address:
        return jsonify({"ok": False, "message": "address is required"}), 400

    success, message = conn.connect(address)
    if success:
        # update device_id in config
        cfg["device_id"] = address
        save_config(cfg)
    return jsonify({"ok": success, "message": message})


@app.route("/api/disconnect", methods=["POST"])
def api_disconnect():
    data = request.json or {}
    address = data.get("address")
    cfg = load_config()
    device_type = DeviceType.ADB if cfg.get("device_type", "adb") == "adb" else DeviceType.HDC
    set_device_type(device_type)

    factory = get_device_factory()
    Connection = factory.get_connection_class()
    conn = Connection()

    if address:
        success, message = conn.disconnect(address)
    else:
        success, message = conn.disconnect()
    return jsonify({"ok": success, "message": message})


@app.route("/api/run_stream", methods=["GET"])
def api_run_stream():
    """
    Run a task and stream stdout/stderr back to client using Server-Sent Events (SSE).
    Use: GET /api/run_stream?task=...
    """
    task = request.args.get("task")
    if not task:
        return jsonify({"ok": False, "message": "task is required"}), 400

    cfg = load_config()

    model_cfg = ModelConfig(
        base_url=cfg.get("base_url"),
        api_key=cfg.get("api_key", "EMPTY"),
        model_name=cfg.get("model"),
        lang=cfg.get("lang", "cn"),
    )

    agent_cfg = AgentConfig(
        max_steps=int(cfg.get("max_steps", 100)),
        device_id=cfg.get("device_id"),
        lang=cfg.get("lang", "cn"),
        verbose=True,
    )

    agent = PhoneAgent(model_config=model_cfg, agent_config=agent_cfg)

    q = queue.Queue()

    class QueueWriter:
        def __init__(self, orig, q):
            self.orig = orig
            self.q = q

        def write(self, s):
            if not s:
                return
            # Write to original stdout/stderr so console shows logs
            try:
                self.orig.write(s)
                try:
                    self.orig.flush()
                except Exception:
                    pass
            except Exception:
                pass
            # Put into queue for SSE streaming
            try:
                self.q.put(s)
            except Exception:
                pass

        def flush(self):
            try:
                self.orig.flush()
            except Exception:
                pass

    def run_agent():
        # Redirect stdout/stderr to the queue (but still mirror to original so console shows it)
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = QueueWriter(old_stdout, q)
        sys.stderr = QueueWriter(old_stderr, q)
        try:
            res = agent.run(task)
            q.put(f"__RESULT__:{res}")
        except Exception as e:
            q.put(f"__ERROR__:{e}")
        finally:
            # sentinel
            q.put(None)
            sys.stdout = old_stdout
            sys.stderr = old_stderr

    t = threading.Thread(target=run_agent, daemon=True)
    t.start()

    def event_stream():
        while True:
            item = q.get()
            if item is None:
                # send done event
                yield "event: done\ndata: done\n\n"
                break
            if isinstance(item, str) and item.startswith("__RESULT__:"):
                yield f"event: result\ndata: {item[len('__RESULT__:'):] }\n\n"
            elif isinstance(item, str) and item.startswith("__ERROR__:"):
                yield f"event: error\ndata: {item[len('__ERROR__:'):] }\n\n"
            else:
                for line in str(item).splitlines():
                    yield f"data: {line}\n\n"

    return Response(event_stream(), mimetype="text/event-stream")


@app.route("/api/screenshot", methods=["GET"])
def api_screenshot():
    """Return a screenshot from the current device.

    Response JSON:
      {
        "width": int,
        "height": int,
        "image": "data:image/png;base64,...",
        "is_sensitive": bool,
        "current_app": str
      }
    """
    cfg = load_config()
    device_id = cfg.get("device_id")
    try:
        factory = get_device_factory()
        screenshot = factory.get_screenshot(device_id)
        current_app = factory.get_current_app(device_id)
        return jsonify(
            {
                "width": screenshot.width,
                "height": screenshot.height,
                "image": f"data:image/png;base64,{screenshot.base64_data}",
                "is_sensitive": getattr(screenshot, "is_sensitive", False),
                "current_app": current_app,
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/run", methods=["POST"])
def api_run(): 
    data = request.json or {}
    task = data.get("task")
    if not task:
        return jsonify({"ok": False, "message": "task is required"}), 400

    cfg = load_config()

    model_cfg = ModelConfig(
        base_url=cfg.get("base_url"),
        api_key=cfg.get("api_key", "EMPTY"),
        model_name=cfg.get("model"),
        lang=cfg.get("lang", "cn"),
    )

    agent_cfg = AgentConfig(
        max_steps=int(cfg.get("max_steps", 100)),
        device_id=cfg.get("device_id"),
        lang=cfg.get("lang", "cn"),
        verbose=True,
    )

    agent = PhoneAgent(model_config=model_cfg, agent_config=agent_cfg)

    # Run synchronously — in real deployments consider background task or websockets
    try:
        result = agent.run(task)
        return jsonify({"ok": True, "result": result})
    except Exception as e:
        return jsonify({"ok": False, "message": str(e)}), 500


@app.route("/api/apps", methods=["GET"])
def api_apps():
    from phone_agent.config.apps import list_supported_apps

    apps = list_supported_apps()
    return jsonify({"apps": apps})


if __name__ == "__main__":
    cfg = load_config()
    host = os.getenv("WEB_HOST", "127.0.0.1")
    port = int(os.getenv("WEB_PORT", "5000"))
    print(f"Starting web server on http://{host}:{port}")
    app.run(host=host, port=port, debug=True)
