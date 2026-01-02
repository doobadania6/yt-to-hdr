import os
import subprocess
import requests
import zipfile
import re
from io import BytesIO
from PIL import Image, ImageEnhance, ImageFilter
from flask import Flask, render_template_string, request, send_file

app = Flask(__name__)

# Lista "zdrowych" serwerów proxy, które pobiorą dane za nas
INSTANCES = [
    "https://inv.tux.pizza",
    "https://invidious.electrolama.it",
    "https://invidious.drgns.space",
    "https://vid.puffyan.us",
    "https://yewtu.be"
]

def apply_hdr_style(image_bytes):
    try:
        img = Image.open(BytesIO(image_bytes))
        # Podbicie detali i kolorów dla efektu "zdjęcia"
        img = ImageEnhance.Contrast(img).enhance(1.5)
        img = img.filter(ImageFilter.SHARPEN)
        img = ImageEnhance.Color(img).enhance(1.4)
        out = BytesIO()
        img.save(out, format="JPEG", quality=90)
        return out.getvalue()
    except:
        return image_bytes

def get_stream_url(v_id):
    """Pobiera link do streamu przez API Invidious."""
    for url in INSTANCES:
        try:
            r = requests.get(f"{url}/api/v1/videos/{v_id}", timeout=5)
            if r.status_code == 200:
                data = r.json()
                # Szukamy najwyższej dostępnej jakości w formacie mp4
                streams = [s for s in data.get('formatStreams', []) if 'video/mp4' in s.get('type', '')]
                if streams:
                    return streams[0]['url'], data.get('lengthSeconds', 0)
        except:
            continue
    return None, None

@app.route('/')
def home():
    return render_template_string('''
    <body style="background:#000;color:white;text-align:center;padding:100px;font-family:sans-serif;">
        <div style="border:1px solid #ff0000; display:inline-block; padding:40px; border-radius:20px;">
            <h1>YT to HDR Photo <span style="font-size:12px;color:red;">v6 PROXY</span></h1>
            <input type="text" id="url" placeholder="Link do YouTube" style="padding:15px;width:350px;border-radius:10px;border:none;">
            <button onclick="go()" style="padding:15px;background:red;color:white;border:none;border-radius:10px;cursor:pointer;font-weight:bold;">GENERUJ ZIP</button>
            <p id="msg" style="color:#666;margin-top:20px;"></p>
        </div>
        <script>
            function go() {
                const u = document.getElementById('url').value;
                if(!u) return;
                document.getElementById('msg').innerText = "Łączenie przez tunel proxy... To potrwa około minuty.";
                window.location.href = "/generate?url=" + encodeURIComponent(u);
            }
        </script>
    </body>
    ''')

@app.route('/generate')
def generate():
    video_url = request.args.get('url')
    # Wyciąganie ID filmu
    v_id = None
    matches = [r"v=([a-zA-Z0-9_-]{11})", r"be/([a-zA-Z0-9_-]{11})", r"embed/([a-zA-Z0-9_-]{11})"]
    for p in matches:
        res = re.search(p, video_url)
        if res: v_id = res.group(1); break
    
    if not v_id: return "Błędny link YouTube", 400

    stream_url, duration = get_stream_url(v_id)
    if not stream_url: return "Błąd: Serwery YouTube są obecnie przeciążone. Spróbuj za chwilę.", 503

    zip_mem = BytesIO()
    with zipfile.ZipFile(zip_mem, 'w') as zf:
        num = 15
        step = duration // (num + 1)
        for i in range(1, num + 1):
            ts = i * step
            # FFmpeg wycina klatkę bezpośrednio z URL podanego przez proxy
            cmd = ['ffmpeg', '-ss', str(ts), '-i', stream_url, '-frames:v', '1', '-f', 'image2', '-vcodec', 'mjpeg', 'pipe:1']
            p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=40)
            if p.stdout:
                zf.writestr(f"foto_{i:02d}.jpg", apply_hdr_style(p.stdout))
    
    zip_mem.seek(0)
    return send_file(zip_mem, mimetype='application/zip', as_attachment=True, download_name='kadry_hdr.zip')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
