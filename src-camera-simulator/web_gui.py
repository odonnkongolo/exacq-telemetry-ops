#!/usr/bin/env python3
"""
web_gui.py — Flask dashboard for the CCTV IP Camera Simulator.

Provides a browser UI to:
  • Authenticate via a custom dark-themed login page (session-based)
  • Check if the RTSP server (port 8554) is listening
  • Count active FFmpeg stream processes  (pgrep -c ffmpeg)
  • Configure camera count & video path, then generate the config
  • Start / stop the simulator with one click
"""

import functools
import json
import os
import secrets
import socket
import subprocess
import urllib.request
from datetime import datetime

from flask import (
    Flask,
    jsonify,
    redirect,
    render_template_string,
    request,
    session,
    url_for,
)

app = Flask(__name__)
# A secure random key is generated at startup; sessions are invalidated on container restart.
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

INSTALL_DIR = "/opt/cctv-simulator"
RTSP_PORT   = 8554
API_PORT    = 9997

# Hardcoded credentials — change here or inject via environment variables
AUTH_USERNAME = os.environ.get("DASHBOARD_USER", "admin")
AUTH_PASSWORD = os.environ.get("DASHBOARD_PASS", "Exacq11955!")


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def login_required(f):
    """Decorator that redirects unauthenticated users to /login."""
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("authenticated"):
            return redirect(url_for("login", next=request.path))
        return f(*args, **kwargs)
    return decorated


# ---------------------------------------------------------------------------
# System helpers
# ---------------------------------------------------------------------------

def is_port_listening(port: int) -> bool:
    """Return True if *something* is listening on localhost:<port>."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1", port)) == 0


def ffmpeg_stream_count() -> int:
    """Return the number of FFmpeg processes (pgrep -c ffmpeg)."""
    try:
        out = subprocess.check_output(
            ["pgrep", "-c", "ffmpeg"],
            stderr=subprocess.DEVNULL,
        )
        return int(out.strip())
    except (subprocess.CalledProcessError, ValueError):
        return 0


def mediamtx_paths() -> list:
    """Query the MediaMTX API and return ALL path items (bypasses 100-item page cap)."""
    try:
        url = f"http://127.0.0.1:{API_PORT}/v3/paths/list?itemsPerPage=9999"
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=2) as resp:
            data = json.loads(resp.read().decode())
            return data.get("items", [])
    except Exception:
        return []


def run_script(name: str) -> str:
    """Run a shell script inside INSTALL_DIR and return combined output."""
    script = os.path.join(INSTALL_DIR, name)
    try:
        result = subprocess.run(
            ["bash", script],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=INSTALL_DIR,
        )
        return result.stdout + result.stderr
    except FileNotFoundError:
        return f"Script not found: {script}"
    except subprocess.TimeoutExpired:
        return "Command timed out after 30 s"


def run_cmd(cmd: list) -> str:
    """Run an arbitrary command list and return combined output."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=INSTALL_DIR,
        )
        return result.stdout + result.stderr
    except Exception as exc:
        return str(exc)


# ---------------------------------------------------------------------------
# HTML — Login page
# ---------------------------------------------------------------------------

