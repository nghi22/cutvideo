import os
import time
import zipfile
import subprocess
from flask import Flask, render_template, request, send_file, url_for, redirect
from werkzeug.utils import secure_filename
from pydub import AudioSegment

app = Flask(__name__)

# ===== Đường dẫn tuyệt đối (chắc chắn KHÔNG nhầm folder) =====
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
RESULT_FOLDER = os.path.join(BASE_DIR, 'results')

ALLOWED_AUDIO = {'mp3', 'wav', 'ogg', 'flac'}
ALLOWED_VIDEO = {'mp4', 'avi', 'mov', 'mkv'}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULT_FOLDER, exist_ok=True)

def allowed_file(filename, allowed_ext):
    return '.' in filename and filename.rsplit('.', 1)[-1].lower() in allowed_ext

def get_duration_str(seconds):
    m, s = divmod(int(seconds), 60)
    return f"{m:02d}:{s:02d}"

# --- Video Helper: duration & cut ---
def get_video_duration(input_path):
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of',
             'default=noprint_wrappers=1:nokey=1', input_path],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        )
        return float(result.stdout.strip())
    except Exception:
        return 0

def cut_video(input_path, output_path, start, end):
    cmd = [
        'ffmpeg', '-y', '-i', input_path,
        '-ss', str(start), '-to', str(end),
        '-c:v', 'libx264', '-c:a', 'aac', '-preset', 'ultrafast', output_path
    ]
    print('[FFMPEG]', ' '.join(cmd))
    completed = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    print(completed.stdout)
    print("[DEBUG] Output file exists?", os.path.exists(output_path))

# ========== Trang chủ: Ghép âm thanh ==========
@app.route('/', methods=['GET', 'POST'])
def index():
    file_infos = []
    merged_file = merged_duration = merged_url = output_name = None
    error = None
    if request.method == 'POST':
        files = request.files.getlist('files')
        output_name = request.form.get('output_name', '').strip()
        audio_segments = []
        filenames = []
        for file in files:
            if file and allowed_file(file.filename, ALLOWED_AUDIO):
                filename = secure_filename(file.filename)
                path = os.path.join(UPLOAD_FOLDER, filename)
                file.save(path)
                audio = AudioSegment.from_file(path)
                audio_segments.append(audio)
                filenames.append(filename)
                file_infos.append({
                    "name": filename,
                    "duration": get_duration_str(audio.duration_seconds),
                    "path": path
                })
        if len(audio_segments) < 2:
            error = "Bạn cần chọn ít nhất 2 file!"
            return render_template('index.html', error=error, file_infos=file_infos, output_name=output_name)
        merged = audio_segments[0]
        for audio in audio_segments[1:]:
            merged += audio
        ext = filenames[0].rsplit('.', 1)[-1].lower()
        if ext not in ALLOWED_AUDIO:
            ext = 'mp3'
        base_name = output_name if output_name else "audio_merged"
        save_name = f"{base_name}.{ext}"
        out_file = os.path.join(UPLOAD_FOLDER, save_name)
        if ext == 'mp3':
            merged.export(out_file, format=ext, bitrate="320k")
        else:
            merged.export(out_file, format=ext)
        merged_duration = get_duration_str(merged.duration_seconds)
        merged_file = save_name
        merged_url = url_for('download', filename=save_name)
        return render_template('index.html',
                              merged_file=merged_file,
                              merged_duration=merged_duration,
                              merged_url=merged_url)
    return render_template('index.html')

@app.route('/download/<filename>')
def download(filename):
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    return send_file(file_path, as_attachment=True)

# ========== Đếm ký tự ==========
@app.route('/charcount', methods=['GET', 'POST'])
def charcount():
    text = ""
    count = 0
    count_type = "chars"
    if request.method == 'POST':
        text = request.form.get('input_text', '')
        count_type = request.form.get('count_type', 'chars')
        if count_type == 'chars':
            count = len(text)
        else:
            count = len([w for w in text.replace('\n',' ').split(' ') if w.strip()])
    return render_template('charcount.html', text=text, count=count, count_type=count_type)

# ========== Chuyển HOA/thường ==========
@app.route('/caseconvert', methods=['GET', 'POST'])
def caseconvert():
    text = ""
    result = ""
    mode = "upper"
    if request.method == 'POST':
        text = request.form.get('input_text', '')
        mode = request.form.get('convert_mode', 'upper')
        if mode == 'upper':
            result = text.upper()
        else:
            result = text.lower()
    return render_template('caseconvert.html', text=text, result=result, mode=mode)

