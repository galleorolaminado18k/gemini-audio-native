"""
Servicio Flask para generar audios MP3 con Gemini y subirlos a GCS.
Compatible con WhatsApp Business API (formato audio/mp3).
"""

import os
import asyncio
import base64
import logging
from io import BytesIO
from typing import Optional

from flask import Flask, request, jsonify
from flask_cors import CORS
from google import genai
from google.genai import types
from pydub import AudioSegment
from google.cloud import storage

# ===========================
# Configuración de Logging
# ===========================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ===========================
# Variables de Entorno
# ===========================
API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyC3895F5JKZSHKng1IVL_3DywImp4lwVyI")
MODEL = "models/gemini-2.5-flash-exp-native-audio-thinking-dialog"
PORT = int(os.getenv("PORT", 5000))

# Validar clave API
if not API_KEY or "YOUR_API_KEY" in API_KEY:
    raise ValueError("API Key de Gemini no configurada correctamente.")

# Cliente Gemini (v1beta para audio nativo)
client = genai.Client(
    http_options=types.HttpOptions(api_version="v1beta"),
    api_key=API_KEY
)

# Configuración de audio: PCM → MP3
CONFIG = types.LiveConnectConfig(
    response_modalities=["AUDIO"],
    speech_config=types.SpeechConfig(
        voice_config=types.VoiceConfig(
            prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Zephyr")
        ),
        output_audio_config=types.OutputAudioConfig(
            audio_encoding="LINEAR16"  # LINEAR16 = PCM 16-bit
        )
    )
)

# ===========================
# Google Cloud Storage
# ===========================
GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME", "gemini-audio-bucket")

def upload_to_gcs(mp3_data: bytes, filename: str) -> str:
    """Sube archivo MP3 a Google Cloud Storage y devuelve URL pública."""
    try:
        client = storage.Client()
        bucket = client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(filename)
        blob.upload_from_string(mp3_data, content_type="audio/mp3")
        blob.make_public()  # Hacer público
        return blob.public_url
    except Exception as e:
        logger.error(f"Error al subir a GCS: {e}")
        return ""

# ===========================
# Funciones de Audio
# ===========================
def pcm_to_mp3_buffer(pcm_data: bytes, frame_rate: int = 16000) -> Optional[BytesIO]:
    """Convierte PCM raw a MP3."""
    try:
        audio = AudioSegment(
            data=pcm_data,
            sample_width=2,
            frame_rate=frame_rate,
            channels=1
        )
        buffer = BytesIO()
        audio.export(buffer, format="mp3", bitrate="64k")
        buffer.seek(0)
        return buffer
    except Exception as e:
        logger.error(f"Error en conversión PCM → MP3: {e}")
        return None

async def generate_speech(text: str) -> Optional[bytes]:
    """Genera audio PCM usando Gemini Live API."""
    try:
        logger.info(f"Generando audio para: {text[:50]}...")
        async with client.aio.live.connect(model=MODEL, config=CONFIG) as session:
            await session.send(input=text, end_of_turn=True)
            chunks = []
            async for response in session.receive():
                if hasattr(response, 'data') and response.data:
                    chunks.append(response.data)
                    logger.debug(f"Chunk recibido: {len(response.data)} bytes")
            return b''.join(chunks) if chunks else None
    except Exception as e:
        logger.error(f"Error en Gemini API: {e}")
        return None

# ===========================
# Servicio Flask
# ===========================
app = Flask(__name__)
CORS(app)

@app.route('/chat', methods=['POST'])
def chat():
    """Recibe texto → genera audio MP3 → sube a GCS → devuelve URL pública."""
    logger.info("=== NUEVA SOLICITUD DE AUDIO ===")

    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'JSON inválido'}), 400

        user_text = data.get('text', '').strip()
        if not user_text:
            return jsonify({'error': 'Campo "text" es requerido'}), 400

        logger.info(f"Texto recibido: '{user_text}'")

        # Generar audio PCM
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        pcm_audio = loop.run_until_complete(generate_speech(user_text))
        loop.close()

        if not pcm_audio:
            logger.error("No se generó audio con Gemini.")
            return jsonify({'error': 'No se pudo generar el audio'}), 500

        # Convertir a MP3
        mp3_buffer = pcm_to_mp3_buffer(pcm_audio)
        if not mp3_buffer:
            return jsonify({'error': 'Error al convertir audio'}), 500

        # Nombre único del archivo
        filename = f"{int(datetime.now().timestamp())}_{uuid.uuid4().hex}.mp3"

        # Subir a GCS
        audio_url = upload_to_gcs(mp3_buffer.read(), filename)
        if not audio_url:
            return jsonify({'error': 'Error al subir audio a GCS'}), 500

        logger.info(f"Audio subido: {audio_url}")

        # ✅ RESPUESTA PARA WHATSAPP
        return jsonify({
            "audio_url": audio_url,
            "mimeType": "audio/mp3",
            "size": len(mp3_buffer.getvalue())
        })

    except Exception as e:
        logger.exception("Error inesperado")
        return jsonify({'error': 'Error interno del servidor'}), 500


@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'ok',
        'service': 'Gemini Audio para WhatsApp',
        'model': MODEL,
        'format': 'audio/mp3',
        'version': '1.0.0'
    })


# ===========================
# Inicio del Servidor
# ===========================
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT, debug=False)