LOGIN_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="en" style="background:#0b0d11;">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>CCTV Simulator — Sign In</title>
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet" />
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  :root {
    --bg:        #0b0d11;
    --surface:   #13161d;
    --surface-2: #1a1e28;
    --border:    #242836;
    --border-hi: #3a3f52;
    --text:      #e8e8ec;
    --text-dim:  #9396a5;
    --accent:    #6366f1;
    --accent-g:  linear-gradient(135deg, #818cf8, #6366f1);
    --radius:    14px;
    --radius-sm: 10px;
  }

  body {
    font-family: 'Inter', system-ui, -apple-system, sans-serif;
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 1.5rem;
  }

  /* Subtle grid pattern overlay */
  body::before {
    content: '';
    position: fixed;
    inset: 0;
    background-image:
      linear-gradient(rgba(99,102,241,0.03) 1px, transparent 1px),
      linear-gradient(90deg, rgba(99,102,241,0.03) 1px, transparent 1px);
    background-size: 40px 40px;
    pointer-events: none;
    z-index: 0;
  }

  .login-wrap {
    position: relative;
    z-index: 1;
    width: 100%;
    max-width: 420px;
    animation: slideUp 0.45s cubic-bezier(0.22,1,0.36,1) both;
  }

  /* Glow halo behind the card */
  .login-wrap::before {
    content: '';
    position: absolute;
    inset: -40px;
    background: radial-gradient(ellipse at 50% 60%, rgba(99,102,241,0.18), transparent 70%);
    pointer-events: none;
    border-radius: 50%;
    z-index: -1;
  }

  .login-header {
    text-align: center;
    margin-bottom: 2rem;
  }
  .login-logo {
    font-size: 2rem;
    font-weight: 800;
    background: var(--accent-g);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    letter-spacing: -0.03em;
    display: block;
    margin-bottom: 0.4rem;
  }
  .login-subtitle {
    font-size: 0.8rem;
    color: var(--text-dim);
    letter-spacing: 0.04em;
  }

  .login-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 2rem 2rem 1.75rem;
    box-shadow: 0 8px 40px rgba(0,0,0,0.5), 0 0 0 1px rgba(99,102,241,0.06);
  }

  .form-row {
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
    margin-bottom: 1.1rem;
  }
  .form-row label {
    font-size: 0.72rem;
    font-weight: 600;
    color: var(--text-dim);
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }
  .form-row input {
    background: var(--surface-2);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    padding: 0.72rem 0.95rem;
    font-family: inherit;
    font-size: 0.88rem;
    color: var(--text);
    outline: none;
    transition: border-color 0.2s, box-shadow 0.2s;
    width: 100%;
  }
  .form-row input:focus {
    border-color: var(--accent);
    box-shadow: 0 0 0 3px rgba(99,102,241,0.2);
  }
  .form-row input::placeholder { color: var(--text-dim); opacity: 0.4; }

  .btn-signin {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    width: 100%;
    padding: 0.78rem 1.5rem;
    margin-top: 0.5rem;
    border: none;
    border-radius: var(--radius-sm);
    background: var(--accent-g);
    color: #fff;
    font-family: inherit;
    font-size: 0.88rem;
    font-weight: 700;
    cursor: pointer;
    letter-spacing: 0.02em;
    transition: box-shadow 0.25s, transform 0.12s;
  }
  .btn-signin:hover {
    box-shadow: 0 4px 28px rgba(99,102,241,0.5), 0 0 0 1px rgba(129,140,248,0.3);
  }
  .btn-signin:active { transform: scale(0.97); }

  .error-msg {
    background: rgba(248,113,113,0.1);
    border: 1px solid rgba(248,113,113,0.25);
    border-radius: var(--radius-sm);
    color: #fca5a5;
    font-size: 0.8rem;
    padding: 0.65rem 0.9rem;
    margin-bottom: 1.1rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .footer {
    margin-top: 2rem;
    font-size: 0.68rem;
    color: var(--text-dim);
    text-align: center;
    opacity: 0.5;
    position: relative;
    z-index: 1;
  }

  @keyframes slideUp {
    from { opacity: 0; transform: translateY(20px); }
    to   { opacity: 1; transform: translateY(0); }
  }
</style>
</head>
<body>

<div class="login-wrap">
  <div class="login-header">
    <span class="login-logo">📹 CCTV Simulator</span>
    <span class="login-subtitle">Restricted Access — Sign in to continue</span>
  </div>

  <div class="login-card">
    {% if error %}
    <div class="error-msg">
      <span>⚠</span>
      <span>{{ error }}</span>
    </div>
    {% endif %}

    <form method="POST" action="/login" autocomplete="on">
      <input type="hidden" name="next" value="{{ next }}" />
      <div class="form-row">
        <label for="username">Username</label>
        <input
          id="username"
          name="username"
          type="text"
          placeholder="Enter username"
          autocomplete="username"
          value="{{ username }}"
          required
        />
      </div>
      <div class="form-row">
        <label for="password">Password</label>
        <input
          id="password"
          name="password"
          type="password"
          placeholder="Enter password"
          autocomplete="current-password"
          required
        />
      </div>
      <button type="submit" class="btn-signin" id="signin-btn">
        🔒 Sign In
      </button>
    </form>
  </div>
</div>

<div class="footer">CCTV IP Camera Simulator · Docker Container · Odon Nkongolo</div>

</body>
</html>
"""


# ---------------------------------------------------------------------------
# HTML — Main dashboard
# ---------------------------------------------------------------------------

TEMPLATE = r"""
<!DOCTYPE html>
<html lang="en" style="background:#0b0d11;">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>CCTV Simulator — Dashboard</title>
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet" />
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  :root {
    --bg:        #0b0d11;
    --surface:   #13161d;
    --surface-2: #1a1e28;
    --border:    #242836;
    --border-hi: #3a3f52;
    --text:      #e8e8ec;
    --text-dim:  #9396a5;
    --accent:    #6366f1;
    --accent-g:  linear-gradient(135deg, #818cf8, #6366f1);
    --green:     #34d399;
    --green-dim: rgba(52, 211, 153, 0.12);
    --red:       #f87171;
    --red-dim:   rgba(248, 113, 113, 0.12);
    --amber:     #fbbf24;
    --radius:    14px;
    --radius-sm: 10px;
    --shadow:    0 4px 24px rgba(0,0,0,0.35);
  }

  body {
    font-family: 'Inter', system-ui, -apple-system, sans-serif;
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
    padding: 2rem 2.5rem;
    line-height: 1.5;
  }

  /* ---------- Header ---------- */
  .header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 2.25rem;
    flex-wrap: wrap;
    gap: 1rem;
  }
  .header-left {
    display: flex;
    align-items: center;
    gap: 0.85rem;
  }
  .logo {
    font-size: 1.6rem;
    font-weight: 800;
    background: var(--accent-g);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    letter-spacing: -0.02em;
  }
  .badge {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    font-size: 0.68rem;
    font-weight: 600;
    padding: 0.3rem 0.75rem;
    border-radius: 999px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }
  .badge-ok,
  .badge-err {
    background: rgba(99,102,241,0.12);
    color: var(--accent);
  }
  .badge-dot {
    width: 7px; height: 7px; border-radius: 50%;
    background: var(--accent);
  }

  .header-right {
    display: flex;
    align-items: center;
    gap: 1rem;
  }

  .timestamp {
    font-size: 0.72rem;
    color: var(--text-dim);
    font-variant-numeric: tabular-nums;
  }

  /* Logout link */
  .logout-btn {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    font-size: 0.72rem;
    font-weight: 600;
    color: var(--text-dim);
    text-decoration: none;
    padding: 0.3rem 0.8rem;
    border: 1px solid var(--border);
    border-radius: 999px;
    transition: color 0.2s, border-color 0.2s;
  }
  .logout-btn:hover { color: var(--text); border-color: var(--border-hi); }

  /* ---------- Status Cards ---------- */
  .section-title {
    font-size: 0.7rem;
    font-weight: 600;
    color: var(--text-dim);
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin-bottom: 0.85rem;
  }

  .status-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 1rem;
    margin-bottom: 2.25rem;
  }

  .card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 1.35rem 1.5rem;
    transition: border-color 0.25s, transform 0.2s;
  }
  .card:hover {
    border-color: var(--border-hi);
    transform: translateY(-2px);
  }
  .card .card-label {
    font-size: 0.7rem;
    color: var(--text-dim);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 0.6rem;
  }
  .card .card-value {
    font-size: 1.85rem;
    font-weight: 700;
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .indicator {
    width: 12px; height: 12px; border-radius: 50%;
    flex-shrink: 0;
  }
  .indicator-on,
  .indicator-off {
    background: var(--accent);
  }

  /* ---------- Two-column layout ---------- */
  .main-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1.25rem;
    margin-bottom: 2rem;
  }
  @media (max-width: 800px) {
    .main-grid { grid-template-columns: 1fr; }
  }

  .panel {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 1.5rem;
  }
  .panel-title {
    font-size: 0.82rem;
    font-weight: 700;
    margin-bottom: 1.25rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }
  .panel-title .icon {
    font-size: 1rem;
  }

  /* ---------- Config Form ---------- */
  .form-row {
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
    margin-bottom: 1.1rem;
  }
  .form-row label {
    font-size: 0.72rem;
    font-weight: 600;
    color: var(--text-dim);
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }
  .form-row input {
    background: var(--surface-2);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    padding: 0.65rem 0.9rem;
    font-family: inherit;
    font-size: 0.85rem;
    color: var(--text);
    outline: none;
    transition: border-color 0.2s, box-shadow 0.2s;
    width: 100%;
  }
  .form-row input:focus {
    border-color: var(--accent);
    box-shadow: 0 0 0 3px rgba(99,102,241,0.18);
  }
  .form-row input::placeholder { color: var(--text-dim); opacity: 0.5; }

  /* ---------- Buttons ---------- */
  .btn {
    display: inline-flex;
    align-items: center;
    gap: 0.45rem;
    padding: 0.6rem 1.35rem;
    border: none;
    border-radius: var(--radius-sm);
    font-family: inherit;
    font-size: 0.8rem;
    font-weight: 600;
    cursor: pointer;
    transition: transform 0.12s, box-shadow 0.25s, opacity 0.2s;
    white-space: nowrap;
  }
  .btn:active { transform: scale(0.96); }
  .btn:disabled { opacity: 0.45; cursor: not-allowed; }

  .btn-accent {
    background: var(--accent-g);
    color: #fff;
  }
  .btn-accent:hover { box-shadow: 0 4px 20px rgba(99,102,241,0.35); }

  .btn-green {
    background: var(--green);
    color: #062e1c;
  }
  .btn-green:hover { box-shadow: 0 4px 20px rgba(52,211,153,0.35); }

  .btn-red {
    background: var(--red);
    color: #fff;
  }
  .btn-red:hover { box-shadow: 0 4px 20px rgba(248,113,113,0.3); }

  .btn-ghost {
    background: var(--surface-2);
    color: var(--text-dim);
    border: 1px solid var(--border);
  }
  .btn-ghost:hover { border-color: var(--border-hi); color: var(--text); }

  .btn-row {
    display: flex;
    gap: 0.75rem;
    flex-wrap: wrap;
  }

  /* ---------- Terminal log ---------- */
  .terminal {
    background: #090b0f;
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 1rem 1.25rem;
    font-family: 'SF Mono', 'Fira Code', 'Cascadia Code', monospace;
    font-size: 0.75rem;
    line-height: 1.65;
    color: var(--text-dim);
    white-space: pre-wrap;
    word-break: break-all;
    max-height: 280px;
    overflow-y: auto;
    margin-top: 1.25rem;
    display: none;
  }
  .terminal.visible { display: block; animation: fadeIn 0.3s ease; }
  .terminal .prompt { color: var(--green); }
  .terminal .err    { color: var(--red); }

  /* ---------- Paths table ---------- */
  .paths-panel { margin-bottom: 2rem; }
  table {
    width: 100%;
    border-collapse: collapse;
  }
  th {
    text-align: left;
    font-size: 0.68rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--text-dim);
    padding: 0.55rem 0.85rem;
    border-bottom: 1px solid var(--border);
  }
  td {
    padding: 0.6rem 0.85rem;
    font-size: 0.82rem;
    border-bottom: 1px solid var(--border);
    color: var(--text);
  }
  tr:hover td { background: rgba(99,102,241,0.04); }

  /* ---------- Footer ---------- */
  .footer {
    margin-top: 3rem;
    font-size: 0.68rem;
    color: var(--text-dim);
    text-align: center;
    opacity: 0.6;
  }

  /* ---------- Animations ---------- */
  @keyframes fadeIn {
    from { opacity: 0; transform: translateY(6px); }
    to   { opacity: 1; transform: translateY(0);   }
  }
  .fade-in { animation: fadeIn 0.4s ease both; }
