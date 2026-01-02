import os
import cv2
import numpy as np
import yt_dlp
import zipfile
from io import BytesIO
from flask import Flask, render_template_string, request, send_file, jsonify

app = Flask(__name__)

# Funkcja "Magiczny Filtr HDR"
def apply_hdr_effect(image):
    # 1. CLAHE - Poprawa detali w cieniach i światłach
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
    cl = clahe.apply(l)
    limg = cv2.merge((cl,a,b))
    enhanced_img = cv2.cvtColor(limg, cv2.COLOR_LAB2BGR)
    
    # 2. Unsharp Mask - Wyostrzanie krawędzi
    gaussian_3 = cv2.GaussianBlur(enhanced_img, (0, 0), 2.0)
    unsharp = cv2.addWeighted(enhanced_img, 1.5, gaussian_3, -0.5, 0)
    
    # 3. Podbicie kolorów (Saturation)
    hsv = cv2.cvtColor(unsharp, cv2.COLOR_BGR2HSV).astype("float32")
    hsv[:, :, 1] *= 1.3  # Mocniejsze podbicie kolorów
    hsv[:, :, 1] = np.clip(hsv[:, :, 1], 0, 255)
    return cv2.cvtColor(hsv.astype("uint8"), cv2.COLOR_HSV2BGR)

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="UTF-8">
    <title>YT do Foto HDR</title>
    <style>
        body { font-family: sans-serif; background: #121212; color: white; text-align: center; padding: 50px; }
        .card { background: #1e1e1e; padding: 30px; border-radius: 15px; max-width: 500px; margin: auto; }
        input { width: 80%; padding: 10px; border-radius: 5px; border: none; margin: 10px 0; }
        button { background: #ff0000; color: white; border: none; padding: 15px 30px; border-radius: 5px; cursor: pointer; font-weight: bold; }
        #status { margin-top: 20px; color: #888; }
    </style>
</head>
<body>
    <div class="card">
        <h1>YT Video to Photos</h1>
        <p>Generuj 30 ulepszonych zdjęć HDR z filmu</p>
        <input type="text" id="ytUrl" placeholder="Link do YouTube">
        <br>
        <button onclick="startProcessing()">GENERUJ PACZKĘ ZDJĘĆ</button>
        <div id="status"></div>
    </div>

    <script>
        async function startProcessing() {
            const url = document.getElementById('ytUrl').value;
            const status = document.getElementById('status');
            if(!url) return alert("Wklej link!");
            
            status.innerHTML = "Trwa łączenie ze strumieniem... (może to zająć do minuty)";
            
            try {
                window.location.href = `/process?url=${encodeURIComponent(url)}`;
                status.innerHTML = "Przetwarzanie rozpoczęte. Twoja paczka ZIP zacznie się pobierać automatycznie.";
            } catch(e) { status.innerHTML = "Błąd."; }
        }
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/process')
def process():
    video_url_raw = request.args.get('url')
    count = 30
    
    ydl_opts = {'format': 'bestvideo[height<=1080]', 'quiet': True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(video_url_raw, download=False)
        video_stream_url = info['url']
    
    cap = cv2.VideoCapture(video_stream_url)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    step = total_frames // (count + 1)
    
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, 'a', zipfile.ZIP_DEFLATED) as zip_file:
        for i in range(count):
            cap.set(cv2.CAP_PROP_POS_FRAMES, (i + 1) * step)
            ret, frame = cap.read()
            if ret:
                # Aplikujemy filtry
                processed = apply_hdr_effect(frame)
                # Kodujemy do JPG w pamięci RAM
                is_success, buffer = cv2.imencode(".jpg", processed, [cv2.IMWRITE_JPEG_QUALITY, 90])
                if is_success:
                    zip_file.writestr(f"foto_{i+1}.jpg", buffer.tobytes())
    
    cap.release()
    zip_buffer.seek(0)
    
    return send_file(
        zip_buffer,
        mimetype='application/zip',
        as_attachment=True,
        download_name='karty_z_filmu_hdr.zip'
    )

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)