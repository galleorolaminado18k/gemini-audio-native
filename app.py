import os
import asyncio
import base64
from flask import Flask, request, jsonify
from flask_cors import CORS
from google import genai
from google.genai import types

app = Flask(__name__)
CORS(app)

# Tu API Key
API_KEY = "AIzaSyC3895F5JKZSHKng1IVL_3DywImp4lwVyI"

# Usar el modelo de TTS público y documentado
MODEL = "gemini-2.5-flash-preview-tts"

# Cliente con configuración beta
client = genai.Client(
    http_options=types.HttpOptions(api_version="v1beta"),
    api_key=API_KEY
)

# Configuración para audio nativo
CONFIG = types.LiveConnectConfig(
    response_modalities=["AUDIO"],
    speech_config=types.SpeechConfig(
        voice_config=types.VoiceConfig(
            prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Zephyr")
        )
    )
)

async def generate_native_audio(text):
    """Genera audio nativo usando Gemini 2.5 Flash TTS"""
    try:
        print(f"Generando audio para: {text}")

        # Utilizar la API de generación de contenido en lugar de Live API
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
            full_audio = audio_part.inline_data.data
            audio_base64 = base64.b64encode(full_audio).decode('utf-8')
            print(f"Audio completo generado: {len(audio_base64)} caracteres")
            return audio_base64
        
        return None
        
    except Exception as e:
        print(f"Error en Gemini API: {e}")
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
                                'mimeType': 'audio/pcm', # CORREGIDO: Usar audio/pcm
                                'data': audio_base64
                            }
                        }]
                    }
                }]
            }
            print("=== AUDIO GEMINI GENERADO ===")
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
                                'mimeType': 'audio/pcm',
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
        'version': 'gemini-native-audio-pcm'
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"Iniciando con Gemini Native Audio en puerto {port}")
    app.run(host='0.0.0.0', port=port)