</style>
</head>
<body>

<!-- ==================== HEADER ==================== -->
<div class="header fade-in">
  <div class="header-left">
    <span class="logo">📹 CCTV Simulator</span>
    <span id="rtsp-badge" class="badge badge-ok">
      <span class="badge-dot"></span>
      <span id="rtsp-badge-text">{{ "Connected" if rtsp_up else "Down" }}</span>
    </span>
  </div>
  <div class="header-right">
    <span class="timestamp" id="ts">{{ now }}</span>
    <a href="/logout" class="logout-btn" title="Sign out">⎋ Sign Out</a>
  </div>
</div>

<div class="section-title fade-in">System Status</div>
<div class="status-grid fade-in">
  <div class="card">
    <div class="card-label">RTSP Server · Port {{ rtsp_port }}</div>
    <div class="card-value">
      <span id="rtsp-indicator" class="indicator indicator-on"></span>
      <span id="rtsp-text">{{ "Listening" if rtsp_up else "Down" }}</span>
    </div>
  </div>
  <div class="card">
    <div class="card-label">Active Camera Streams</div>
    <div class="card-value" id="ffmpeg-count">{{ ffmpeg_count }}</div>
  </div>
  <div class="card">
    <div class="card-label">Configured Paths</div>
    <div class="card-value">{{ camera_count }}</div>
  </div>
