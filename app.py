import os
import subprocess
import requests
import zipfile
import re
from io import BytesIO
from PIL import Image, ImageEnhance, ImageFilter
from flask import Flask, render_template_string, request, send_file

app = Flask(__name__)

# Baza zapasowych instancji Invidious
INSTANCES = [
    "https://inv.tux.pizza",
    "https://invidious.electrolama.it",
    "https://invidious.drgns.space",
    "https://vid.puffyan.us",
    "https://yewtu.be"
]

def apply_hdr_style(image_bytes):
    """Nakłada filtry poprawiające wygląd klatki (pseudo-HDR)."""
    try:
        img = Image.open(BytesIO(image_bytes))
        # 1. Kontrast
        img = ImageEnhance.Contrast(img).enhance(1.5)
        # 2. Jasność
        img = ImageEnhance.Brightness(img).enhance(1.1)
        # 3. Wyostrzenie
        img = img.filter(ImageFilter.SHARPEN)
        # 4. Kolory (Nasycenie)
        img = ImageEnhance.Color(img).enhance(1.4)
        
        out = BytesIO()
        img.save(out, format="JPEG", quality=90)
        return out.getvalue()
    except:
        return image_bytes

def get_stream_data(v_id):
    """Pobiera link do wideo, dynamicznie rotując między 20 najlepszymi serwerami."""
    search_list = []
    
    # 1. Pobierz listę wszystkich działających instancji z API Invidious
    try:
        # Sortujemy po kondycji (health) i wybieramy tylko te z HTTPS
        api_res = requests.get("https://api.invidious.io/instances?sort_by=health", timeout=5)
        if api_res.status_code == 200:
            data = api_res.json()
            # Wybieramy tylko te, które mają health > 90 i obsługują API v1
            search_list = [
                f"https://{i[0]}" for i in data 
                if i[1].get('type') == 'https' and i[1].get('health', 0) > 90
            ]
    except Exception as e:
        print(f"Błąd API listy: {e}")

    # Dodaj zapasowe serwery na koniec listy, jeśli API by zawiodło
    search_list.extend(INSTANCES)
    search_list = list(dict.fromkeys(search_list)) # Usuń duplikaty

    # 2. Sprawdź pierwsze 20 serwerów z listy
    for base_url in search_list[:20]:
        try:
            # Ustawiamy krótki timeout, żeby nie czekać na martwe serwery
            r = requests.get(f"{base_url}/api/v1/videos/{v_id}?region=PL", timeout=3)
            if r.status_code == 200:
                video_info = r.json()
                # Szukamy streamu MP4
                streams = [s for s in video_info.get('formatStreams', []) if 'video/mp4' in s.get('type', '')]
                if streams:
                    print(f"Sukces! Używam instancji: {base_url}")
                    return streams[0]['url'], video_info.get('lengthSeconds', 0)
        except:
            continue
            
    return None, None

@app.route('/')
def home():
    return render_template_string('''
    <!DOCTYPE html>
    <html lang="pl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>YT HDR Photo Bypass</title>
        <style>
            body { background: #000; color: white; text-align: center; font-family: sans-serif; padding: 50px 20px; }
            .container { border: 2px solid #ff0000; display: inline-block; padding: 40px; border-radius: 20px; background: #111; max-width: 500px; }
            h1 { color: #ff0000; margin-bottom: 5px; }
            input { width: 100%; padding: 15px; border-radius: 10px; border: none; margin: 20px 0; box-sizing: border-box; font-size: 16px; }
            button { width: 100%; padding: 15px; background: #ff0000; color: white; border: none; border-radius: 10px; cursor: pointer; font-weight: bold; font-size: 18px; }
            button:disabled { background: #555; }
            #status { color: #ffcc00; margin-top: 20px; min-height: 20px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>YouTube to Photo</h1>
            <p style="color:#888;">Wersja v6: Tunelowanie Invidious</p>
            <input type="text" id="url" placeholder="Wklej link do YouTube...">
            <button onclick="go()" id="btn">GENERUJ PACZKĘ ZIP</button>
            <div id="status"></div>
        </div>
        <script>
            function go() {
                const u = document.getElementById('url').value;
                if(!u) return alert("Wklej link!");
                document.getElementById('btn').disabled = true;
                document.getElementById('status').innerText = "Szukanie wolnego tunelu i wycinanie klatek (60-120s)...";
                window.location.href = "/generate?url=" + encodeURIComponent(u);
            }
        </script>
    </body>
    </html>
    ''')

@app.route('/generate')
def generate():
    video_url = request.args.get('url')
    
    # Wyciąganie ID filmu z różnych formatów linków
    v_id = None
    patterns = [r"v=([a-zA-Z0-9_-]{11})", r"be/([a-zA-Z0-9_-]{11})", r"embed/([a-zA-Z0-9_-]{11})", r"shorts/([a-zA-Z0-9_-]{11})"]
    for p in patterns:
        res = re.search(p, video_url)
        if res:
            v_id = res.group(1)
            break
    
    if not v_id:
        return "Błędny link YouTube!", 400

    # Pobieranie URL do strumienia przez Proxy
    stream_url, duration = get_stream_data(v_id)
    if not stream_url:
        return "Błąd: Wszystkie proxy są zajęte. Spróbuj za chwilę.", 503

    try:
        zip_mem = BytesIO()
        with zipfile.ZipFile(zip_mem, 'w') as zf:
            count = 15
            # Zabezpieczenie przed bardzo krótkimi filmami
            if duration < count: count = duration if duration > 0 else 1
            interval = duration // (count + 1)
            
            for i in range(1, count + 1):
                timestamp = i * interval
                # FFmpeg - wysoka jakość, szybkie szukanie (-ss przed -i)
                cmd = [
                    'ffmpeg', '-hide_banner', '-loglevel', 'error',
                    '-ss', str(timestamp), '-i', stream_url,
                    '-frames:v', '1', '-q:v', '2', '-f', 'image2', '-vcodec', 'mjpeg', 'pipe:1'
                ]
                proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=45)
                
                if proc.stdout:
                    # Nałożenie filtrów HDR i dodanie do ZIP
                    final_img = apply_hdr_style(proc.stdout)
                    zf.writestr(f"kadr_{i:02d}.jpg", final_img)
        
        zip_mem.seek(0)
        return send_file(
            zip_mem, 
            mimetype='application/zip', 
            as_attachment=True, 
            download_name=f'HDR_Frames_{v_id}.zip'
        )
    
    except Exception as e:
        return f"Błąd krytyczny: {str(e)}", 500

if __name__ == '__main__':
    # Render przypisuje port dynamicznie
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
