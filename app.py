import os
import subprocess
import yt_dlp
import zipfile
import requests
from io import BytesIO
from PIL import Image, ImageEnhance, ImageFilter
from flask import Flask, render_template_string, request, send_file, Response, stream_with_context

app = Flask(__name__)

def apply_hdr_lite(image_bytes):
    """Lekka obróbka HDR przy użyciu biblioteki PIL."""
    try:
        img = Image.open(BytesIO(image_bytes))
        
        # 1. Poprawa dynamiki (Contrast)
        img = ImageEnhance.Contrast(img).enhance(1.3)
        
        # 2. Wyostrzenie detali
        img = img.filter(ImageFilter.SHARPEN)
        
        # 3. Nasycenie barw (Saturacja)
        img = ImageEnhance.Color(img).enhance(1.4)
        
        # 4. Jasność (delikatne rozjaśnienie cieni)
        img = ImageEnhance.Brightness(img).enhance(1.1)
        
        output = BytesIO()
        img.save(output, format="JPEG", quality=90)
        return output.getvalue()
    except Exception:
        return image_bytes

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>YT HDR Frame Extractor</title>
    <style>
        body { font-family: -apple-system, sans-serif; background: #0f0f0f; color: white; text-align: center; padding: 20px; }
        .container { max-width: 600px; margin: 50px auto; background: #1a1a1a; padding: 30px; border-radius: 20px; border: 1px solid #ff0000; box-shadow: 0 10px 30px rgba(0,0,0,0.5); }
        h1 { color: #ff0000; margin-bottom: 10px; }
        input { width: 90%; padding: 15px; border-radius: 10px; border: 1px solid #333; background: #000; color: white; margin: 20px 0; outline: none; }
        button { background: #ff0000; color: white; border: none; padding: 15px 40px; border-radius: 10px; cursor: pointer; font-weight: bold; width: 90%; font-size: 16px; }
        button:disabled { background: #444; cursor: not-allowed; }
        .info { font-size: 13px; color: #888; margin-top: 20px; line-height: 1.5; }
        #loader { display: none; margin-top: 20px; }
        .spinner { border: 4px solid rgba(255,255,255,0.1); border-top: 4px solid #ff0000; border-radius: 50%; width: 30px; height: 30px; animation: spin 1s linear infinite; margin: auto; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
    </style>
</head>
<body>
    <div class="container">
        <h1>YouTube to HDR Photos</h1>
        <p>Generuj 20 wysokiej jakości kadrów z obróbką</p>
        <input type="text" id="url" placeholder="Wklej link do filmu YouTube...">
        <button id="btn" onclick="startExport()">GENERUJ PACZKĘ ZIP</button>
        <div id="loader">
            <div class="spinner"></div>
            <p id="status">Inicjalizacja FFmpeg i omijanie blokad...</p>
        </div>
        <div class="info">
            UWAGA: Pierwsze klatki mogą zająć do 30 sekund. <br>
            Jeśli wyskoczy błąd "Sign in", spróbuj inny film lub odśwież stronę.
        </div>
    </div>

    <script>
        function startExport() {
            const url = document.getElementById('url').value;
            if(!url) return alert("Wklej link!");
            
            const btn = document.getElementById('btn');
            const loader = document.getElementById('loader');
            
            btn.disabled = true;
            loader.style.display = "block";
            
            // Przekierowanie do endpointu generującego
            window.location.href = "/generate?url=" + encodeURIComponent(url);
            
            // Reset przycisku po kilku sekundach (żeby użytkownik mógł spróbować ponownie w razie błędu)
            setTimeout(() => {
                btn.disabled = false;
                loader.style.display = "none";
            }, 10000);
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
    if not video_url_raw:
        return "Brak adresu URL", 400

    # Zaawansowane opcje yt-dlp omijające wykrywanie botów
    ydl_opts = {
        'format': 'bestvideo[height<=720][ext=mp4]/best[ext=mp4]/best',
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        # Udawanie nowoczesnej przeglądarki
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url_raw, download=False)
            duration = info.get('duration', 0)
            stream_url = info['url']
            title = "".join([c for c in info.get('title', 'frames') if c.isalnum() or c==' ']).strip()

        def stream_zip():
            zip_buffer = BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_STORED) as zf:
                # Generujemy 20 klatek rozłożonych w czasie filmu
                num_frames = 20
                interval = duration // (num_frames + 1)

                for i in range(1, num_frames + 1):
                    timestamp = i * interval
                    
                    # FFmpeg wycina klatkę bezpośrednio ze strumienia bez pobierania całego filmu
                    # Flaga -ss PRZED -i jest kluczowa dla szybkości (fast seek)
                    cmd = [
                        'ffmpeg', '-ss', str(timestamp), '-i', stream_url,
                        '-frames:v', '1', '-q:v', '2', '-f', 'image2', '-vcodec', 'mjpeg', 'pipe:1'
                    ]
                    
                    process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    
                    if process.stdout:
                        # Nakładamy filtr HDR/Foto
                        hdr_frame = apply_hdr_lite(process.stdout)
                        zf.writestr(f"foto_{i:02d}.jpg", hdr_frame)
                        
                        # Wysyłamy dane do przeglądarki kawałek po kawałku (streaming)
                        chunk = zip_buffer.getvalue()
                        yield chunk
                        zip_buffer.truncate(0)
                        zip_buffer.seek(0)
            
            # Finalizacja ZIP (jeśli zostały jakieś bajty w buforze)
            yield zip_buffer.getvalue()

        return Response(
            stream_with_context(stream_zip()),
            mimetype='application/zip',
            headers={"Content-Disposition": f"attachment; filename={title}_HDR.zip"}
        )

    except Exception as e:
        # Bardziej czytelny błąd dla użytkownika
        error_msg = str(e)
        if "Sign in" in error_msg:
            return "YouTube zablokował serwer (Bot Detection). Spróbuj ponownie za kilka minut lub użyj innego filmu.", 403
        return f"Wystąpił błąd: {error_msg}", 500

if __name__ == '__main__':
    # Render używa zmiennej środowiskowej PORT
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
