import os
import subprocess
import yt_dlp
import zipfile
from io import BytesIO
from PIL import Image, ImageEnhance, ImageFilter
from flask import Flask, render_template_string, request, send_file

app = Flask(__name__)

def apply_photo_effect(image_bytes):
    """Przekształca klatkę wideo w żywe zdjęcie (Pseudo-HDR)."""
    try:
        img = Image.open(BytesIO(image_bytes))
        
        # 1. Poprawa kontrastu i dynamiki
        img = ImageEnhance.Contrast(img).enhance(1.4)
        
        # 2. Inteligentne wyostrzanie (usuwa 'miękkość' wideo)
        img = img.filter(ImageFilter.SHARPEN)
        img = img.filter(ImageFilter.DETAIL)
        
        # 3. Podbicie kolorów (Saturacja)
        img = ImageEnhance.Color(img).enhance(1.35)
        
        # 4. Korekta jasności
        img = ImageEnhance.Brightness(img).enhance(1.05)
        
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
    <title>YT HDR Photo Extractor</title>
    <style>
        body { font-family: sans-serif; background: #0a0a0a; color: white; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; }
        .card { background: #151515; padding: 40px; border-radius: 25px; border: 1px solid #ff0000; text-align: center; width: 450px; }
        h1 { color: #ff0000; margin-bottom: 20px; }
        input { width: 100%; padding: 15px; border-radius: 10px; border: 1px solid #333; background: #000; color: white; margin-bottom: 20px; box-sizing: border-box; }
        button { width: 100%; padding: 15px; background: #ff0000; color: white; border: none; border-radius: 10px; cursor: pointer; font-weight: bold; font-size: 16px; }
        #status { margin-top: 20px; color: #888; font-size: 14px; }
    </style>
</head>
<body>
    <div class="card">
        <h1>YouTube to Photo</h1>
        <p>Wyciągnij 15 kadrów HDR z dowolnego filmu</p>
        <input type="text" id="url" placeholder="Wklej link YouTube...">
        <button onclick="start()">GENERUJ PACZKĘ ZIP</button>
        <div id="status"></div>
    </div>
    <script>
        function start() {
            const url = document.getElementById('url').value;
            if(!url) return alert("Wklej link!");
            document.getElementById('status').innerText = "Omijanie blokad YT i przetwarzanie klatek... (ok. 60 sek)";
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
    
    # Opcje yt-dlp skonfigurowane pod omijanie systemów bot-detection
    ydl_opts = {
        'format': 'bestvideo[height<=720][ext=mp4]/best',
        'quiet': True,
        'nocheckcertificate': True,
        # Symulacja klienta iOS/Android - najskuteczniejsza metoda bez cookies
        'extractor_args': {
            'youtube': {
                'player_client': ['ios', 'android', 'web'],
            }
        },
        'user_agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1'
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            stream_url = info['url']
            duration = info.get('duration', 0)
            title = "".join(x for x in info['title'] if x.isalnum())[:20]
            
        zip_mem = BytesIO()
        with zipfile.ZipFile(zip_mem, 'w') as zf:
            num = 15
            step = duration // (num + 1)
            
            for i in range(1, num + 1):
                ts = i * step
                # FFmpeg - szybkie wycinanie klatki bez pobierania całego filmu
                cmd = [
                    'ffmpeg', '-ss', str(ts), '-i', stream_url,
                    '-frames:v', '1', '-f', 'image2', '-vcodec', 'mjpeg', 'pipe:1'
                ]
                p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=40)
                
                if p.stdout:
                    # Obróbka zdjęcia
                    photo = apply_photo_effect(p.stdout)
                    zf.writestr(f"foto_{i:02d}.jpg", photo)
        
        zip_mem.seek(0)
        return send_file(zip_mem, mimetype='application/zip', as_attachment=True, download_name=f'{title}_HDR.zip')
        
    except Exception as e:
        error_text = str(e)
        if "Sign in" in error_text:
            return "Błąd: YouTube zablokował serwer. Spróbuj za chwilę lub użyj innego filmu.", 403
        return f"Błąd: {error_text}", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
