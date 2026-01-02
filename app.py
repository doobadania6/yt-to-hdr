import os
import subprocess
import requests
import re
from io import BytesIO
from PIL import Image, ImageEnhance
from flask import Flask, render_template_string, request, Response

app = Flask(__name__)

def get_best_instance():
    """Pobiera tylko jedną, najzdrowszą instancję, by nie tracić czasu."""
    try:
        res = requests.get("https://api.invidious.io/instances?sort_by=health", timeout=3)
        if res.status_code == 200:
            data = res.json()
            return f"https://{data[0][0]}"
    except:
        return "https://yewtu.be"

@app.route('/')
def home():
    return render_template_string('''
    <!DOCTYPE html>
    <html>
    <head>
        <title>HDR Frame Extractor v7</title>
        <style>
            body { background: #0c0c0c; color: #eee; font-family: sans-serif; text-align: center; padding: 20px; }
            .input-group { margin: 40px 0; }
            input { padding: 15px; width: 350px; border-radius: 8px; border: 1px solid #333; background: #000; color: #fff; }
            button { padding: 15px 25px; background: #e50914; color: white; border: none; border-radius: 8px; cursor: pointer; font-weight: bold; }
            #gallery { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 20px; padding: 20px; }
            .card { background: #1a1a1a; padding: 10px; border-radius: 12px; border: 1px solid #333; }
            img { width: 100%; border-radius: 8px; background: #000; min-height: 170px; }
            .btn-dl { display: inline-block; margin-top: 10px; color: #e50914; text-decoration: none; font-weight: bold; }
        </style>
    </head>
    <body>
        <h1>YouTube HDR Frames</h1>
        <div class="input-group">
            <input type="text" id="url" placeholder="Wklej link do filmu...">
            <button onclick="loadGallery()">GENERUJ</button>
        </div>
        <div id="gallery"></div>

        <script>
            async function loadGallery() {
                const url = document.getElementById('url').value;
                const match = url.match(/(?:v=|be\/|shorts\/)([a-zA-Z0-9_-]{11})/);
                if(!match) return alert("Błędny link!");
                
                const v_id = match[1];
                const gallery = document.getElementById('gallery');
                gallery.innerHTML = '<p>Przygotowuję klatki (każda ładuje się osobno, by nie przeciążyć serwera)...</p>';

                let html = '';
                for(let i=1; i<=12; i++) {
                    html += `
                        <div class="card">
                            <img src="/frame/${v_id}/${i}" loading="lazy" alt="Klatka ${i}">
                            <a href="/frame/${v_id}/${i}" download="HDR_${v_id}_${i}.jpg" class="btn-dl">POBIERZ JPG</a>
                        </div>
                    `;
                }
                gallery.innerHTML = html;
            }
        </script>
    </body>
    </html>
    ''')

@app.route('/frame/<v_id>/<int:n>')
def get_frame(v_id, n):
    instance = get_best_instance()
    
    try:
        # Pobieranie danych o wideo
        r = requests.get(f"{instance}/api/v1/videos/{v_id}", timeout=5)
        data = r.json()
        duration = data.get('lengthSeconds', 0)
        stream_url = [s['url'] for s in data.get('formatStreams', []) if 'video/mp4' in s.get('type', '')][0]
        
        # Obliczanie czasu (rozrzut klatek co 8% długości filmu)
        timestamp = (duration // 13) * n
        
        # FFmpeg wycina klatkę - skrajnie niskie użycie zasobów
        cmd = [
            'ffmpeg', '-ss', str(timestamp), '-i', stream_url,
            '-frames:v', '1', '-q:v', '4', '-f', 'image2', '-vcodec', 'mjpeg', 'pipe:1'
        ]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
        
        if proc.stdout:
            # Szybki filtr HDR (Pillow)
            img = Image.open(BytesIO(proc.stdout))
            img = ImageEnhance.Contrast(img).enhance(1.4)
            img = ImageEnhance.Color(img).enhance(1.3)
            
            output = BytesIO()
            img.save(output, format="JPEG", quality=85)
            return Response(output.getvalue(), mimetype='image/jpeg')
            
    except Exception as e:
        return str(e), 500
    
    return "Error", 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
