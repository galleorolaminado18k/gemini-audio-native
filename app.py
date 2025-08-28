from flask import Flask, request, jsonify
from flask_cors import CORS
import base64
import os

app = Flask(__name__)
CORS(app)

@app.route('/chat', methods=['POST'])
def chat():
    print("=== INICIO CHAT ===")
    try:
        data = request.get_json()
        user_text = data.get('text', '') if data else 'sin texto'
        print(f"Texto: {user_text}")
        
        # Audio simulado
        audio_data = b"RIFF" + b"\x00" * 40 + user_text.encode('utf-8')[:20]
        audio_base64 = base64.b64encode(audio_data).decode('utf-8')
        print(f"Audio generado: {len(audio_base64)} caracteres")
        
        response = {
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
        
        print("=== RESPUESTA OK ===")
        return jsonify(response)
        
    except Exception as e:
        print(f"ERROR: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'version': 'clean'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
