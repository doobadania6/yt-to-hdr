import os
import subprocess
import requests
import zipfile
import re
from io import BytesIO
from PIL import Image, ImageEnhance, ImageFilter
from flask import Flask, render_template_string, request, send_file

app = Flask(__name__)

# Lista stabilnych instancji Invidious, które pobiorą dane za nas
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
        # Filtry poprawiające jakość klatki wideo
        img = ImageEnhance.Contrast(img).enhance(1.5)
        img = ImageEnhance.Brightness(img).enhance(1.1)
        img = img.filter(ImageFilter.SHARPEN)
        img = ImageEnhance.Color(img).enhance(1.4)
        
        out = BytesIO()
        img.save(out, format="JPEG", quality=90)
        return out.getvalue()
    except:
        return image_bytes

def get_stream_data(v_id):
    """Pobiera link do pliku wideo przez API Invidious."""
    for base_url in INSTANCES:
        try:
            # Zapytanie do API o dane o filmie
            r = requests.get(f"{base_url}/api/v1/videos/{v_id}", timeout=5)
            if r.status_code == 200:
                data = r.json()
                # Szukamy streamu mp4 (najlepiej 720p)
                streams = [s for s in data.get('formatStreams', []) if 'video/mp4' in s.get('type', '')]
                if streams:
                    return streams[0]['url'], data.get('lengthSeconds', 0)
        except:
            continue
    return None, None

@app.route('/')
def home():
    return render_template_string('''
    <body style="background:#000;color:white;text-align:center;padding-top:100px;font-family:sans-serif;">
        <div style="border:2px solid #ff0000; display:inline-block; padding:40px; border-radius:20px; background:#111;">
            <h1 style="color:#ff0000;">YT to HDR Photo <span style="font-size:14px;">v6 BYPASS</span></h1>
            <p style="color:#888;">Pobieranie klatek przez tunel Invidious (Omija blokady bota)</p>
            <input type="text" id="url" placeholder="Wklej link YouTube..." style="padding:15px;width:350px;border-radius:10px;border:none;margin-bottom:10px;">
            <br>
            <button onclick="go()" id="btn" style="padding:15px 40px;background:#ff0000;color:white;border:none;border-radius:10px;cursor:pointer;font-weight:bold;">GENERUJ ZDJĘCIA</button>
            <p id="msg" style="color:#ffcc00;margin-top:20px;"></p>
        </div>
        <script>
            function go() {
                const u = document.getElementById('url').value;
                if(!u) return alert("Wklej link!");
                document.getElementById('btn').disabled = true;
                document.getElementById('msg').innerText = "Inicjowanie tunelu proxy... To potrwa ok. 60-90 sekund.";
                window.location.href = "/generate?url=" + encodeURIComponent(u);
            }
        </script>
    </body>
    ''')

@app.route('/generate')
def generate():
    video_url = request.args.get('url')
    
    # Wyciąganie ID filmu (obsługuje różne formaty linków)
    v_id = None
    patterns = [r"v=([a-zA-Z0-9_-]{11})", r"be/([a-zA-Z0-9_-]{11})", r"embed/([a-zA-Z0-9_-]{11})"]
    for p in patterns:
        res = re.search(p, video_url)
        if res:
            v_id = res.group(1)
            break
    
    if not v_id:
        return "Błędny link YouTube. Upewnij się, że wkleiłeś pełny adres.", 400

    # Pobieranie linku przez Proxy
    stream_url, duration = get_stream_data(v_id)
    if not stream_url:
        return "Błąd: Wszystkie tunele proxy są zajęte. Spróbuj za 2 minuty.", 503

    try:
        zip_mem = BytesIO()
        with zipfile.ZipFile(zip_mem, 'w') as zf:
            # 15 klatek rozłożonych w czasie
            count = 15
            interval = duration // (count + 1)
            
            for i in range(1, count + 1):
                timestamp = i * interval
                # FFmpeg pobiera klatkę prosto z URL dostarczonego przez Invidious
                cmd = [
                    'ffmpeg', '-ss', str(timestamp), '-i', stream_url,
                    '-frames:v', '1', '-f', 'image2', '-vcodec', 'mjpeg', 'pipe:1'
                ]
                proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=40)
                
                if proc.stdout:
                    processed = apply_hdr_style(proc.stdout)
                    zf.writestr(f"kadr_{i:02d}.jpg", processed)
        
        zip_mem.seek(0)
        return send_file(zip_mem, mimetype='application/zip', as_attachment=True, download_name='kadry_hdr_proxy.zip')
    
    except Exception as e:
        return f"Wystąpił błąd podczas generowania: {str(e)}", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
