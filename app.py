import os
import io
import json
import base64
import uuid
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import google.generativeai as genai
import pydub

# Configuración de la API de Gemini
# Usa la variable de entorno GOOGLE_API_KEY
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
if not GOOGLE_API_KEY:
    raise ValueError("No se encontró la variable de entorno GOOGLE_API_KEY.")

genai.configure(api_key=GOOGLE_API_KEY)

# Configuración de la aplicación Flask
app = Flask(__name__)
CORS(app)

# Ruta principal (opcional, para verificar que la app esté viva)
@app.route('/', methods=['GET'])
def home():
    return "API Gemini Audio Bot está funcionando!", 200

# Ruta para servir los archivos de audio
@app.route('/audio/<filename>', methods=['GET'])
def get_audio(filename):
    """
    Sirve un archivo de audio temporal desde el directorio 'temp_audio'.
    """
    audio_path = os.path.join('temp_audio', filename)
    if os.path.exists(audio_path):
        return send_file(audio_path, mimetype='audio/mp3')
    else:
        return jsonify({"error": "Archivo de audio no encontrado."}), 404

# Ruta de chat asincrónica
@app.route('/chat', methods=['POST'])
async def chat():
    print("=== INICIO GEMINI AUDIO ===")
    try:
        data = request.json
        if not data or 'text' not in data:
            return jsonify({"error": "No se encontró el campo 'text' en la petición"}), 400

        user_text = data['text']
        print(f"Texto recibido: {user_text}")

        # Configura la petición para la API de Gemini, solicitando audio
        generation_config = genai.types.GenerationConfig(
            response_modality="AUDIO",
            speech_config={
                "voice_config": {
                    "prebuilt_voice_config": {
                        "voice_name": "Kore"
                    }
                }
            }
        )
        
        # Llama a la API de Gemini
        print("Llamando a la API de Gemini...")
        response = await genai.generate_content_async(
            user_text,
            generation_config=generation_config,
            model="gemini-2.5-flash-preview-tts"
        )
        print("Respuesta de Gemini recibida.")

        if not response.candidates:
            return jsonify({"error": "No se encontraron candidatos en la respuesta de Gemini."}), 500

        candidate = response.candidates[0]
        if not candidate.content or not candidate.content.parts:
            return jsonify({"error": "El contenido de la respuesta de Gemini está vacío."}), 500

        audio_part = candidate.content.parts[0]
        audio_data_base64 = audio_part.inline_data.data

        # Convierte el audio de base64 a bytes PCM16
        audio_bytes = base64.b64decode(audio_data_base64)
        print(f"Bytes de audio PCM16 recibidos, longitud: {len(audio_bytes)}")

        try:
            pcm_audio = pydub.AudioSegment(
                data=audio_bytes,
                sample_width=2,  # 16-bit PCM
                frame_rate=16000, # La API de Gemini TTS usa 16kHz
                channels=1
            )
            print("Conversión a PCM exitosa.")

            # Crea un nombre de archivo único para evitar conflictos
            filename = f"audio-{uuid.uuid4()}.mp3"
            temp_dir = 'temp_audio'
            os.makedirs(temp_dir, exist_ok=True)
            file_path = os.path.join(temp_dir, filename)

            # Exporta el audio a un archivo MP3 temporal
            pcm_audio.export(file_path, format="mp3")
            print(f"Archivo MP3 guardado en: {file_path}")
            
            # Construye la URL pública
            # Reemplaza <replit_username>-<project_name> con tu URL de Replit
            base_url = os.getenv('REPLIT_URL')
            if not base_url:
                base_url = request.url_root
            
            audio_url = f"{base_url}audio/{filename}"
            print(f"URL de audio generada: {audio_url}")

            # Devuelve la URL en formato JSON
            return jsonify({
                "audio_url": audio_url
            }), 200

        except Exception as e:
            print(f"Error en la conversión y guardado de audio: {e}")
            return jsonify({"error": f"Error en el procesamiento de audio: {e}"}), 500

    except Exception as e:
        print(f"Error general: {e}")
        return jsonify({"error": "Error interno del servidor"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)
