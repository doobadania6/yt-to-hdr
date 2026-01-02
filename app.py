import os
import cv2
import numpy as np
import yt_dlp
import zipfile
from io import BytesIO
from flask import Flask, render_template_string, request, send_file, jsonify

app = Flask(__name__)

def get_sharpness(img):
    """Oblicza ostrość obrazu za pomocą wariancji Laplasjanu."""
    return cv2.Laplacian(img, cv2.CV_64F).var()

def apply_hdr_effect(image):
    """Zoptymalizowany filtr HDR/Foto."""
    # Resize do 720p jeśli klatka jest większa (oszczędność RAM na Renderze)
    h, w = image.shape[:2]
    if h > 720:
        ratio = 720.0 / h
        image = cv2.resize(image, (int(w * ratio), 720))

    # Korekcja lokalna kontrastu
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8,8))
    l = clahe.apply(l)
    enhanced_img = cv2.cvtColor(cv2.merge((l,a,b)), cv2.COLOR_LAB2BGR)
    
    # Wyostrzanie (Subtelne)
    gaussian = cv2.GaussianBlur(enhanced_img, (0, 0), 1.5)
    unsharp = cv2.addWeighted(enhanced_img, 1.4, gaussian, -0.4, 0)
    
    # Podbicie kolorów
    hsv = cv2.cvtColor(unsharp, cv2.COLOR_BGR2HSV).astype("float32")
    hsv[:, :, 1] *= 1.25 
    hsv[:, :, 1] = np.clip(hsv[:, :, 1], 0, 255)
    return cv2.cvtColor(hsv.astype("uint8"), cv2.COLOR_HSV2BGR)

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="UTF-8">
    <title>YT do Foto HDR v2</title>
    <style>
        body { font-family: -apple-system, sans-serif; background: #0f0f0f; color: white; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; }
        .card { background: #1a1a1a; padding: 40px; border-radius: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.5); width: 100%; max-width: 450px; text-align: center; }
        h1 { color: #ff0000; font-size: 24px; margin-bottom: 10px; }
        input { width: 100%; padding: 15px; border-radius: 10px; border: 1px solid #333; background: #000; color: white; margin: 20px 0; box-sizing: border-box; }
        button { background: #ff0000; color: white; border: none; padding: 15px 30px; border-radius: 10px; cursor: pointer; font-weight: bold; width: 100%; font-size: 16px; }
        button:disabled { background: #444; }
        #log { margin-top: 20px; font-size: 12px; color: #aaa; text-align: left; max-height: 100px; overflow-y: auto; }
    </style>
</head>
<body>
    <div class="card">
        <h1>YT Smart Frames</h1>
        <p>30 ostrych kadrów z obróbką HDR</p>
        <input type="text" id="url" placeholder="Wklej link YouTube...">
        <button id="btn" onclick="process()">GENERUJ ZDJĘCIA</button>
        <div id="log"></div>
    </div>
    <script>
        function process() {
            const url = document.getElementById('url').value;
            if(!url) return alert("Wklej link!");
            document.getElementById('btn').disabled = true;
            document.getElementById('log').innerHTML = "Łączenie z YT... Proces może zająć 1-2 minuty.";
            window.location.href = "/generate?url=" + encodeURIComponent(url);
            setTimeout(() => {
                document.getElementById('btn').disabled = false;
                document.getElementById('log').innerHTML = "Pobieranie powinno się rozpocząć.";
            }, 5000);
        }
    </script>
</body>
</html>
'''

@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)

@app.route('/generate')
def generate():
    video_url_raw = request.args.get('url')
    count = 30
    
    # Pobieramy tylko stream 720p dla stabilności na darmowym serwerze
    ydl_opts = {'format': 'bestvideo[height<=720][ext=mp4]', 'quiet': True}
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url_raw, download=False)
            video_stream_url = info['url']
        
        cap = cv2.VideoCapture(video_stream_url)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total_frames <= 0: raise ValueError("Błąd strumienia")
        
        step = total_frames // (count + 1)
        zip_buffer = BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'a', zipfile.ZIP_DEFLATED) as zip_file:
            for i in range(count):
                target_pos = (i + 1) * step
                
                # Inteligentna selekcja: sprawdź 3 klatki i wybierz najostrzejszą
                best_frame = None
                max_sharpness = -1
                
                for offset in [0, 5, 10]: # Sprawdzamy klatkę bazową i dwie kolejne
                    cap.set(cv2.CAP_PROP_POS_FRAMES, target_pos + offset)
                    ret, frame = cap.read()
                    if ret:
                        sharpness = get_sharpness(frame)
                        if sharpness > max_sharpness:
                            max_sharpness = sharpness
                            best_frame = frame
                
                if best_frame is not None:
                    processed = apply_hdr_effect(best_frame)
                    _, buffer = cv2.imencode(".jpg", processed, [cv2.IMWRITE_JPEG_QUALITY, 85])
                    zip_file.writestr(f"foto_{i+1}.jpg", buffer.tobytes())
        
        cap.release()
        zip_buffer.seek(0)
        return send_file(zip_buffer, mimetype='application/zip', as_attachment=True, download_name='yt_hdr_frames.zip')
    
    except Exception as e:
        return f"Błąd: {str(e)}", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
