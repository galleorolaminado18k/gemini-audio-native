"""
Servicio Flask para generar respuestas de voz en MP3 usando Gemini 2.5 Flash Exp.
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

# Configuración básica de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ===========================
# Configuración del Servicio
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

# Configuración de salida de audio: PCM 16-bit, 16kHz, mono
CONFIG = types.LiveConnectConfig(
    response_modalities=["AUDIO"],
    speech_config=types.SpeechConfig(
        voice_config=types.VoiceConfig(
            prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Zephyr")
        ),
        output_audio_config=types.OutputAudioConfig(
            audio_encoding="LINEAR16"  # Salida en PCM raw (16-bit, little-endian)
        )
    )
)

# ===========================
# Funciones de Audio
# ===========================

def pcm_to_mp3_buffer(pcm_data: bytes, frame_rate: int = 16000) -> Optional[bytes]:
    """
    Convierte audio PCM raw (16-bit, mono) a MP3.
    
    Args:
        pcm_data: Datos de audio en formato PCM (raw bytes)
        frame_rate: Frecuencia de muestreo (típicamente 16000 Hz)
    
    Returns:
        bytes: Audio codificado en MP3, o None si falla.
    """
    try:
        audio_segment = AudioSegment(
            data=pcm_data,
            sample_width=2,      # 16 bits = 2 bytes
            frame_rate=frame_rate,
            channels=1           # Mono
        )
        
        mp3_buffer = BytesIO()
        audio_segment.export(mp3_buffer, format="mp3", bitrate="64k", parameters=["-ac", "1"])
        return mp3_buffer.getvalue()
    
    except Exception as e:
        logger.error(f"Error en conversión PCM → MP3: {e}")
        return None


async def generate_speech(text: str) -> Optional[bytes]:
    """
    Genera audio de voz usando Gemini Live API.
    
    Args:
        text: Texto a convertir en voz.
    
    Returns:
        bytes: Audio PCM raw, o None si falla.
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
            
            if not chunks:
                logger.warning("No se recibieron datos de audio.")
                return None

            return b''.join(chunks)
    
    except Exception as e:
        logger.error(f"Error en Gemini Live API: {e}")
        return None


# ===========================
# Servicio Flask
# ===========================

app = Flask(__name__)
CORS(app)  # Permitir solicitudes desde frontend

@app.route('/chat', methods=['POST'])
def chat():
    """
    Endpoint principal:
    Recibe texto → genera voz MP3 → devuelve Base64 para WhatsApp.
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

        # Ejecutar en loop asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        # Generar audio PCM
        pcm_audio = loop.run_until_complete(generate_speech(user_text))
        if not pcm_audio:
            logger.error("No se pudo generar audio con Gemini.")
            return jsonify({'error': 'No se pudo generar el audio'}), 500

        # Convertir a MP3
        mp3_audio = pcm_to_mp3_buffer(pcm_audio)
        if not mp3_audio:
            logger.error("Fallo en conversión a MP3.")
            return jsonify({'error': 'Error interno al procesar audio'}), 500

        # Codificar en Base64
        audio_base64 = base64.b64encode(mp3_audio).decode('utf-8')
        logger.info(f"Audio MP3 generado: {len(audio_base64)} caracteres (Base64)")

        # Respuesta compatible con WhatsApp
        return jsonify({
            'candidates': [{
                'content': {
                    'role': 'model',
                    'parts': [{
                        'inlineData': {
                            'mimeType': 'audio/mp3',
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
    """Endpoint de salud del servicio."""
    return jsonify({
        'status': 'ok',
        'service': 'Gemini Audio to WhatsApp',
        'model': MODEL,
        'format': 'audio/mp3',
        'version': '1.0.0'
    })


# ===========================
# Inicio del Servidor
# ===========================

if __name__ == '__main__':
    logger.info(f"🚀 Iniciando servidor en puerto {PORT}...")
    logger.info("✅ Asegúrate de tener 'ffmpeg' instalado en el sistema.")
    logger.info("💡 Usa: pip install pydub y sudo apt install ffmpeg")
    
    app.run(host='0.0.0.0', port=PORT, debug=False)
