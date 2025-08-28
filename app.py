import os
import asyncio
import base64
from flask import Flask, request, jsonify
from flask_cors import CORS
from google import genai
from google.genai import types

app = Flask(__name__)
CORS(app)

# Nueva API Key
API_KEY = "AIzaSyC3895F5JKZSHKng1IVL_3DywImp4lwVyI"
MODEL = "models/gemini-2.5-flash-exp-native-audio-thinking-dialog"

# Cliente con configuración beta
client = genai.Client(
    http_options=types.HttpOptions(api_version="v1beta"),
    api_key=API_KEY
)

# Configuración para audio nativo en formato PCM (compatible con WhatsApp)
CONFIG = types.LiveConnectConfig(
    response_modalities=["AUDIO"],
    speech_config=types.SpeechConfig(
        voice_config=types.VoiceConfig(
            prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Zephyr")
        ),
        # Especificar formato de salida como PCM
        output_audio_config=types.OutputAudioConfig(
            audio_encoding="LINEAR16"  # Esto genera PCM raw
        )
    )
)

async def generate_native_audio(text):
    """Genera audio nativo en formato PCM usando Gemini Live API"""
    try:
        print(f"Generando audio PCM para: {text}")
        
        async with client.aio.live.connect(model=MODEL, config=CONFIG) as session:
            await session.send(input=text, end_of_turn=True)
            
            audio_chunks = []
            turn = session.receive()
            
            async for response in turn:
                if hasattr(response, 'data') and response.data:
                    audio_chunks.append(response.data)
                    print(f"Chunk recibido: {len(response.data)} bytes")
            
            if audio_chunks:
                full_audio = b''.join(audio_chunks)
                audio_base64 = base64.b64encode(full_audio).decode('utf-8')
                print(f"Audio PCM generado: {len(audio_base64)} caracteres")
                return audio_base64
            
            return None
            
    except Exception as e:
        print(f"Error en Live API: {e}")
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
        
        # Generar audio con Gemini Live API
        audio_base64 = loop.run_until_complete(generate_native_audio(user_text))
        
        if audio_base64:
            response = {
                'candidates': [{
                    'content': {
                        'role': 'model',
                        'parts': [{
                            'inlineData': {
                                'mimeType': 'audio/pcm',  # ← Crucial para WhatsApp
                                'data': audio_base64
                            }
                        }]
                    }
                }]
            }
            print("=== AUDIO PCM GENERADO PARA WHATSAPP ===")
            return jsonify(response)
        else:
            # Fallback a audio simulado si falla
            print("Usando fallback de audio simulado")
            dummy_audio = b"\x00\x00\x00\x00\x00\x00\x00\x00" + user_text.encode('utf-8')[:30]
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
        'version': 'gemini-native-audio-pcm-whatsapp'
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"Iniciando con Gemini Native Audio (PCM) en puerto {port}")
    app.run(host='0.0.0.0', port=port)
