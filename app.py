import os
import subprocess
import yt_dlp
import zipfile
from io import BytesIO
from PIL import Image, ImageEnhance, ImageFilter
from flask import Flask, render_template_string, request, send_file

app = Flask(__name__)

def apply_hdr_lite(image_bytes):
    try:
        img = Image.open(BytesIO(image_bytes))
        img = ImageEnhance.Contrast(img).enhance(1.4)
        img = img.filter(ImageFilter.SHARPEN)
        img = ImageEnhance.Color(img).enhance(1.3)
        output = BytesIO()
        img.save(output, format="JPEG", quality=90)
        return output.getvalue()
    except:
        return image_bytes

HTML_UI = '''
<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="UTF-8">
    <title>YT HDR Extractor (Authorized)</title>
    <style>
        body { font-family: sans-serif; background: #000; color: white; text-align: center; padding-top: 100vh; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }
        .box { background: #111; padding: 40px; border-radius: 20px; border: 1px solid #ff0000; width: 400px; }
        input { width: 100%; padding: 12px; border-radius: 8px; border: 1px solid #333; background: #000; color: white; margin-bottom: 20px; box-sizing: border-box; }
        button { width: 100%; padding: 12px; background: #ff0000; color: white; border: none; border-radius: 8px; cursor: pointer; font-weight: bold; }
        #status { margin-top: 20px; color: #888; font-size: 13px; }
    </style>
</head>
<body>
    <div class="box">
        <h1>YT to Photo Pro</h1>
        <input type="text" id="url" placeholder="Wklej link YouTube...">
        <button onclick="start()">POBIERZ PACZKĘ HDR</button>
        <div id="status"></div>
    </div>
    <script>
        function start() {
            const url = document.getElementById('url').value;
            if(!url) return;
            document.getElementById('status').innerText = "Trwa autoryzacja sesji i generowanie klatek...";
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
    cookie_file = 'cookies.txt'
    
    ydl_opts = {
        'format': 'bestvideo[height<=720][ext=mp4]/best',
        'quiet': True,
        'nocheckcertificate': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    # Jeśli plik cookies istnieje w folderze, używamy go
    if os.path.exists(cookie_file):
        ydl_opts['cookiefile'] = cookie_file

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
                cmd = ['ffmpeg', '-ss', str(ts), '-i', stream_url, '-frames:v', '1', '-f', 'image2', '-vcodec', 'mjpeg', 'pipe:1']
                p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
                if p.stdout:
                    zf.writestr(f"foto_{i:02d}.jpg", apply_hdr_lite(p.stdout))
        
        zip_mem.seek(0)
        return send_file(zip_mem, mimetype='application/zip', as_attachment=True, download_name='yt_frames.zip')
        
    except Exception as e:
        return f"Błąd (prawdopodobnie ciasteczka wygasły): {str(e)}", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
