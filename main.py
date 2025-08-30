# 1. Generar audio con Gemini TTS
response = client.models.generate_content(
    model="gemini-2.5-flash-preview-tts",
    contents=user_text,
    config={
        "response_mime_type": "audio/ogg"
    }
)

# 2. Extraer audio
audio_base64 = response.candidates[0].content.parts[0].inline_data.data
audio_data = base64.b64decode(audio_base64)

# 3. Guardar en Google Sheets
if gs_ready and sheet is not None:
    try:
        sheet.append_row([user_text, "(audio generado por Gemini)", audio_base64])
    except Exception as e_sheet:
        print(f"⚠️ No se pudo escribir en Sheets: {e_sheet}")

# 4. Guardar en cache y construir URL
audio_id = str(uuid4())
audio_cache[audio_id] = audio_data
audio_url = f"{_public_base_url()}/audio/{audio_id}.ogg"

# 5. Respuesta JSON
return jsonify({
    "text_response": "(solo audio, no texto)",
    "audio_base64": audio_base64,
    "audio_url": audio_url,
    "candidates": [{
        "content": {
            "role": "model",
            "parts": [{
                "inlineData": {
                    "mimeType": "audio/ogg",
                    "data": audio_base64
                }
            }]
        }
    }]
}), 200
