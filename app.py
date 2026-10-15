import os
import re
import shutil
import tempfile

import yt_dlp
from flask import Flask, after_this_request, render_template_string, request, send_file

app = Flask(__name__)

URL_RE = re.compile(
    r"^(https?://)?((www|m)\.)?(youtube\.com/shorts/[\w-]{11}|youtu\.be/[\w-]{11})",
    re.IGNORECASE,
)

PAGE = """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Shorts Downloader</title>
<style>
  body { font-family: system-ui, sans-serif; background:#111; color:#eee;
         display:flex; justify-content:center; padding:24px; margin:0; }
  main { width:100%; max-width:420px; }
  h1 { font-size:1.4rem; }
  input, select, button { width:100%; padding:14px; margin-top:10px; font-size:1rem;
         border-radius:10px; border:1px solid #333; background:#1c1c1c; color:#eee;
         box-sizing:border-box; }
  button { background:#e62117; border:0; font-weight:600; cursor:pointer; }
  button:disabled { opacity:.6; }
  .err { color:#ff7b72; margin-top:12px; }
  small { color:#888; display:block; margin-top:16px; }
</style>
</head>
<body>
<main>
  <h1>Shorts Downloader</h1>
  <form method="post" action="/download" onsubmit="document.getElementById('b').disabled=true;document.getElementById('b').textContent='Downloading...';setTimeout(()=>{document.getElementById('b').disabled=false;document.getElementById('b').textContent='Download'},15000)">
    <input name="url" type="url" placeholder="Paste YouTube Shorts link" required>
    <select name="kind">
      <option value="video">Video (MP4)</option>
      <option value="audio">Audio only (M4A)</option>
    </select>
    <button id="b" type="submit">Download</button>
  </form>
  {% if error %}<div class="err">{{ error }}</div>{% endif %}
  <small>Only download content you own or have permission to save.</small>
</main>
</body>
</html>
"""


@app.get("/")
def index():
    return render_template_string(PAGE, error=None)


@app.post("/download")
def download():
    url = (request.form.get("url") or "").strip()
    kind = request.form.get("kind", "video")

    if not URL_RE.match(url):
        return render_template_string(PAGE, error="That doesn't look like a YouTube Shorts link."), 400

    tmp = tempfile.mkdtemp(prefix="shorts_")

    @after_this_request
    def cleanup(response):
        shutil.rmtree(tmp, ignore_errors=True)
        return response

    # No ffmpeg needed: pick single-file formats that already contain what we need.
    fmt = "bestaudio[ext=m4a]/bestaudio" if kind == "audio" else "best[ext=mp4]/best"
    opts = {
        "format": fmt,
        "outtmpl": os.path.join(tmp, "%(title).60s.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "max_filesize": 100 * 1024 * 1024,
    }

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
        files = os.listdir(tmp)
        if not files:
            raise RuntimeError("No file produced")
        path = os.path.join(tmp, files[0])
        return send_file(path, as_attachment=True, download_name=files[0])
    except Exception:
        shutil.rmtree(tmp, ignore_errors=True)
        return render_template_string(
            PAGE,
            error="Download failed. The video may be private, or YouTube blocked this server.",
        ), 502


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
