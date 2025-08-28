import os
import asyncio
import base64
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
from google import genai
from google.genai import types

app = Flask(__name__)
CORS(app)

# Configuración
API_KEY = "AIzaSyC3895F5JKZSHKng1IVL_3DywImp4lwVyI"
MODEL = "models/gemini-2.5-flash-exp-native-audio-thinking-dialog"

# Cliente con configuración beta para Live API
client = genai.Client(
    http_options=types.HttpOptions(api_version="v1beta"),
    api_key=API_KEY
)

# Configuración para audio nativo
AUDIO_CONFIG = types.LiveConnectConfig(
    response_modalities=["AUDIO"],
    media_resolution="MEDIA_RESOLUTION_MEDIUM",
    speech_config=types.SpeechConfig(
        voice_config=types.VoiceConfig(
            prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Zephyr")
        )
    )
)

async def generate_native_audio(text):
    """Genera audio nativo usando Live API de Gemini 2.5 Flash Exp"""
    try:
        # Conectar a Live API
        async with client.aio.live.connect(model=MODEL, config=AUDIO_CONFIG) as session:
            # Enviar texto del usuario
            await session.send(input=text, end_of_turn=True)
            
            # Recopilar respuesta de audio
            audio_chunks = []
            turn = session.receive()
            
            async for response in turn:
                # Obtener datos de audio
                if hasattr(response, 'data') and response.data:
                    audio_chunks.append(response.data)
                
                # También obtener texto si está disponible
                if hasattr(response, 'text') and response.text:
                    print(f"Texto generado: {response.text}")
            
            # Combinar todos los chunks de audio
            if audio_chunks:
                full_audio = b''.join(audio_chunks)
                # Convertir a base64
                audio_base64 = base64.b64encode(full_audio).decode('utf-8')
                return audio_base64
            
            return None
            
    except Exception as e:
        print(f"Error generando audio: {e}")
        return None

@app.route('/chat', methods=['POST'])
def chat():
    """Endpoint principal para generar audio nativo"""
    try:
        # Obtener datos del request
        data = request.get_json()
        user_text = data.get('text', '').strip()
        
        if not user_text:
            return jsonify({'error': 'Campo text requerido'}), 400
        
        print(f"Texto recibido: {user_text}")
        
        # Crear nuevo event loop para async
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        # Generar audio usando Live API
        audio_base64 = loop.run_until_complete(generate_native_audio(user_text))
        
        if audio_base64:
            # Formato compatible con BuilderBot
            response = {
                'candidates': [{
                    'content': {
                        'role': 'model',
                        'parts': [{
                            'inlineData': {
                                'mimeType': 'audio/pcm',
                                'data': audio_base64
                            }
                        }]
                    }
                }]
            }
            print(f"Audio generado exitosamente, tamaño base64: {len(audio_base64)}")
            return jsonify(response)
        else:
            return jsonify({'error': 'No se pudo generar el audio'}), 500
            
    except Exception as e:
        print(f"Error en endpoint: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    """Endpoint de salud"""
    return jsonify({'status': 'ok', 'model': MODEL})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"Iniciando servidor en puerto {port}")
    print(f"Modelo: {MODEL}")
    app.run(host='0.0.0.0', port=port, debug=False)