</div>

<!-- ==================== CONFIG + CONTROLS ==================== -->
<div class="main-grid fade-in">

  <!-- Configuration panel -->
  <div class="panel">
    <div class="panel-title"><span class="icon">⚙️</span> Configuration</div>
    <form id="configForm" onsubmit="applyConfig(event)">
      <div class="form-row">
        <label for="camCount">Camera Count</label>
        <input id="camCount" name="camera_count" type="number" min="1"
               value="{{ camera_count }}" placeholder="e.g. 10" />
      </div>
      <div class="form-row">
        <label for="videoPath">Video Path</label>
        <input id="videoPath" name="video_path" type="text"
               value="{{ video_path }}" placeholder="videos/camera.mp4" />
      </div>
      <button type="submit" class="btn btn-accent">⟳ Apply Changes</button>
    </form>
  </div>

  <!-- Controls panel -->
  <div class="panel">
    <div class="panel-title"><span class="icon">🎛️</span> Simulator Controls</div>
    <p style="font-size:0.78rem; color:var(--text-dim); margin-bottom:1.25rem;">
      Start or stop all camera streams. Starting will launch MediaMTX with the
      current configuration. Stopping cleanly kills all MediaMTX and FFmpeg processes.
    </p>
    <div class="btn-row">
      <button class="btn btn-green" onclick="doAction('/api/start')">▶ Start Simulator</button>
      <button class="btn btn-red"   onclick="doAction('/api/stop')">■ Stop Simulator</button>
      <button class="btn btn-ghost" onclick="location.reload()">↻ Refresh</button>
    </div>
  </div>
