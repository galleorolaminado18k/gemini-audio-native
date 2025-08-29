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
    Genera audio nativo usando Live API con manejo robusto para Railway
    """
    try:
        print(f"Generando audio para: {text_input}")
        
        # Configuración con timeout más corto para Railway
        import asyncio
        
        # Wrapper con timeout
        async def connect_with_timeout():
            try:
                async with client.aio.live.connect(model=MODEL, config=CONFIG) as session:
                    print("Conexión Live API establecida exitosamente")
                    
                    # Enviar texto como entrada
                    await session.send_realtime_input(text=text_input)
                    print("Texto enviado a Live API")
                    
                    # Recopilar respuesta de audio con timeout por chunk
                    audio_chunks = []
                    chunk_count = 0
                    max_chunks = 50  # Límite de chunks para evitar bucles infinitos
                    
                    async for response in session.receive():
                        chunk_count += 1
                        print(f"Procesando chunk {chunk_count}")
                        
                        if response.data is not None:
                            audio_chunks.append(response.data)
                            print(f"Chunk de audio recibido: {len(response.data)} bytes")
                        
                        # Verificar múltiples condiciones de finalización
                        if response.server_content:
                            if hasattr(response.server_content, 'turn_complete'):
                                if response.server_content.turn_complete:
                                    print("Turno completo detectado")
                                    break
                            
                            if response.server_content.model_turn:
                                if hasattr(response.server_content.model_turn, 'parts'):
                                    print("Partes del modelo detectadas")
                        
                        # Límite de seguridad
                        if chunk_count >= max_chunks:
                            print(f"Límite de chunks alcanzado: {max_chunks}")
                            break
                    
                    print(f"Total de chunks de audio recolectados: {len(audio_chunks)}")
                    return audio_chunks
                    
            except Exception as inner_e:
                print(f"Error interno en conexión: {inner_e}")
                return None
        
        # Ejecutar con timeout de 30 segundos
        audio_chunks = await asyncio.wait_for(connect_with_timeout(), timeout=30.0)
        
        if audio_chunks:
            # Combinar todos los chunks de audio
            full_audio = b''.join(audio_chunks)
            
            # Convertir a base64 para la respuesta HTTP
            audio_base64 = base64.b64encode(full_audio).decode('utf-8')
            
            print(f"Audio completo generado: {len(audio_base64)} caracteres base64")
            return audio_base64
        
        return None
            
    except asyncio.TimeoutError:
        print("Timeout en Live API - conexión demasiado lenta")
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
        'version': 'live-api-oficial-railway',
        'sdk_version': '1.6.0'
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
    print(f"SDK: google-genai 1.6.0")
    print(f"Timeout configurado: 30 segundos")
    app.run(host='0.0.0.0', port=port, debug=False)
