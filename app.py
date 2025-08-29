"""
Servicio Flask para generar audio OGG con Gemini y convertirlo para WhatsApp.
Compatible con WhatsApp Business API (mimeType: audio/ogg).
"""

import os
import asyncio
import base64
import logging
from io import BytesIO

from flask import Flask, request, jsonify
from flask_cors import CORS
from google import genai
from google.genai import types
from pydub import AudioSegment

# ===========================
# Configuración básica
# ===========================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Tu API Key (directamente incluida)
API_KEY = "AIzaSyC3895F5JKZSHKng1IVL_3DywImp4lwVyI"
MODEL = "models/gemini-2.5-flash-exp-native-audio-thinking-dialog"
PORT = int(os.getenv("PORT", 5000))

# Cliente Gemini (v1beta para audio nativo)
client = genai.Client(
    http_options=types.HttpOptions(api_version="v1beta"),
    api_key=API_KEY
)

# Configuración de audio: salida en PCM (LINEAR16)
CONFIG = types.LiveConnectConfig(
    response_modalities=["AUDIO"],
    speech_config=types.SpeechConfig(
        voice_config=types.VoiceConfig(
            prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Zephyr")
        ),
        output_audio_config=types.OutputAudioConfig(
            audio_encoding="LINEAR16"  # PCM 16-bit
        )
    )
)

# ===========================
# Función: Convertir PCM → OGG
# ===========================
def pcm_to_ogg(pcm_data: bytes) -> bytes | None:
    """
    Convierte audio PCM raw a formato OGG (Opus), compatible con WhatsApp.
    """
    try:
        audio = AudioSegment(
            data=pcm_data,
            sample_width=2,      # 16-bit
            frame_rate=16000,    # 16kHz
            channels=1           # Mono
        )
        ogg_buffer = BytesIO()
        audio.export(ogg_buffer, format="ogg", codec="libopus")
        return ogg_buffer.getvalue()
    except Exception as e:
        logger.error(f"Error al convertir PCM → OGG: {e}")
        return None

# ===========================
# Generar audio con Gemini
# ===========================
async def generate_speech(text: str) -> bytes | None:
    """
    Genera audio PCM usando Gemini Live API.
    """
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
CORS(app)  # Permitir solicitudes desde frontend

@app.route('/chat', methods=['POST'])
def chat():
    """
    Recibe texto → genera audio → convierte a OGG → devuelve Base64.
    Formato compatible con WhatsApp: audio/ogg
    """
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

        # Convertir a OGG
        ogg_audio = pcm_to_ogg(pcm_audio)
        if not ogg_audio:
            return jsonify({'error': 'Error al convertir a OGG'}), 500

        # Codificar en Base64
        audio_base64 = base64.b64encode(ogg_audio).decode('utf-8')
        logger.info(f"Audio OGG generado: {len(audio_base64)} caracteres")

        # ✅ Respuesta compatible con WhatsApp
        return jsonify({
            'candidates': [{
                'content': {
                    'role': 'model',
                    'parts': [{
                        'inlineData': {
                            'mimeType': 'audio/ogg',
                            'data': audio_base64
                        }
                    }]
                }
            }]
        })

    except Exception as e:
        logger.exception("Error inesperado en /chat")
        return jsonify({'error': 'Error interno del servidor'}), 500


@app.route('/health', methods=['GET'])
def health():
    """Endpoint de salud"""
    return jsonify({
        'status': 'ok',
        'service': 'Gemini Audio para WhatsApp',
        'format': 'audio/ogg',
        'version': '1.0.0'
    })


# ===========================
# Inicio del Servidor
# ===========================
if __name__ == '__main__':
    logger.info(f"🚀 Iniciando servidor en puerto {PORT}...")
    logger.info("💡 Asegúrate de tener 'ffmpeg' instalado.")
    app.run(host='0.0.0.0', port=PORT, debug=False)
