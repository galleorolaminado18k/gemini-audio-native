import React, { useState, useRef } from 'react';

// Este es el componente principal de tu aplicación
const App = () => {
  const [text, setText] = useState('');
  const [isSending, setIsSending] = useState(false);
  const [audioUrl, setAudioUrl] = useState('');
  const [errorMessage, setErrorMessage] = useState('');
  const audioRef = useRef(null);

  // La URL de tu API de Flask en Replit
  const API_URL = "https://gemini-audio-native.replit.dev/chat";

  // Esta función maneja el envío del formulario
  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsSending(true);
    setAudioUrl('');
    setErrorMessage('');

    try {
      // Envía una petición POST a tu API
      const response = await fetch(API_URL, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ text: text }),
      });

      // Si la respuesta no es exitosa, lanza un error
      if (!response.ok) {
        throw new Error(`Error en la respuesta de la API: ${response.statusText}`);
      }

      const data = await response.json();
      
      // Extrae el audio en base64 de la respuesta
      const audioData = data.candidates?.[0]?.content?.parts?.[0]?.inlineData?.data;
      const mimeType = data.candidates?.[0]?.content?.[0]?.inlineData?.mimeType;

      if (audioData && mimeType) {
        // Crea una URL de objeto para el audio
        const audioBlob = base64toBlob(audioData, mimeType);
        const url = URL.createObjectURL(audioBlob);
        setAudioUrl(url);
        if (audioRef.current) {
          audioRef.current.play();
        }
      } else {
        setErrorMessage('No se encontró audio en la respuesta de la API.');
      }
    } catch (error) {
      console.error("Error al enviar la solicitud:", error);
      setErrorMessage(`Ocurrió un error: ${error.message}`);
    } finally {
      setIsSending(false);
    }
  };

  // Función para convertir base64 a Blob
  const base64toBlob = (base64, mimeType) => {
    const byteCharacters = atob(base64);
    const byteNumbers = new Array(byteCharacters.length);
    for (let i = 0; i < byteCharacters.length; i++) {
      byteNumbers[i] = byteCharacters.charCodeAt(i);
    }
    const byteArray = new Uint8Array(byteNumbers);
    return new Blob([byteArray], { type: mimeType });
  };

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100 p-4 font-sans">
      <div className="w-full max-w-2xl bg-white rounded-2xl shadow-xl p-8 space-y-6">
        <header className="text-center">
          <h1 className="text-4xl font-extrabold text-gray-800 tracking-tight">
            <span className="bg-gradient-to-r from-blue-500 to-purple-600 text-transparent bg-clip-text">
              Audio Bot
            </span>
          </h1>
          <p className="mt-2 text-gray-600">
            Ingresa un texto para convertirlo a audio usando Gemini AI.
          </p>
        </header>

        <main>
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <div className="relative">
              <textarea
                value={text}
                onChange={(e) => setText(e.target.value)}
                className="w-full p-4 pl-12 pr-4 bg-gray-50 text-gray-700 rounded-xl border border-gray-300 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all duration-300 resize-none"
                rows="4"
                placeholder="Escribe tu mensaje aquí..."
                disabled={isSending}
              />
              <div className="absolute top-4 left-4 text-gray-400">
                <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="lucide lucide-mic"><path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" x2="12" y1="19" y2="22"/></svg>
              </div>
            </div>
            
            <button
              type="submit"
              className="w-full py-3 px-4 flex items-center justify-center gap-2 rounded-xl text-white font-semibold transition-all duration-300 
                         bg-gradient-to-r from-blue-500 to-purple-600 hover:from-blue-600 hover:to-purple-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
              disabled={isSending}
            >
              {isSending ? (
                <>
                  <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="lucide lucide-loader-2 animate-spin"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>
                  <span>Generando...</span>
                </>
              ) : (
                <>
                  <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="lucide lucide-send-horizonal"><path d="m3 3 3 9-3 9 19-9Z"/><path d="M6 12h16"/></svg>
                  <span>Generar Audio</span>
                </>
              )}
            </button>
          </form>

          {errorMessage && (
            <div className="mt-4 p-4 text-red-700 bg-red-100 rounded-xl border border-red-300">
              <p className="font-medium">Error:</p>
              <p>{errorMessage}</p>
            </div>
          )}

          {audioUrl && (
            <div className="mt-6 flex flex-col items-center gap-4 p-6 bg-blue-50 rounded-2xl border border-blue-200 shadow-inner">
              <h2 className="text-xl font-bold text-blue-800 flex items-center gap-2">
                <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="lucide lucide-volume-2"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14"/></svg>
                <span>Audio Generado</span>
              </h2>
              <audio 
                controls 
                ref={audioRef}
                src={audioUrl}
                className="w-full"
              />
            </div>
          )}
        </main>
      </div>
    </div>
  );
};

export default App;