# ========== Cắt video (ffmpeg subprocess) ==========
@app.route('/cutvideo', methods=['GET', 'POST'])
def cutvideo():
    videos_info = []
    result_files = []
    skipped_files = []
    zip_url = None
    progress_msg = None

    if request.method == 'POST':
        cut_mode = request.form.get('cut_mode')
        files = request.files.getlist('videos')
        try:
            if cut_mode == 'start':
                duration = int(request.form.get('duration', 10))
            elif cut_mode == 'middle':
                from_sec = int(request.form.get('from_sec', 0))
                to_sec = int(request.form.get('to_sec', 10))
            elif cut_mode == 'end':
                tail_sec = int(request.form.get('tail_sec', 10))
        except Exception:
            progress_msg = "Có lỗi khi đọc tham số vùng cắt!"
            return render_template('cutvideo.html', progress_msg=progress_msg)

        for f in files:
            if f and allowed_file(f.filename, ALLOWED_VIDEO):
                filename = secure_filename(f.filename)
                in_path = os.path.join(UPLOAD_FOLDER, f"{int(time.time())}_{filename}")
                f.save(in_path)
                try:
                    duration_orig = get_video_duration(in_path)
                    videos_info.append({'name': filename, 'duration': round(duration_orig, 2)})
                    # Cắt video
                    if cut_mode == 'start':
                        end = min(duration, duration_orig)
                        if duration_orig <= duration:
                            result_name = filename
                            out_path = in_path
                            skipped_files.append(filename)
                        else:
                            result_name = f"{os.path.splitext(filename)[0]}_{duration}s.mp4"
                            out_path = os.path.join(RESULT_FOLDER, result_name)
                            cut_video(in_path, out_path, 0, end)
                    elif cut_mode == 'middle':
                        start = max(0, from_sec)
                        end = min(to_sec, duration_orig)
                        if start >= end or start >= duration_orig:
                            skipped_files.append(filename)
                            continue
                        result_name = f"{os.path.splitext(filename)[0]}_{start}-{end}s.mp4"
                        out_path = os.path.join(RESULT_FOLDER, result_name)
                        cut_video(in_path, out_path, start, end)
                    elif cut_mode == 'end':
                        sec = min(tail_sec, duration_orig)
                        if duration_orig <= tail_sec:
                            result_name = filename
                            out_path = in_path
                            skipped_files.append(filename)
                        else:
                            start = duration_orig - tail_sec
                            end = duration_orig
                            result_name = f"{os.path.splitext(filename)[0]}_cuoi{tail_sec}s.mp4"
                            out_path = os.path.join(RESULT_FOLDER, result_name)
                            cut_video(in_path, out_path, start, end)
                    result_files.append({
                        'display': result_name,
                        'path': out_path
                    })
                except Exception as e:
                    progress_msg = f"Lỗi khi xử lý video {filename}: {e}"
                # Xoá file upload tạm (chỉ giữ file cắt ra)
                if os.path.exists(in_path) and (not (out_path == in_path)):
                    try: os.remove(in_path)
                    except: pass

        # Nếu có nhiều file, nén zip để tải tất cả
        if len(result_files) > 1:
            zipname = f"videos_cut_{int(time.time())}.zip"
            zippath = os.path.join(RESULT_FOLDER, zipname)
            with zipfile.ZipFile(zippath, 'w') as zf:
                for f in result_files:
                    if os.path.exists(f['path']):
                        zf.write(f['path'], arcname=os.path.basename(f['path']))
            zip_url = url_for('download_result', filename=zipname)

        return render_template('cutvideo.html',
            videos_info=videos_info,
            result_files=result_files,
            skipped_files=skipped_files,
            zip_url=zip_url,
            progress_msg=progress_msg
        )

    return render_template('cutvideo.html')

@app.route('/download_result/<filename>')
def download_result(filename):
    file_path = os.path.join(RESULT_FOLDER, filename)
    print("[DEBUG] download file:", file_path, "| EXIST:", os.path.exists(file_path))
    return send_file(file_path, as_attachment=True)

if __name__ == "__main__":
    print("[DEBUG] BASE_DIR:", BASE_DIR)
    print("[DEBUG] UPLOAD_FOLDER:", UPLOAD_FOLDER)
    print("[DEBUG] RESULT_FOLDER:", RESULT_FOLDER)
    app.run(debug=True)
