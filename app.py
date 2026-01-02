import os
import cv2
import numpy as np
import yt_dlp
import zipfile
from io import BytesIO
from flask import Flask, render_template_string, request, Response, stream_with_context

app = Flask(__name__)

def apply_hdr_effect(image):
    # Zmniejszamy klatkę do 720p dla stabilności RAM
    h, w = image.shape[:2]
    if h > 720:
        image = cv2.resize(image, (int(w * (720/h)), 720))

    # HDR - CLAHE
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    l = clahe.apply(l)
    img = cv2.cvtColor(cv2.merge((l,a,b)), cv2.COLOR_LAB2BGR)
    
    # Wyostrzanie i nasycenie
    gaussian = cv2.GaussianBlur(img, (0, 0), 1.0)
    img = cv2.addWeighted(img, 1.4, gaussian, -0.4, 0)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV).astype("float32")
    hsv[:, :, 1] *= 1.3
    hsv[:, :, 1] = np.clip(hsv[:, :, 1], 0, 255)
    return cv2.cvtColor(hsv.astype("uint8"), cv2.COLOR_HSV2BGR)

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="UTF-8">
    <title>YT HDR Frames v3</title>
    <style>
        body { font-family: sans-serif; background: #000; color: white; text-align: center; padding-top: 100px; }
        .box { background: #111; padding: 30px; border-radius: 20px; display: inline-block; border: 1px solid #333; }
        input { padding: 12px; width: 300px; border-radius: 5px; border: none; }
        button { padding: 12px 25px; background: #ff0000; color: white; border: none; border-radius: 5px; cursor: pointer; font-weight: bold; }
        #status { margin-top: 20px; color: #aaa; font-size: 14px; }
    </style>
</head>
<body>
    <div class="box">
        <h1>YT to HDR Photo</h1>
        <input type="text" id="url" placeholder="Wklej link YouTube...">
        <button onclick="download()">POBIERZ ZIP</button>
        <div id="status"></div>
    </div>
    <script>
        function download() {
            const url = document.getElementById('url').value;
            if(!url) return;
            document.getElementById('status').innerText = "Trwa generowanie... Paczka ZIP zacznie się pobierać automatycznie.";
            window.location.href = "/stream_zip?url=" + encodeURIComponent(url);
        }
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/stream_zip')
def stream_zip():
    video_url_raw = request.args.get('url')
    
    def generate():
        # Ustawienia yt-dlp
        ydl_opts = {'format': 'bestvideo[height<=720][ext=mp4]', 'quiet': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url_raw, download=False)
            stream_url = info['url']
        
        cap = cv2.VideoCapture(stream_url)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        step = total_frames // 31
        
        # Inicjalizacja strumienia ZIP
        queue = BytesIO()
        with zipfile.ZipFile(queue, mode='w', compression=zipfile.ZIP_STORED) as zf:
            for i in range(30):
                cap.set(cv2.CAP_PROP_POS_FRAMES, (i + 1) * step)
                ret, frame = cap.read()
                if ret:
                    processed = apply_hdr_effect(frame)
                    _, buffer = cv2.imencode(".jpg", processed, [cv2.IMWRITE_JPEG_QUALITY, 85])
                    
                    # Tworzymy nagłówek pliku w ZIP
                    zf.writestr(f"foto_{i+1}.jpg", buffer.tobytes())
                    
                    # Wypychamy to, co aktualnie mamy w buforze do użytkownika
                    data = queue.getvalue()
                    yield data
                    queue.truncate(0)
                    queue.seek(0)
        cap.release()

    return Response(stream_with_context(generate()), mimetype='application/zip', 
                    headers={"Content-Disposition": "attachment; filename=frames_hdr.zip"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
