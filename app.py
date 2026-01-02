import os
import subprocess
import requests
import zipfile
import re
from io import BytesIO
from PIL import Image, ImageEnhance, ImageFilter
from flask import Flask, render_template_string, request, send_file

app = Flask(__name__)

# Lista publicznych instancji Invidious (jeśli jedna nie działa, sprawdzamy kolejną)
INVIDIOUS_INSTANCES = [
    "https://invidious.snopyta.org",
    "https://yewtu.be",
    "https://invidious.kavin.rocks",
    "https://vid.puffyan.us"
]

def apply_hdr_effect(image_bytes):
    try:
        img = Image.open(BytesIO(image_bytes))
        img = ImageEnhance.Contrast(img).enhance(1.5)
        img = img.filter(ImageFilter.SHARPEN)
        img = ImageEnhance.Color(img).enhance(1.4)
        out = BytesIO()
        img.save(out, format="JPEG", quality=90)
        return out.getvalue()
    except:
        return image_bytes

def get_video_data(video_id):
    """Pobiera bezpośredni link do wideo przez Invidious API."""
    for instance in INVIDIOUS_INSTANCES:
        try:
            res = requests.get(f"{instance}/api/v1/videos/{video_id}", timeout=10)
            if res.status_code == 200:
                data = res.json()
                # Szukamy formatu MP4, najlepiej 720p
                formats = [f for f in data['formatStreams'] if f['container'] == 'mp4']
                if formats:
                    return formats[0]['url'], data['lengthSeconds']
        except:
            continue
    return None, None

@app.route('/')
def index():
    return '''
    <body style="background:#000;color:white;text-align:center;padding-top:100px;font-family:sans-serif;">
        <div style="border:1px solid red; display:inline-block; padding:30px; border-radius:15px;">
            <h1>YT to Photo HDR (Proxy Mode)</h1>
            <input type="text" id="url" placeholder="Link YouTube" style="padding:10px;width:300px;">
            <button onclick="go()" style="padding:10px;background:red;color:white;border:none;cursor:pointer;">POBIERZ ZIP</button>
            <p id="st"></p>
        </div>
        <script>
            function go() {
                const url = document.getElementById('url').value;
                document.getElementById('st').innerText = "Praca przez Proxy... Czekaj ok. 60s.";
                window.location.href = "/generate?url=" + encodeURIComponent(url);
            }
        </script>
    </body>
    '''

@app.route('/generate')
def generate():
    url = request.args.get('url')
    # Wyciąganie ID filmu z linku
    video_id_match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11}).*", url)
    if not video_id_match:
        return "Niepoprawny link", 400
    
    video_id = video_id_match.group(1)
    stream_url, duration = get_video_data(video_id)
    
    if not stream_url:
        return "Błąd: Wszystkie serwery proxy są zajęte. Spróbuj za chwilę.", 503

    try:
        zip_mem = BytesIO()
        with zipfile.ZipFile(zip_mem, 'w') as zf:
            num = 15
            step = duration // (num + 1)
            for i in range(1, num + 1):
                ts = i * step
                # FFmpeg pobiera klatkę przez link z proxy
                cmd = ['ffmpeg', '-ss', str(ts), '-i', stream_url, '-frames:v', '1', '-f', 'image2', '-vcodec', 'mjpeg', 'pipe:1']
                p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=45)
                if p.stdout:
                    zf.writestr(f"foto_{i:02d}.jpg", apply_hdr_effect(p.stdout))
        
        zip_mem.seek(0)
        return send_file(zip_mem, mimetype='application/zip', as_attachment=True, download_name='kadry_hdr_proxy.zip')
    except Exception as e:
        return f"Błąd przetwarzania: {str(e)}", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
