import os, socket, secrets, time
from io import BytesIO
from flask import Flask, request, render_template_string, abort
import qrcode
import pyperclip
from PIL import Image
import win32clipboard
from werkzeug.utils import secure_filename

PORT = 8010
PIN = "1234"
TOKEN = secrets.token_hex(4)
INBOX = os.path.join(os.getcwd(), "beam_inbox")
os.makedirs(INBOX, exist_ok=True)

app = Flask(__name__)

IOS_UI = """
<!doctype html>
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
<title>N-Drop</title>
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; background: #0d1117; color: #f0f6fc; padding: 18px; margin: 0; }
  .card { background: #161b22; border: 1px solid #30363d; border-radius: 14px; padding: 16px; margin-bottom: 14px; }
  h2 { margin: 0 0 10px 0; font-size: 17px; color: #58a6ff; }
  textarea, input[type=file] { width: 100%; box-sizing: border-box; background: #0d1117; color: #fff; border: 1px solid #30363d; border-radius: 8px; padding: 10px; margin-bottom: 10px; font-size: 15px; }
  button { width: 100%; background: #238636; color: #fff; border: none; padding: 12px; border-radius: 8px; font-size: 15px; font-weight: 600; cursor: pointer; }
  .pc-clip { font-family: monospace; background: #0d1117; padding: 10px; border-radius: 8px; word-break: break-all; font-size: 13px; border: 1px solid #30363d; margin-bottom: 10px; }
</style>
<div class="card">
  <h2>📁 Beam File, Photo, or PDF → Windows</h2>
  <form action="/beam?key={{ key }}" method="post" enctype="multipart/form-data">
    <input type="file" name="file" required>
    <button type="submit">Beam to PC</button>
  </form>
</div>
<div class="card">
  <h2>📝 Beam Text → Windows Ctrl+V</h2>
  <form action="/beam?key={{ key }}" method="post">
    <textarea name="text" rows="3" placeholder="Paste text or code..."></textarea>
    <button type="submit">Inject Text into PC Clipboard</button>
  </form>
</div>
<div class="card">
  <h2>💻 Live Windows Clipboard (PC → iPhone)</h2>
  <div class="pc-clip" id="pcClip">{{ pc_clip }}</div>
  <button onclick="navigator.clipboard.writeText(document.getElementById('pcClip').innerText)">Copy PC Text to iPhone</button>
</div>
"""

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()

def copy_image_to_windows_clipboard(img_bytes):
    image = Image.open(BytesIO(img_bytes))
    output = BytesIO()
    image.convert("RGB").save(output, "BMP")
    dib_data = output.getvalue()[14:]
    output.close()
    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32clipboard.CF_DIB, dib_data)
    finally:
        win32clipboard.CloseClipboard()

def verify():
    key = request.args.get("key")
    if key not in (TOKEN, PIN):
        abort(403)
    return key

@app.route("/")
def index():
    key = verify()
    try:
        pc_clip = pyperclip.paste() or "(Windows clipboard is empty or holds an image)"
    except Exception:
        pc_clip = "(Clipboard unavailable)"
    return render_template_string(IOS_UI, key=key, pc_clip=pc_clip)

@app.route("/pull", methods=["GET"])
def pull_from_pc():
    verify()
    return pyperclip.paste() or ""

@app.route("/beam", methods=["POST"])
def beam():
    key = verify()
    if "file" in request.files and request.files["file"].filename:
        f = request.files["file"]
        raw_bytes = f.read()
        filename = secure_filename(f.filename) or f"file_{int(time.time())}.bin"
        filepath = os.path.join(INBOX, filename)
        with open(filepath, "wb") as out:
            out.write(raw_bytes)

        ext = os.path.splitext(filename)[1].lower()
        if ext in [".png", ".jpg", ".jpeg", ".heic", ".webp"]:
            try:
                copy_image_to_windows_clipboard(raw_bytes)
                print(f"\n[📸 PHOTO BEAMED] '{filename}' saved & loaded into Windows Ctrl+V!")
                return f"Photo copied to Windows Ctrl+V & saved! <a href='/?key={key}'>Back</a>"
            except Exception as e:
                print(f"\n[⚠️ IMAGE ERROR] Saved file, but clipboard load failed: {e}")

        print(f"\n[📁 FILE/PDF BEAMED] '{filename}' saved to beam_inbox/")
        return f"File/PDF saved to beam_inbox! <a href='/?key={key}'>Back</a>"

    text = request.form.get("text", "")
    if text:
        pyperclip.copy(text)
        print(f"\n[📝 TEXT BEAMED] {len(text)} chars -> Hit Ctrl+V on Windows!")
        return f"Text copied to Windows Ctrl+V! <a href='/?key={key}'>Back</a>"

    return "Nothing received", 400

if __name__ == "__main__":
    ip = get_local_ip()
    url = f"http://{ip}:{PORT}/?key={PIN}"
    print(f"\n⚡ N-DROP ACTIVE | Inbox: {INBOX}")
    print(f"📲 Endpoint: http://{ip}:{PORT}/beam?key={PIN}\n")
    qr = qrcode.QRCode(border=1)
    qr.add_data(url)
    qr.make(fit=True)
    qr.print_ascii(invert=True)
    app.run(host="0.0.0.0", port=PORT, debug=False)