import os
import json
import base64
import asyncio
import websockets
from uuid import uuid4
from io import BytesIO

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import gspread
from google.oauth2.service_account import Credentials

app = Flask(__name__)
CORS(app)

# -----------------------------
# Configuración Gemini Live API
# -----------------------------
GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY", "TU_API_KEY_AQUI")
GEMINI_WS_URL = "wss://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-exp-native-audio-thinking-dialog:streamGenerateContent?key=" + GEMINI_API_KEY

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
    print(f"⚠️ Google Sheets deshabilitado: {e}")

# -----------------------------
# Cache de audios
# -----------------------------
audio_cache = {}

def _public_base_url() -> str:
    env_url = os.getenv("PUBLIC_BASE_URL")
    if env_url:
        return env_url.rstrip("/")
    return (request.host_url or "").rstrip("/")

# -----------------------------
# Función: hablar con Gemini WS
# -----------------------------
async def generate_audio_with_gemini(user_text: str):
    async with websockets.connect(GEMINI_WS_URL) as ws:
        # Enviar mensaje
        await ws.send(json.dumps({
            "contents": [{
                "role": "user",
                "parts": [{"text": user_text}]
            }]
        }))

        audio_bytes = b""
        generated_text = ""

        # Recibir respuesta
        async for message in ws:
            msg = json.loads(message)

            # Extraer texto
            if "candidates" in msg:
                for c in msg["candidates"]:
                    if "content" in c and "parts" in c["content"]:
                        for p in c["content"]["parts"]:
                            if "text" in p:
                                generated_text += p["text"]

            # Extraer audio inline
            if "candidates" in msg:
                for c in msg["candidates"]:
                    if "content" in c and "parts" in c["content"]:
                        for p in c["content"]["parts"]:
                            if "inlineData" in p:
                                audio_chunk = base64.b64decode(p["inlineData"]["data"])
                                audio_bytes += audio_chunk

        return generated_text, audio_bytes


# -----------------------------
# Endpoint /chat
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

        # Llamar Gemini en modo async
        generated_text, audio_bytes = asyncio.run(generate_audio_with_gemini(user_text))

        print(f"Respuesta generada: {generated_text}")

        # Codificar audio en base64
        audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")

        # Guardar fila en Google Sheets
        if gs_ready and sheet is not None:
            try:
                sheet.append_row([user_text, generated_text, audio_base64])
            except Exception as e_sheet:
                print(f"⚠️ No se pudo escribir en Sheets: {e_sheet}")

        # Guardar en cache y URL
        audio_id = str(uuid4())
        audio_cache[audio_id] = audio_bytes
        audio_url = f"{_public_base_url()}/audio/{audio_id}.ogg"

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


# -----------------------------
# Endpoint /audio/<id>
# -----------------------------
@app.route("/audio/<audio_id>.ogg", methods=["GET"])
def get_audio(audio_id):
    data = audio_cache.get(audio_id)
    if not data:
        return "Audio expirado o no encontrado", 404
    return send_file(BytesIO(data), mimetype="audio/ogg", as_attachment=False, download_name=f"{audio_id}.ogg")


# -----------------------------
# Endpoint /health
# -----------------------------
@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "sheets": "ready" if gs_ready else "disabled",
        "version": "gemini-native-audio"
    }), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
