import os
import base64
from flask import Flask, request, jsonify
from flask_cors import CORS
from google import genai

app = Flask(__name__)
CORS(app)

API_KEY = "AIzaSyC3895F5JKZSHKng1IVL_3DywImp4lwVyI"
client = genai.Client(api_key=API_KEY)

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.get_json()
        user_text = data.get('text', '').strip()
        
        if not user_text:
            return jsonify({'error': 'Campo text requerido'}), 400
        
        print(f"Texto recibido: {user_text}")
        
        # Usar generateContent normal (funciona en todos los hostings)
        response = client.models.generate_content(
            model="gemini-2.0-flash-001",
            contents=user_text
        )
        
        generated_text = response.text
        print(f"Respuesta generada: {generated_text}")
        
        # Simular audio base64 con la respuesta
        audio_data = b"AUDIO:" + generated_text.encode('utf-8')[:500]
        audio_base64 = base64.b64encode(audio_data).decode('utf-8')
        
        return jsonify({
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
        })
        
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'version': 'no-live-api'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
