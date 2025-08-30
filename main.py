import os
import json
import base64
import asyncio
import websockets
from uuid import uuid4
from io import BytesIO

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# -----------------------------
# Configuración Gemini Live API
# -----------------------------
API_KEY = os.getenv("GOOGLE_API_KEY", "TU_API_KEY_AQUI")
GEMINI_WS = "wss://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-exp-native-audio-thinking-dialog:generateContent?key=" + API_KEY

# Cache en memoria para audios
audio_cache = {}  # {audio_id: bytes}


async def get_audio_from_gemini(user_text: str) -> bytes:
    """
    Abre un WebSocket con Gemini Live API y recibe audio OGG generado por el modelo nativo
    """
    async with websockets.connect(GEMINI_WS, ping_interval=None) as ws:
        # 1. Enviar prompt de usuario
        await ws.send(json.dumps({
            "contents": [{"role": "user", "parts": [{"text": user_text}]}],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "audioConfig": {
                    "audioEncoding": "AUDIO_ENCODING_OGG_OPUS"
                }
            }
        }))

        audio_chunks = []
        # 2. Escuchar respuestas
        async for message in ws:
            msg = json.loads(message)

            if "candidates" in msg:
                for cand in msg["candidates"]:
                    for part in cand["content"]["parts"]:
                        if "inlineData" in part:
                            data_b64 = part["inlineData"]["data"]
                            audio_chunks.append(base64.b64decode(data_b64))

            # fin de respuesta
            if msg.get("serverContent") == "DONE":
                break

        return b"".join(audio_chunks)


@app.route("/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json(force=True)
        user_text = (data.get("text") or "").strip()
        if not user_text:
            return jsonify({"error": "Campo text requerido"}), 400

        print(f"Texto recibido: {user_text}")

        # Ejecutar el WebSocket en un bucle asyncio
        audio_bytes = asyncio.run(get_audio_from_gemini(user_text))

        # Guardar en cache y generar URL
        audio_id = str(uuid4())
        audio_cache[audio_id] = audio_bytes
        audio_url = f"{request.host_url.rstrip('/')}/audio/{audio_id}.ogg"

        audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")

        return jsonify({
            "audio_url": audio_url,
            "audio_base64": audio_base64,
            "text_response": f"[Gemini respondió con audio para: {user_text}]"
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
    return jsonify({"status": "ok", "version": "gemini-audio-native"}), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
