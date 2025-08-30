import os
import json
import base64
from uuid import uuid4
from io import BytesIO

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from google import genai  # sdk google-genai
import gspread
from google.oauth2.service_account import Credentials

app = Flask(__name__)
CORS(app)

# -----------------------------
# Gemini API
# -----------------------------
API_KEY = os.getenv("GOOGLE_API_KEY", "TU_API_KEY_AQUI")
client = genai.Client(api_key=API_KEY)

# -----------------------------
# Google Sheets
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
    sheet = gc.open_by_key(SPREADSHEET_ID).sheet1
    gs_ready = True
    print("✅ Google Sheets listo")
except Exception as e:
    print(f"⚠ Google Sheets deshabilitado: {e}")

# -----------------------------
# Cache de audio
# -----------------------------
audio_cache = {}

def _public_base_url() -> str:
    env_url = os.getenv("PUBLIC_BASE_URL")
    if env_url:
        return env_url.rstrip("/")
    return (request.host_url or "").rstrip("/")


@app.route("/chat", methods=["POST"])
def chat():
    try:
        if not request.is_json:
            return jsonify({'error': 'Content-Type debe ser application/json'}), 400

        data = request.get_json(silent=True) or {}
        user_text = (data.get("text") or "").strip()
        if not user_text:
            return jsonify({"error": "Campo text requerido"}), 400

        print(f"Texto recibido: {user_text}")

        # 1️⃣ Generar respuesta de texto con Gemini normal
        response_text = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=user_text
        )
        generated_text = getattr(response_text, "text", "") or ""
        print(f"Respuesta generada (texto): {generated_text}")

        # 2️⃣ Generar respuesta en AUDIO con Gemini TTS
        response_audio = client.models.generate_content(
            model="gemini-2.5-flash-preview-tts",
            contents=generated_text,
            config={
                "response_modalities": ["AUDIO"],
                "speech_config": {
                    "voice_config": {"language_code": "es-ES"}
                }
            }
        )

        audio_data = None
        for c in response_audio.candidates:
            for p in c.content.parts:
                if hasattr(p, "inline_data"):
                    audio_data = base64.b64decode(p.inline_data.data)

        if not audio_data:
            return jsonify({"error": "No se generó audio"}), 500

        audio_base64 = base64.b64encode(audio_data).decode("utf-8")

        # 3️⃣ Guardar fila en Google Sheets
        if gs_ready and sheet is not None:
            try:
                sheet.append_row([user_text, generated_text, audio_base64])
            except Exception as e_sheet:
                print(f"⚠ No se pudo escribir en Sheets: {e_sheet}")

        # 4️⃣ Guardar audio en cache y construir URL pública
        audio_id = str(uuid4())
        audio_cache[audio_id] = audio_data
        audio_url = f"{_public_base_url()}/audio/{audio_id}.ogg"

        # 5️⃣ Respuesta JSON completa
        return jsonify({
            "text_response": generated_text,
            "audio_base64": audio_base64,
            "audio_url": audio_url,
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
        "version": "gemini-text+tts"
    }), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