</div>

<!-- ==================== TERMINAL LOG ==================== -->
<div id="terminal" class="terminal"></div>

<!-- ==================== PATHS TABLE ==================== -->
{% if paths %}
<div class="section-title fade-in" style="margin-top:2rem;">Active Paths</div>
<div class="panel paths-panel fade-in">
  <table>
    <thead><tr><th>Path</th><th>Readers</th><th>Source</th></tr></thead>
    <tbody>
    {% for p in paths %}
      <tr>
        <td style="font-family:monospace; color:var(--accent);">/{{ p.name }}</td>
        <td>{{ p.readers | default([], true) | length }}</td>
        <td>{{ p.source.type if p.source else '—' }}</td>
      </tr>
    {% endfor %}
    </tbody>
  </table>
</div>
{% endif %}

<div class="footer">CCTV IP Camera Simulator · Docker Container · Odon Nkongolo</div>

<script>
function termLog(msg, cls) {
  const t = document.getElementById('terminal');
  t.classList.add('visible');
  const span = document.createElement('span');
  if (cls) span.className = cls;
  span.textContent = msg + '\n';
  t.appendChild(span);
  t.scrollTop = t.scrollHeight;
}

// Update status cards in-place — no page reload, no flash
async function refreshStatus() {
  try {
    const res = await fetch('/api/status');
    if (res.status === 401 || res.redirected) { location.href = '/login'; return; }
    const d = await res.json();
    document.getElementById('rtsp-text').textContent    = d.rtsp_listening ? 'Listening' : 'Down';
    document.getElementById('rtsp-badge-text').textContent = d.rtsp_listening ? 'Connected' : 'Down';
    document.getElementById('ffmpeg-count').textContent = d.ffmpeg_streams;
    const now = new Date();
    document.getElementById('ts').textContent =
      now.toISOString().slice(0,10) + '  ' + now.toTimeString().slice(0,8);
  } catch(_) {}
}

