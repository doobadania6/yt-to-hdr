import os
import subprocess
import yt_dlp
import zipfile
from io import BytesIO
from PIL import Image, ImageEnhance, ImageFilter
from flask import Flask, render_template_string, request, send_file, Response, stream_with_context

app = Flask(__name__)

def apply_hdr_lite(image_bytes):
    try:
        img = Image.open(BytesIO(image_bytes))
        img = ImageEnhance.Contrast(img).enhance(1.4)
        img = img.filter(ImageFilter.SHARPEN)
        img = ImageEnhance.Color(img).enhance(1.3)
        
        output = BytesIO()
        img.save(output, format="JPEG", quality=85)
        return output.getvalue()
    except:
        return image_bytes

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="UTF-8">
    <title>YT HDR Frame Extractor</title>
    <style>
        body { font-family: sans-serif; background: #0f0f0f; color: white; text-align: center; padding: 50px; }
        .box { background: #1a1a1a; padding: 30px; border-radius: 20px; border: 1px solid #ff0000; display: inline-block; }
        input { padding: 12px; width: 300px; border-radius: 5px; border: 1px solid #333; background: #000; color: white; }
        button { padding: 12px 25px; background: #ff0000; color: white; border: none; border-radius: 5px; cursor: pointer; font-weight: bold; }
        #msg { margin-top: 20px; color: #888; }
    </style>
</head>
<body>
    <div class="box">
        <h1>YouTube to HDR Photos</h1>
        <input type="text" id="url" placeholder="Wklej link YouTube...">
        <button onclick="go()">GENERUJ ZIP</button>
        <div id="msg"></div>
    </div>
    <script>
        function go() {
            const url = document.getElementById('url').value;
            if(!url) return;
            document.getElementById('msg').innerText = "Trwa przetwarzanie... To może potrwać do 2 minut.";
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
    video_url = request.args.get('url')
    
    # Skoncentrowane opcje omijające błędy bota
    ydl_opts = {
        'format': 'bestvideo[height<=720][ext=mp4]/best',
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            stream_url = info['url']
            duration = info.get('duration', 0)
            
        def generate_zip():
            # Używamy BytesIO jako bufora dla całego ZIPa (najbezpieczniejsze na Render)
            memory_zip = BytesIO()
            with zipfile.ZipFile(memory_zip, 'w') as zf:
                # 15 klatek (zmniejszone dla stabilności)
                num_frames = 15
                step = duration // (num_frames + 1)
                
                for i in range(1, num_frames + 1):
                    pos = i * step
                    # FFmpeg wyciąga jedną klatkę
                    cmd = [
                        'ffmpeg', '-ss', str(pos), '-i', stream_url,
                        '-frames:v', '1', '-f', 'image2', '-vcodec', 'mjpeg', 'pipe:1'
                    ]
                    
                    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    if proc.stdout:
                        frame = apply_hdr_lite(proc.stdout)
                        zf.writestr(f"foto_{i:02d}.jpg", frame)
            
            memory_zip.seek(0)
            return memory_zip.read()

        # Wysyłamy plik po wygenerowaniu (jeśli potrwa to < 30s, przejdzie bez streamingu)
        data = generate_zip()
        return send_file(
            BytesIO(data),
            mimetype='application/zip',
            as_attachment=True,
            download_name='kadry_hdr.zip'
        )

    except Exception as e:
        return f"Błąd: {str(e)}", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=os.environ.get("PORT", 5000))
