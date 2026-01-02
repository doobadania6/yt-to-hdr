import os
import subprocess
import requests
import re
from io import BytesIO
from PIL import Image, ImageEnhance, ImageFilter
from flask import Flask, render_template_string, request, Response

app = Flask(__name__)

# Dynamiczna lista serwerów proxy
def get_instances():
    try:
        res = requests.get("https://api.invidious.io/instances?sort_by=health", timeout=3)
        if res.status_code == 200:
            return [f"https://{i[0]}" for i in res.json() if i[1].get('type') == 'https' and i[1].get('health', 0) > 90]
    except:
        return ["https://inv.tux.pizza", "https://yewtu.be", "https://vid.puffyan.us"]

def apply_hdr(image_bytes):
    try:
        img = Image.open(BytesIO(image_bytes))
        img = ImageEnhance.Contrast(img).enhance(1.4)
        img = img.filter(ImageFilter.SHARPEN)
        img = ImageEnhance.Color(img).enhance(1.3)
        out = BytesIO()
        img.save(out, format="JPEG", quality=85)
        return out.getvalue()
    except: return image_bytes

@app.route('/')
def home():
    return render_template_string('''
    <!DOCTYPE html>
    <html>
    <head>
        <title>YT HDR Frame Extractor</title>
        <style>
            body { background: #000; color: #fff; font-family: sans-serif; text-align: center; padding: 20px; }
            input { padding: 12px; width: 300px; border-radius: 8px; border: 1px solid #333; background: #111; color: #fff; }
            button { padding: 12px 20px; background: red; color: white; border: none; border-radius: 8px; cursor: pointer; font-weight: bold; }
            #gallery { display: flex; flex-wrap: wrap; justify-content: center; gap: 15px; margin-top: 30px; }
            .frame-box { border: 1px solid #333; padding: 5px; border-radius: 10px; background: #111; }
            img { width: 300px; border-radius: 5px; display: block; }
            .dl-btn { display: block; margin-top: 5px; color: #aaa; text-decoration: none; font-size: 12px; }
        </style>
    </head>
    <body>
        <h1>YouTube Frame Extractor</h1>
        <input type="text" id="url" placeholder="Link YouTube...">
        <button onclick="loadFrames()">POKAŻ KLATKI</button>
        <div id="status"></div>
        <div id="gallery"></div>

        <script>
            function loadFrames() {
                const url = document.getElementById('url').value;
                const v_id = url.match(/(?:v=|be\/|shorts\/)([a-zA-Z0-9_-]{11})/)[1];
                const gallery = document.getElementById('gallery');
                const status = document.getElementById('status');
                
                gallery.innerHTML = '';
                status.innerText = "Łączenie z proxy...";

                // Generujemy 12 klatek (możesz zmienić ilość)
                for(let i=1; i<=12; i++) {
                    const div = document.createElement('div');
                    div.className = 'frame-box';
                    div.innerHTML = `
                        <img src="/frame?v=${v_id}&n=${i}" alt="Ładowanie...">
                        <a href="/frame?v=${v_id}&n=${i}" download="kadr_${i}.jpg" class="dl-btn">Pobierz JPG</a>
                    `;
                    gallery.appendChild(div);
                }
                status.innerText = "Klatki ładowane są niezależnie. Kliknij prawym na zdjęcie, aby zapisać.";
            }
        </script>
    </body>
    </html>
    ''')

@app.route('/frame')
def get_frame():
    v_id = request.args.get('v')
    frame_no = int(request.args.get('n', 1))
    
    # Pobieranie danych o streamie
    instances = get_instances()
    stream_url = None
    duration = 0
    
    for base in instances[:10]:
        try:
            r = requests.get(f"{base}/api/v1/videos/{v_id}", timeout=3)
            if r.status_code == 200:
                data = r.json()
                streams = [s for s in data.get('formatStreams', []) if 'video/mp4' in s.get('type', '')]
                if streams:
                    stream_url = streams[0]['url']
                    duration = data.get('lengthSeconds', 0)
                    break
        except: continue

    if not stream_url: return "Błąd proxy", 500

    # Obliczanie czasu klatki
    ts = (duration // 13) * frame_no
    
    # FFmpeg wycina konkretną klatkę
    cmd = [
        'ffmpeg', '-ss', str(ts), '-i', stream_url,
        '-frames:v', '1', '-q:v', '2', '-f', 'image2', '-vcodec', 'mjpeg', 'pipe:1'
    ]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)
    
    if proc.stdout:
        processed = apply_hdr(proc.stdout)
        return Response(processed, mimetype='image/jpeg')
    return "Błąd FFmpeg", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
