import os
import json
import base64
from uuid import uuid4
from io import BytesIO

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from google import genai  # usa google-genai
import gspread
from google.oauth2.service_account import Credentials

app = Flask(__name__)
CORS(app)

# -----------------------------
# Gemini API (usa tu API key)
# -----------------------------
API_KEY = os.getenv("GOOGLE_API_KEY", "AIzaSyC3895F5JKZSHKng1IVL_3DywImp4lwVyI")
client = genai.Client(api_key=API_KEY)

# -----------------------------
# Google Sheets (seguro)
#   - Primero intenta GOOGLE_CREDENTIALS (JSON completo en env var)
#   - Si no hay, usa credenciales.json (para local)
#   - Apunta a sheet1 o a SHEET_TITLE si lo defines en env
# -----------------------------
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SPREADSHEET_ID = "1GD_HKVDQLQgYX_XaOkyVpI9RBSAgkRNPVnWC3KaY5P0"

gs_ready = False
sheet = None
try:
    creds_json = os.getenv("GOOGLE_CREDENTIALS")
    if creds_json:
        info = json.loads(creds_json)
        creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    else:
        creds = Credentials.from_service_account_file("credenciales.json", scopes=SCOPES)

    gc = gspread.authorize(creds)
    ss = gc.open_by_key(SPREADSHEET_ID)
    sheet_title = os.getenv("SHEET_TITLE")  # opcional, para apuntar a una pestaña específica
    sheet = ss.worksheet(sheet_title) if sheet_title else ss.sheet1
    gs_ready = True
    print("✅ Google Sheets listo")
except Exception as e:
    print(f"⚠️ Google Sheets deshabilitado: {e}")

# -----------------------------
# Helper: base pública del servicio (para construir audio_url)
# -----------------------------
def _public_base_url() -> str:
    env_url = os.getenv("PUBLIC_BASE_URL")
    if env_url:
        return env_url.rstrip("/")
    # Fallback en Cloud Run
    return (request.host_url or "").rstrip("/")

# -----------------------------
# Cache simple para servir audio por URL
# -----------------------------
audio_cache = {}  # {audio_id: bytes}

@app.route("/chat", methods=["POST"])
def chat():
    try:
        if not request.is_json:
            return jsonify({"error": "Content-Type debe ser application/json"}), 400

        data = request.get_json(silent=True) or {}
        user_text = (data.get("text") or "").strip()
        if not user_text:
            return jsonify({"error": "Campo text requerido"}), 400

        print(f"Texto recibido: {user_text}")

        # Generar texto con Gemini
        response = client.models.generate_content(
            model="gemini-2.0-flash-001",
            contents=user_text
        )
        generated_text = getattr(response, "text", "") or ""
        print(f"Respuesta generada: {generated_text}")

        # Simular audio base64 (mantengo tu lógica)
        audio_data = b"AUDIO:" + generated_text.encode("utf-8")[:500]
        audio_base64 = base64.b64encode(audio_data).decode("utf-8")

        # Guardar fila en Google Sheets (no romper si falla)
        if gs_ready and sheet is not None:
            try:
                sheet.append_row([user_text, generated_text, audio_base64])
            except Exception as e_sheet:
                print(f"⚠️ No se pudo escribir en Sheets: {e_sheet}")

        # Guardar audio en cache y construir URL pública
        try:
            audio_bytes = base64.b64decode(audio_base64)
        except Exception:
            audio_bytes = b""
        audio_id = str(uuid4())
        audio_cache[audio_id] = audio_bytes
        audio_url = f"{_public_base_url()}/audio/{audio_id}.ogg"

        # Respuesta: campos planos + estructura original
        return jsonify({
            "text_response": generated_text,   # texto plano
            "audio_base64": audio_base64,      # base64 directo
            "audio_url": audio_url,            # URL directa (sirve este servicio)

            "candidates": [{
                "content": {
                    "role": "model",
                    "parts": [{
                        "inlineData": {
                            "mimeType": "audio/ogg",
                            "data": audio_base64
                        }
                    }]
                }
            }]
        }), 200

    except Exception as e:
        print(f"❌ Error en /chat: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/audio/<audio_id>.ogg", methods=["GET"])
def get_audio(audio_id):
    data = audio_cache.get(audio_id)
    if not data:
        return "Audio expirado o no encontrado", 404
    return send_file(BytesIO(data), mimetype="audio/ogg", as_attachment=False, download_name=f"{audio_id}.ogg")

@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "sheets": "ready" if gs_ready else "disabled",
        "version": "no-live-api"
    }), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))  # Cloud Run
    app.run(host="0.0.0.0", port=port)
