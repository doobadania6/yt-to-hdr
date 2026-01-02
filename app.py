import os
import subprocess
import yt_dlp
import zipfile
from io import BytesIO
from PIL import Image, ImageEnhance, ImageFilter
from flask import Flask, render_template_string, request, send_file

app = Flask(__name__)

def apply_photo_effect(image_bytes):
    try:
        img = Image.open(BytesIO(image_bytes))
        img = ImageEnhance.Contrast(img).enhance(1.4)
        img = img.filter(ImageFilter.SHARPEN)
        img = ImageEnhance.Color(img).enhance(1.35)
        out = BytesIO()
        img.save(out, format="JPEG", quality=92)
        return out.getvalue()
    except:
        return image_bytes

HTML_UI = '''
<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="UTF-8">
    <title>YT HDR Photo Extractor v5</title>
    <style>
        body { font-family: sans-serif; background: #000; color: white; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; }
        .card { background: #111; padding: 40px; border-radius: 25px; border: 1px solid #ff0000; text-align: center; width: 450px; }
        input { width: 100%; padding: 15px; border-radius: 10px; border: 1px solid #333; background: #000; color: white; margin-bottom: 20px; box-sizing: border-box; }
        button { width: 100%; padding: 15px; background: #ff0000; color: white; border: none; border-radius: 10px; cursor: pointer; font-weight: bold; }
        #status { margin-top: 20px; color: #888; }
    </style>
</head>
<body>
    <div class="card">
        <h1>YouTube to Photo (Bypass v5)</h1>
        <input type="text" id="url" placeholder="Wklej link YouTube...">
        <button onclick="start()">POBIERZ PACZKĘ ZIP</button>
        <div id="status"></div>
    </div>
    <script>
        function start() {
            const url = document.getElementById('url').value;
            if(!url) return;
            document.getElementById('status').innerText = "Trwa omijanie blokad YouTube (może to zająć do 2 minut)...";
            window.location.href = "/generate?url=" + encodeURIComponent(url);
        }
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(HTML_UI)

@app.route('/generate')
def generate():
    video_url = request.args.get('url')
    
    # Opcje omijające blokadę botów przez zmianę klienta na TV (najmniej restrykcyjny)
    ydl_opts = {
        'format': 'bestvideo[height<=720][ext=mp4]/best',
        'quiet': True,
        'nocheckcertificate': True,
        # Kluczowe: używamy klienta TV, który rzadziej blokuje serwery
        'extractor_args': {
            'youtube': {
                'player_client': ['tv', 'android'],
                'player_skip': ['webpage', 'configs'],
            }
        },
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            stream_url = info['url']
            duration = info.get('duration', 0)
            
        zip_mem = BytesIO()
        with zipfile.ZipFile(zip_mem, 'w') as zf:
            num = 15
            step = duration // (num + 1)
            for i in range(1, num + 1):
                ts = i * step
                # Wywołanie FFmpeg zoptymalizowane pod streaming
                cmd = ['ffmpeg', '-ss', str(ts), '-i', stream_url, '-frames:v', '1', '-f', 'image2', '-vcodec', 'mjpeg', 'pipe:1']
                p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
                if p.stdout:
                    zf.writestr(f"foto_{i:02d}.jpg", apply_photo_effect(p.stdout))
        
        zip_mem.seek(0)
        return send_file(zip_mem, mimetype='application/zip', as_attachment=True, download_name='kadry_hdr.zip')
        
    except Exception as e:
        # Jeśli nadal błąd, spróbujemy wyjaśnić użytkownikowi co się dzieje
        return f"Błąd (YouTube zablokował IP serwera): {str(e)}", 403

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
