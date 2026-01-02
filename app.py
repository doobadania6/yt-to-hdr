import os
import subprocess
import requests
import re
from io import BytesIO
from PIL import Image, ImageEnhance
from flask import Flask, render_template_string, request, Response

app = Flask(__name__)

# Lista najbardziej stabilnych instancji
INSTANCES = ["https://yewtu.be", "https://invidious.lunar.icu", "https://inv.tux.pizza", "https://invidious.projectsegfau.lt"]

def apply_hdr(image_bytes):
    try:
        img = Image.open(BytesIO(image_bytes))
        img = ImageEnhance.Contrast(img).enhance(1.4)
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
        <title>HDR Frame Extractor v9</title>
        <style>
            body { background: #0c0c0c; color: #eee; font-family: sans-serif; text-align: center; padding: 20px; }
            input { padding: 15px; width: 350px; border-radius: 8px; border: 1px solid #333; background: #000; color: #fff; }
            button { padding: 15px 25px; background: #e50914; color: white; border: none; border-radius: 8px; cursor: pointer; font-weight: bold; }
            #gallery { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 20px; padding: 20px; }
            .card { background: #1a1a1a; padding: 15px; border-radius: 12px; border: 1px solid #333; }
            img { width: 100%; border-radius: 8px; background: #000; min-height: 170px; display: block; }
            .btn-dl { display: block; margin-top: 15px; padding: 10px; background: #333; color: white; text-decoration: none; border-radius: 5px; font-weight: bold; cursor: pointer; }
        </style>
    </head>
    <body>
        <h1>YouTube HDR Frames</h1>
        <input type="text" id="url" placeholder="Link YouTube...">
        <button onclick="loadGallery()">GENERUJ</button>
        <div id="gallery"></div>
        <script>
            async function loadGallery() {
                const url = document.getElementById('url').value;
                const match = url.match(/(?:v=|be\/|shorts\/)([a-zA-Z0-9_-]{11})/);
                if(!match) return alert("Błędny link!");
                const v_id = match[1];
                const gallery = document.getElementById('gallery');
                gallery.innerHTML = '';
                for(let i=1; i<=12; i++) {
                    gallery.innerHTML += `
                        <div class="card">
                            <img src="/frame/${v_id}/${i}" alt="Ładowanie klatki ${i}...">
                            <a href="/frame/${v_id}/${i}" download="kadr_${i}.jpg" class="btn-dl">POBIERZ JPG</a>
                        </div>`;
                }
            }
        </script>
    </body>
    </html>
    ''')

@app.route('/frame/<v_id>/<int:n>')
def get_frame(v_id, n):
    stream_url = None
    duration = 0
    
    # Próbujemy znaleźć działające proxy
    for base in INSTANCES:
        try:
            r = requests.get(f"{base}/api/v1/videos/{v_id}", timeout=5)
            if r.status_code == 200:
                data = r.json()
                # Szukamy mp4
                formats = [f for f in data.get('formatStreams', []) if 'video/mp4' in f.get('type', '')]
                if formats:
                    stream_url = formats[0]['url']
                    duration = data.get('lengthSeconds', 0)
                    break
        except: continue

    if not stream_url:
        return "Błąd Proxy - YouTube blokuje to połączenie", 500

    timestamp = (duration // 14) * n
    
    # FFmpeg z dodatkowymi flagami stabilności
    cmd = [
        'ffmpeg', '-reconnect', '1', '-reconnect_streamed', '1', '-reconnect_delay_max', '5',
        '-ss', str(timestamp), '-i', stream_url,
        '-frames:v', '1', '-q:v', '2', '-f', 'image2', '-vcodec', 'mjpeg', 'pipe:1'
    ]
    
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=45)
        if proc.stdout and len(proc.stdout) > 1000:
            final_img = apply_hdr(proc.stdout)
            return Response(final_img, mimetype='image/jpeg', headers={"Content-Disposition": f"attachment; filename=kadr_{n}.jpg"})
    except Exception as e:
        return str(e), 500

    return "Błąd generowania", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