async function doAction(url) {
  const t = document.getElementById('terminal');
  t.innerHTML = '';
  termLog('$ ' + url.replace('/api/', ''), 'prompt');
  termLog('Running…');
  try {
    const res = await fetch(url, { method: 'POST' });
    if (res.status === 401 || res.redirected) { location.href = '/login'; return; }
    const data = await res.json();
    if (data.output) termLog(data.output);
    else termLog(JSON.stringify(data, null, 2));
  } catch (e) {
    termLog('Error: ' + e, 'err');
  }
  termLog('\nDone.', 'prompt');
  // Poll status a few times to pick up the new state without a reload
  setTimeout(refreshStatus, 1000);
  setTimeout(refreshStatus, 3000);
  setTimeout(refreshStatus, 6000);
}

async function applyConfig(e) {
  e.preventDefault();
  const camCount  = document.getElementById('camCount').value;
  const videoPath = document.getElementById('videoPath').value;

  const t = document.getElementById('terminal');
  t.innerHTML = '';
  termLog('$ generate_config.py ' + camCount + ' ' + videoPath, 'prompt');
  termLog('Generating configuration…');

  try {
    const res = await fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ camera_count: parseInt(camCount), video_path: videoPath }),
    });
    if (res.status === 401 || res.redirected) { location.href = '/login'; return; }
    const data = await res.json();
    if (data.output) termLog(data.output);
    else termLog(JSON.stringify(data, null, 2));
    termLog('\nConfig applied.', 'prompt');
    // Update the configured paths card directly — no reload needed
    document.querySelectorAll('.card .card-value').forEach(el => {
      if (el.closest('.card')?.querySelector('.card-label')?.textContent.includes('Configured')) {
        el.textContent = camCount;
      }
    });
    setTimeout(refreshStatus, 800);
  } catch (e) {
    termLog('Error: ' + e, 'err');
  }
}
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Read / write config
# ---------------------------------------------------------------------------

def read_cameras_conf() -> dict:
    """Parse cameras.conf for defaults."""
    defaults = {"camera_count": 10, "video_path": "/opt/cctv-simulator/videos/camera.mp4"}
    conf = os.path.join(INSTALL_DIR, "configs", "cameras.conf")
    if os.path.isfile(conf):
        with open(conf) as f:
            for line in f:
                line = line.strip()
                if line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if key == "CAMERA_COUNT":
                    try:
                        defaults["camera_count"] = int(val)
                    except ValueError:
                        pass
                elif key == "VIDEO_FILE":
                    defaults["video_path"] = val
    return defaults


