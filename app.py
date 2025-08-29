import os
import asyncio
import base64
import io
from flask import Flask, request, jsonify
from flask_cors import CORS
from google import genai
from google.genai import types
from pydub import AudioSegment

app = Flask(__name__)
CORS(app)

# Tu API Key
API_KEY = "AIzaSyC3895F5JKZSHKng1IVL_3DywImp4lwVyI"

# Usar el modelo de TTS que el usuario solicitó
MODEL = "gemini-2.5-flash-exp-native-audio-thinking-dialog"

# Cliente con configuración beta
client = genai.Client(
    http_options=types.HttpOptions(api_version="v1beta"),
    api_key=API_KEY
)

# La configuración de LiveConnect ya no se usa, pero la mantengo como referencia.
CONFIG = types.LiveConnectConfig(
    response_modalities=["AUDIO"],
    speech_config=types.SpeechConfig(
        voice_config=types.VoiceConfig(
            prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Zephyr")
        )
    )
)

async def generate_native_audio(text):
    """
    Genera audio usando la API de Gemini 2.5 Flash TTS y lo convierte a MP3.
    """
    try:
        print(f"Generando audio para: {text}")

        # Utilizar la API de generación de contenido para obtener el audio PCM
        response = await client.aio.generate_content(
            model=MODEL,
            contents=[{'parts': [{'text': text}]}],
            generation_config=types.GenerationConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Zephyr")
                    )
                )
            )
        )

        audio_part = response.candidates[0].content.parts[0]
        if hasattr(audio_part, 'inline_data') and audio_part.inline_data:
            full_audio_pcm = audio_part.inline_data.data
            
            # Convertir los datos de audio PCM a formato MP3 usando pydub
            # La API de Gemini TTS devuelve PCM de 16-bit (L16) con un sample rate de 24000 Hz
            audio_segment = AudioSegment.from_raw(
                io.BytesIO(full_audio_pcm),
                sample_width=2, # 16-bit
                frame_rate=24000,
                channels=1
            )
            
            # Exportar a un buffer de bytes en formato MP3
            mp3_buffer = io.BytesIO()
            audio_segment.export(mp3_buffer, format="mp3")
            mp3_buffer.seek(0)
            
            audio_base64 = base64.b64encode(mp3_buffer.read()).decode('utf-8')
            
            print(f"Audio completo convertido a MP3: {len(audio_base64)} caracteres")
            return audio_base64
        
        return None
        
    except Exception as e:
        print(f"Error en Gemini API o conversión: {e}")
        return None

@app.route('/chat', methods=['POST'])
def chat():
    print("=== INICIO GEMINI AUDIO ===")
    try:
        data = request.get_json()
        user_text = data.get('text', '').strip()
        
        if not user_text:
            return jsonify({'error': 'Campo text requerido'}), 400
        
        print(f"Texto recibido: {user_text}")
        
        # Crear event loop para async
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        # Generar audio con Gemini TTS API
        audio_base64 = loop.run_until_complete(generate_native_audio(user_text))
        
        if audio_base64:
            response = {
                'candidates': [{
                    'content': {
                        'role': 'model',
                        'parts': [{
                            'inlineData': {
                                'mimeType': 'audio/mpeg', # CORREGIDO: Usar audio/mpeg para MP3
                                'data': audio_base64
                            }
                        }]
                    }
                }]
            }
            print("=== AUDIO GEMINI GENERADO Y CONVERTIDO A MP3 ===")
            return jsonify(response)
        else:
            # Fallback a audio simulado si falla
            print("Usando fallback de audio simulado")
            dummy_audio = b"RIFF fallback audio for: " + user_text.encode('utf-8')[:30]
            fallback_base64 = base64.b64encode(dummy_audio).decode('utf-8')
            
            return jsonify({
                'candidates': [{
                    'content': {
                        'role': 'model',
                        'parts': [{
                            'inlineData': {
                                'mimeType': 'audio/mpeg', # Usar audio/mpeg para MP3
                                'data': fallback_base64
                            }
                        }]
                    }
                }]
            })
            
    except Exception as e:
        print(f"Error general: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'ok',
        'model': MODEL,
        'version': 'gemini-native-audio-mp3'
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"Iniciando con Gemini Native Audio en puerto {port}")
    app.run(host='0.0.0.0', port=port)
