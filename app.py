import os
import subprocess
import yt_dlp
import zipfile
from io import BytesIO
from PIL import Image, ImageEnhance, ImageFilter
from flask import Flask, render_template_string, request, send_file

app = Flask(__name__)

def apply_hdr_lite(image_bytes):
    """Lekka obróbka HDR przy użyciu biblioteki PIL (zamiast ciężkiego OpenCV)."""
    img = Image.open(BytesIO(image_bytes))
    
    # 1. Kontrast i detale
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(1.4)
    
    # 2. Wyostrzanie
    img = img.filter(ImageFilter.SHARPEN)
    
    # 3. Nasycenie kolorów
    enhancer = ImageEnhance.Color(img)
    img = enhancer.enhance(1.3)
    
    output = BytesIO()
    img.save(output, format="JPEG", quality=85)
    return output.getvalue()

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="UTF-8">
    <title>YT HDR Frames v4 - Ultra Light</title>
    <style>
        body { font-family: sans-serif; background: #000; color: white; text-align: center; padding-top: 100px; }
        .box { background: #111; padding: 30px; border-radius: 20px; border: 1px solid #ff0000; display: inline-block; }
        input { padding: 12px; width: 300px; border-radius: 5px; border: none; }
        button { padding: 12px 25px; background: #ff0000; color: white; border: none; border-radius: 5px; cursor: pointer; font-weight: bold; }
    </style>
</head>
<body>
    <div class="box">
        <h1>YT Smart Frames (Light)</h1>
        <p>Wersja zoptymalizowana pod darmowe serwery</p>
        <input type="text" id="url" placeholder="Link YouTube...">
        <button onclick="process()">GENERUJ ZIP</button>
        <div id="status" style="margin-top:20px; color:#888;"></div>
    </div>
    <script>
        function process() {
            const url = document.getElementById('url').value;
            if(!url) return;
            document.getElementById('status').innerText = "Trwa wycinanie klatek przez FFmpeg... Czekaj.";
            window.location.href = "/generate?url=" + encodeURIComponent(url);
        }
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/generate')
def generate():
    video_url_raw = request.args.get('url')
    
    try:
        # 1. Pobieramy link do streamu przez yt-dlp
        ydl_opts = {'format': 'bestvideo[height<=720][ext=mp4]', 'quiet': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url_raw, download=False)
            duration = info.get('duration', 0)
            stream_url = info['url']
        
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zf:
            # Robimy 20 zdjęć (zmniejszone z 30 dla pewności, że serwer nie padnie)
            for i in range(1, 21):
                timestamp = (duration // 21) * i
                
                # 2. Używamy FFmpeg do wycięcia klatki (BARDZO LEKKIE)
                # Wyciąga jedną klatkę z konkretnego czasu bez dekodowania całego filmu
                cmd = [
                    'ffmpeg', '-ss', str(timestamp), '-i', stream_url,
                    '-frames:v', '1', '-f', 'image2', '-vcodec', 'mjpeg', 'pipe:1'
                ]
                
                result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                
                if result.stdout:
                    processed_img = apply_hdr_lite(result.stdout)
                    zf.writestr(f"foto_{i}.jpg", processed_img)
        
        zip_buffer.seek(0)
        return send_file(zip_buffer, mimetype='application/zip', as_attachment=True, download_name='kadr_hdr.zip')

    except Exception as e:
        return f"Błąd: {str(e)}", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
