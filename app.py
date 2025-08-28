@app.route('/chat', methods=['POST'])
def chat():
    """Endpoint principal - versión corregida"""
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
        
        # Corregir la extracción del texto
        if hasattr(response, 'text') and response.text:
            generated_text = response.text
        elif hasattr(response, 'candidates') and response.candidates:
            generated_text = response.candidates[0].content.parts[0].text
        else:
            generated_text = "Hola, aquí tienes tu respuesta de audio."
        
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
        print(f"Tipo de error: {type(e)}")
        # Devolver respuesta de respaldo
        backup_audio = text_to_speech_simulation("Respuesta de audio de respaldo")
        return jsonify({
            'candidates': [{
                'content': {
                    'role': 'model',
                    'parts': [{
                        'inlineData': {
                            'mimeType': 'audio/wav',
                            'data': backup_audio
                        }
                    }]
                }
            }]
        })