def write_cameras_conf(cam_count: int, video_path: str) -> None:
    """Persist camera_count and video_path back into cameras.conf."""
    conf_path = os.path.join(INSTALL_DIR, "configs", "cameras.conf")
    lines = [
        "# =============================================================================\n",
        "# cameras.conf — CCTV Simulator Configuration (updated by web GUI)\n",
        "# =============================================================================\n",
        "\n",
        f"CAMERA_COUNT={cam_count}\n",
        "\n",
        f'VIDEO_FILE="{video_path}"\n',
        "\n",
        "RTSP_PORT=8554\n",
        "\n",
        "API_PORT=9997\n",
    ]
    os.makedirs(os.path.dirname(conf_path), exist_ok=True)
    with open(conf_path, "w") as f:
        f.writelines(lines)


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------

@app.route("/login", methods=["GET", "POST"])
def login():
    # Already logged in — go straight to the dashboard
    if session.get("authenticated"):
        return redirect(url_for("dashboard"))

    error    = None
    username = ""
    next_url = request.values.get("next", "/")

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        next_url = request.form.get("next", "/")

        if username == AUTH_USERNAME and password == AUTH_PASSWORD:
            session["authenticated"] = True
            session.permanent = False
            # Guard against open-redirect: only allow relative paths
            if not next_url.startswith("/"):
                next_url = "/"
            return redirect(next_url)
        else:
            error = "Invalid username or password."

    return render_template_string(
        LOGIN_TEMPLATE,
        error=error,
        username=username,
        next=next_url,
    )


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------------------------------------------------------------------------
# Dashboard route
# ---------------------------------------------------------------------------

@app.route("/")
@login_required
def dashboard():
    conf = read_cameras_conf()
    return render_template_string(
        TEMPLATE,
        rtsp_up=is_port_listening(RTSP_PORT),
        rtsp_port=RTSP_PORT,
        ffmpeg_count=ffmpeg_stream_count(),
        paths=mediamtx_paths(),
        now=datetime.now().strftime("%Y-%m-%d  %H:%M:%S"),
        camera_count=conf["camera_count"],
        video_path=conf["video_path"],
    )


# ---------------------------------------------------------------------------
# API routes (all protected)
# ---------------------------------------------------------------------------

@app.route("/api/config", methods=["POST"])
@login_required
def api_config():
    """Run generate_config.py and persist settings back to cameras.conf."""
    data = request.get_json(force=True)
    cam_count  = int(data.get("camera_count", 10))
    video_path = data.get("video_path", "/opt/cctv-simulator/videos/camera.mp4")

    # 1. Generate mediamtx.yml
    output = run_cmd([
        "python3",
        os.path.join(INSTALL_DIR, "generate_config.py"),
        str(cam_count),
        str(video_path),
        os.path.join(INSTALL_DIR, "configs"),
    ])

    # 2. Persist values to cameras.conf so they survive restart / refresh
    try:
        write_cameras_conf(cam_count, video_path)
        output += f"\nSaved: CAMERA_COUNT={cam_count}  VIDEO_FILE={video_path}"
    except Exception as exc:
        output += f"\nWarning: could not update cameras.conf — {exc}"

    return jsonify({"status": "ok", "output": output})


@app.route("/api/start", methods=["POST"])
@login_required
def api_start():
    output = run_script("start_cameras.sh")
    return jsonify({"status": "ok", "output": output})


@app.route("/api/stop", methods=["POST"])
@login_required
def api_stop():
    """Cleanly kill MediaMTX and FFmpeg processes."""
    lines = []
    for proc in ["mediamtx", "ffmpeg"]:
        result = subprocess.run(
            ["pkill", proc],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            lines.append(f"Killed {proc} processes.")
        else:
            lines.append(f"{proc}: no matching processes.")
    # Also clean up pid files
    pids_dir = os.path.join(INSTALL_DIR, "pids")
    if os.path.isdir(pids_dir):
        for pf in os.listdir(pids_dir):
            os.remove(os.path.join(pids_dir, pf))
        lines.append("Cleaned up PID files.")
    return jsonify({"status": "ok", "output": "\n".join(lines)})


@app.route("/api/status")
@login_required
def api_status():
    return jsonify({
        "rtsp_listening": is_port_listening(RTSP_PORT),
        "ffmpeg_streams": ffmpeg_stream_count(),
        "paths": mediamtx_paths(),
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
