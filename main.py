import os
import json
import base64
from uuid import uuid4
from io import BytesIO

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS

from google import genai
from google.genai import types  # para TTS config

import gspread
from google.oauth2.service_account import Credentials

app = Flask(__name__)
CORS(app)

# -----------------------------
# Gemini API con API KEY fija
# -----------------------------
API_KEY = "AIzaSyDf9n-nERTfTC3G4WRf7msqQP1gjZkZST0"
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
    print("⚠ Google Sheets deshabilitado:", e)

# -----------------------------
# Cache de audios
# -----------------------------
audio_cache = {}

def _public_base_url():
    env = os.getenv("PUBLIC_BASE_URL")
    return env.rstrip("/") if env else (request.host_url or "").rstrip("/")

# -----------------------------
# Endpoint principal /chat
# -----------------------------
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

        # 1️⃣ Generar texto con Gemini Flash
        response_text = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=user_text
        )
        generated_text = getattr(response_text, "text", "") or "(sin respuesta)"
        print(f"Respuesta generada: {generated_text}")

        # 2️⃣ Generar audio con Gemini TTS
        response_audio = client.models.generate_content(
            model="gemini-2.5-flash-preview-tts",
            contents=generated_text,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name="charon"  # puedes cambiar por "zephyr", "kore", etc.
                        )
                    )
                )
            )
        )

        # Extraer audio base64
        audio_base64 = response_audio.candidates[0].content.parts[0].inline_data.data
        audio_bytes = base64.b64decode(audio_base64)

        # 3️⃣ Guardar en Google Sheets
        if gs_ready and sheet:
            try:
                sheet.append_row([user_text, generated_text, f"{_public_base_url()}/audio/temp.ogg"])
            except Exception as e_sheet:
                print("⚠ No se pudo guardar en Sheets:", e_sheet)

        # 4️⃣ Guardar en caché para URL pública
        audio_id = str(uuid4())
        audio_cache[audio_id] = audio_bytes
        audio_url = f"{_public_base_url()}/audio/{audio_id}.ogg"

        # 5️⃣ Respuesta JSON para Builderbot / WhatsApp
        return jsonify({
            "reply": generated_text,
            "audio_url": audio_url,
            "audio_base64": audio_base64
        }), 200

    except Exception as e:
        print("❌ Error en /chat:", e)
        return jsonify({"error": str(e)}), 500

# -----------------------------
# Endpoint para servir audios
# -----------------------------
@app.route("/audio/<audio_id>.ogg")
def get_audio(audio_id):
    data = audio_cache.get(audio_id)
    if not data:
        return "Audio expirado o no encontrado", 404
    return send_file(BytesIO(data), mimetype="audio/ogg")

# -----------------------------
# Health check
# -----------------------------
@app.route("/health")
def health():
    return jsonify({"status": "ok", "version": "gemini-tts"}), 200

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
