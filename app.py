import os
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

# Usar modelo estándar que definitivamente funciona
client = genai.Client(api_key=API_KEY)

def text_to_speech_simulation(text):
   """Simula conversión de texto a audio devolviendo datos base64 ficticios"""
   # Por ahora, crear una respuesta de audio simulada
   # En un caso real, aquí iría la conversión text-to-speech
   dummy_audio = b"RIFF fake audio data for testing purposes"
   return base64.b64encode(dummy_audio).decode('utf-8')

@app.route('/chat', methods=['POST'])
def chat():
   """Endpoint principal - versión simplificada"""
   try:
       # Obtener datos del request
       data = request.get_json()
       user_text = data.get('text', '').strip()
       
       if not user_text:
           return jsonify({'error': 'Campo text requerido'}), 400
       
       print(f"Texto recibido: {user_text}")
       
       # Generar texto con Gemini (modelo estándar)
       response = client.models.generate_content(
           model="gemini-2.0-flash-001",
           contents=user_text
       )
       
       generated_text = response.text
       print(f"Texto generado: {generated_text}")
       
       # Simular conversión a audio
       audio_base64 = text_to_speech_simulation(generated_text)
       
       # Formato compatible con BuilderBot
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
       
       print("Respuesta enviada exitosamente")
       return jsonify(result)
           
   except Exception as e:
       print(f"Error en endpoint: {e}")
       return jsonify({'error': f'Error interno: {str(e)}'}), 500

@app.route('/health', methods=['GET'])
def health():
   """Endpoint de salud"""
   return jsonify({
       'status': 'ok', 
       'model': 'gemini-2.0-flash-001',
       'version': 'simplified'
   })

if __name__ == '__main__':
   port = int(os.environ.get('PORT', 5000))
   print(f"Iniciando servidor simplificado en puerto {port}")
   app.run(host='0.0.0.0', port=port, debug=True)
