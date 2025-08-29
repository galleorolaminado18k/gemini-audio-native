import os
import asyncio
import base64
import io
from flask import Flask, request, jsonify
from flask_cors import CORS
from google import genai
from google.genai import types

app = Flask(__name__)
CORS(app)

# Configuración según documentación oficial
API_KEY = "AIzaSyC3895F5JKZSHKng1IVL_3DywImp4lwVyI"
MODEL = "gemini-2.0-flash-live-001"  # Modelo correcto

# Cliente con API key
client = genai.Client(api_key=API_KEY)

# Configuración Live API según documentación
CONFIG = {
    "response_modalities": ["AUDIO"],
    "system_instruction": "Eres un asistente útil que responde de manera amigable y natural."
}

async def generate_native_audio_official(text_input):
    """
    Genera audio nativo usando Live API siguiendo exactamente la documentación oficial
    """
    try:
        print(f"Generando audio para: {text_input}")
        
        # Establecer conexión Live API según documentación
        async with client.aio.live.connect(model=MODEL, config=CONFIG) as session:
            
            # Enviar texto como entrada (según documentación oficial)
            await session.send_realtime_input(
                text=text_input
            )
            
            # Recopilar respuesta de audio
            audio_chunks = []
            
            # Recibir respuesta usando el patrón oficial
            async for response in session.receive():
                if response.data is not None:
                    # Acumular datos de audio
                    audio_chunks.append(response.data)
                    print(f"Chunk de audio recibido: {len(response.data)} bytes")
                
                # Verificar si el turno está completo
                if (response.server_content and 
                    response.server_content.model_turn and 
                    hasattr(response.server_content, 'turn_complete') and 
                    response.server_content.turn_complete):
                    break
            
            # Combinar todos los chunks de audio
            if audio_chunks:
                # Los chunks ya vienen como bytes, combinarlos
                full_audio = b''.join(audio_chunks)
                
                # Convertir a base64 para la respuesta HTTP
                audio_base64 = base64.b64encode(full_audio).decode('utf-8')
                
                print(f"Audio completo generado: {len(audio_base64)} caracteres base64")
                return audio_base64
            
            return None
            
    except Exception as e:
        print(f"Error en Live API: {e}")
        print(f"Tipo de error: {type(e)}")
        return None

@app.route('/chat', methods=['POST'])
def chat():
    """Endpoint principal usando Live API oficial"""
    print("=== INICIO GEMINI LIVE API OFICIAL ===")
    
    try:
        # Obtener datos del request
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No se recibieron datos JSON'}), 400
        
        user_text = data.get('text', '').strip()
        if not user_text:
            return jsonify({'error': 'Campo text requerido y no puede estar vacío'}), 400
        
        print(f"Texto recibido: '{user_text}'")
        
        # Crear event loop para función async
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        # Generar audio usando Live API oficial
        audio_base64 = loop.run_until_complete(generate_native_audio_official(user_text))
        
        if audio_base64:
            # Respuesta en formato esperado por BuilderBot
            response = {
                'candidates': [{
                    'content': {
                        'role': 'model',
                        'parts': [{
                            'inlineData': {
                                'mimeType': 'audio/pcm',  # Formato PCM como en documentación
                                'data': audio_base64
                            }
                        }]
                    }
                }]
            }
            
            print("=== AUDIO NATIVO GENERADO EXITOSAMENTE ===")
            return jsonify(response)
        
        else:
            # Respuesta de error si no se pudo generar audio
            print("No se pudo generar audio con Live API")
            return jsonify({'error': 'No se pudo generar el audio'}), 500
    
    except Exception as e:
        print(f"Error en endpoint /chat: {e}")
        print(f"Tipo de error: {type(e)}")
        return jsonify({'error': f'Error interno del servidor: {str(e)}'}), 500

@app.route('/health', methods=['GET'])
def health():
    """Endpoint de verificación de salud"""
    return jsonify({
        'status': 'ok',
        'model': MODEL,
        'version': 'live-api-oficial',
        'sdk_version': '1.0.1'
    })

@app.route('/test', methods=['GET'])
def test():
    """Endpoint de prueba simple"""
    return jsonify({
        'message': 'Servidor funcionando correctamente',
        'api_configured': bool(API_KEY),
        'model': MODEL
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"=== INICIANDO GEMINI LIVE API SERVIDOR ===")
    print(f"Puerto: {port}")
    print(f"Modelo: {MODEL}")
    print(f"SDK: google-genai 1.0.1")
    app.run(host='0.0.0.0', port=port, debug=False)
