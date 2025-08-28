from flask import Flask, request, jsonify
from flask_cors import CORS
import base64
import os

app = Flask(__name__)
CORS(app)

@app.route('/chat', methods=['POST'])
def chat():
    try:
        print("=== INICIO DE PETICIÓN ===")
        
        # Obtener datos del request
        data = request.get_json()
        print(f"Datos recibidos: {data}")
        
        user_text = data.get('text', '') if data else ''
        print(f"Texto extraído: '{user_text}'")
        
        # Crear audio simulado más realista
        dummy_audio = b"RIFF" + b"\x00" * 44 + b"audio simulation response for: " + user_text.encode('utf-8')[:50]
        audio_base64 = base64.b64encode(dummy_audio).decode('utf-8')
        print(f"Audio base64 generado, longitud: {len(audio_base64)}")
        
        # Respuesta en formato correcto
        result = {
            'candidates': [{
                'content': {
                    'role': 'model',
                    'parts': [{
                        'inlineData': {
                            'mimeType': 'audio/wav',
                            'data': audio_base64
                        }
                    }]
                }
            }]
        }
        
        print("=== RESPUESTA ENVIADA EXITOSAMENTE ===")
        return jsonify(result)
        
    except Exception as e:
        print(f"=== ERROR: {e} ===")
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'version': 'no-gemini'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
