
# Omite espacio al comienzo y punto al final. mantiene mayusc

import tkinter as tk
from tkinter import messagebox, ttk, scrolledtext, simpledialog, filedialog
import pyaudio
import wave
import threading
import pyperclip
import io
import os
from groq import Groq
import tempfile
import winreg
import pystray
from PIL import Image, ImageTk
import keyboard


# Importar servicios de transcripción
try:
    import speech_recognition as sr
    google_service_available = True
except ImportError:
    google_service_available = False

class TranscriptionApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Transcripción de Audio en Tiempo Real")
        self.root.geometry("400x500")
        
        self.recording = False
        self.always_on_top = False
        self.transcribing = False
        self.service = "Whisper (Groq)"
        self.log_visible = True
        
        self.groq_api_key = self.get_groq_api_key_from_registry()
        self.groq_client = None if not self.groq_api_key else Groq(api_key=self.groq_api_key)
        
        self.create_widgets()
        self.check_service_availability()

        # Crear icono en la bandeja del sistema
        self.create_system_tray_icon()

        # Configurar el atajo de teclado
        keyboard.add_hotkey('ctrl+alt+m', self.toggle_recording_hotkey)

        # Mostrar el log al iniciar
        self.log_frame.pack(fill=tk.BOTH, expand=True)

    def get_groq_api_key_from_registry(self):
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"SOFTWARE\TranscriptionApp", 0, winreg.KEY_READ)
            value, _ = winreg.QueryValueEx(key, "GroqApiKey")
            winreg.CloseKey(key)
            return value
        except WindowsError:
            return None

    def save_groq_api_key_to_registry(self, api_key):
        try:
            key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"SOFTWARE\TranscriptionApp")
            winreg.SetValueEx(key, "GroqApiKey", 0, winreg.REG_SZ, api_key)
            winreg.CloseKey(key)
        except WindowsError as e:
            print(f"Error al guardar la API key en el registro: {e}")

    def create_widgets(self):
        self.main_frame = tk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        self.top_frame = tk.Frame(self.main_frame)
        self.top_frame.pack(side=tk.TOP, fill=tk.X)

        self.bottom_frame = tk.Frame(self.main_frame)
        self.bottom_frame.pack(side=tk.BOTTOM, fill=tk.X)

        self.start_button = tk.Button(self.top_frame, text="Iniciar Grabación", command=self.toggle_recording, width=20, height=2)
        self.start_button.pack(pady=20)

        self.always_on_top_button = tk.Button(self.top_frame, text="Siempre Visible: Apagado", command=self.toggle_always_on_top)
        self.always_on_top_button.pack(pady=10)
        
        self.status_label = tk.Label(self.top_frame, text="Estado: Inactivo")
        self.status_label.pack(pady=10)
        
        self.service_label = tk.Label(self.top_frame, text="Selecciona el servicio de transcripción:")
        self.service_label.pack(pady=10)

        self.service_var = tk.StringVar(value="Whisper (Groq)")
        self.service_radio_whisper = tk.Radiobutton(self.top_frame, text="Whisper (Groq)", variable=self.service_var, value="Whisper (Groq)", command=self.change_service)
        self.service_radio_whisper.pack()
        self.service_radio_google = tk.Radiobutton(self.top_frame, text="Google", variable=self.service_var, value="Google", command=self.change_service)
        self.service_radio_google.pack()

        self.toggle_log_button = tk.Button(self.top_frame, text="Ocultar Log", command=self.toggle_log)
        self.toggle_log_button.pack(pady=10)

        self.log_frame = tk.Frame(self.main_frame)
        self.log_frame.pack(fill=tk.BOTH, expand=True)

        self.log_text = scrolledtext.ScrolledText(self.log_frame, wrap=tk.WORD, state="disabled", height=10)
        self.log_text.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        self.change_api_key_button = tk.Button(self.bottom_frame, text="Cambiar API Key de Groq", command=self.change_groq_api_key)
        self.change_api_key_button.pack(side=tk.LEFT, padx=5, pady=5)

        self.api_status_frame = tk.Frame(self.bottom_frame)
        self.api_status_frame.pack(side=tk.RIGHT, padx=5, pady=5)

        self.groq_status_label = tk.Label(self.api_status_frame, text="Groq API:")
        self.groq_status_label.pack(side=tk.LEFT)

        self.groq_status_indicator = tk.Canvas(self.api_status_frame, width=15, height=15)
        self.groq_status_indicator.pack(side=tk.LEFT, padx=(5, 10))

        self.google_status_label = tk.Label(self.api_status_frame, text="Google API:")
        self.google_status_label.pack(side=tk.LEFT)

        self.google_status_indicator = tk.Canvas(self.api_status_frame, width=15, height=15)
        self.google_status_indicator.pack(side=tk.LEFT, padx=5)

        self.mic_label = tk.Label(self.top_frame, text="Micrófono en uso: Desconocido")
        self.mic_label.pack(pady=10)

        self.update_mic_info()

    def update_mic_info(self):
        p = pyaudio.PyAudio()
        default_mic = p.get_default_input_device_info()
        mic_name = default_mic['name']
        self.mic_label.config(text=f"Micrófono en uso: {mic_name}")
        p.terminate()

    def update_api_status_indicators(self):
        # Actualizar indicador de Groq
        if self.groq_client:
            self.groq_status_indicator.create_oval(2, 2, 13, 13, fill="green", outline="")
        elif self.groq_api_key is None:
            self.groq_status_indicator.create_oval(2, 2, 13, 13, fill="gray", outline="")
        else:
            self.groq_status_indicator.create_oval(2, 2, 13, 13, fill="red", outline="")

        # Actualizar indicador de Google
        if google_service_available:
            self.google_status_indicator.create_oval(2, 2, 13, 13, fill="green", outline="")
        else:
            self.google_status_indicator.create_oval(2, 2, 13, 13, fill="red", outline="")

    def log_message(self, message):
        self.log_text.config(state="normal")
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.config(state="disabled")
        self.log_text.see(tk.END)

    def check_service_availability(self):
        if google_service_available:
            self.log_message("Google Cloud Speech-to-Text está disponible.")
        else:
            self.log_message("Google Cloud Speech-to-Text no está disponible.")

        if self.groq_api_key:
            self.log_message("Whisper (Groq) está disponible.")
        else:
            self.log_message("Whisper (Groq) no está disponible. API key no proporcionada.")

        self.update_api_status_indicators()

    def toggle_recording(self):
        if self.recording:
            self.stop_recording()
        else:
            self.start_recording()

    def start_recording(self):
        self.recording = True
        self.status_label.config(text="Estado: Grabando...")
        self.start_button.config(text="Detener Grabación")
        self.log_message("Grabación iniciada.")
        self.icon.icon = self.create_icon_image("red")
        threading.Thread(target=self.record_audio).start()

    def stop_recording(self):
        self.recording = False
        self.status_label.config(text="Estado: Inactivo")
        self.start_button.config(text="Iniciar Grabación")
        self.log_message("Grabación detenida.")
        self.icon.icon = self.create_icon_image("blue")

    def toggle_always_on_top(self):
        self.always_on_top = not self.always_on_top
        self.root.attributes("-topmost", self.always_on_top)
        self.always_on_top_button.config(text=f"Siempre Visible: {'Encendido' if self.always_on_top else 'Apagado'}")
        self.log_message(f"Siempre Visible: {'Encendido' if self.always_on_top else 'Apagado'}")

    def change_service(self):
        self.service = self.service_var.get()
        self.log_message(f"Servicio de transcripción cambiado a: {self.service}")

    def record_audio(self):
        p = pyaudio.PyAudio()
        stream = p.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=1024)
        frames = []

        while self.recording:
            data = stream.read(1024)
            frames.append(data)
        
        stream.stop_stream()
        stream.close()
        p.terminate()

        audio_data = b''.join(frames)
        
        self.log_message("Audio grabado, iniciando transcripción...")
        if self.service == "Whisper (Groq)":
            self.transcribe_with_whisper_groq(audio_data)
        elif self.service == "Google":
            self.transcribe_with_google(io.BytesIO(audio_data))

    def transcribe_with_google(self, audio_data):
        recognizer = sr.Recognizer()
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp_audio:
                wf = wave.open(temp_audio.name, 'wb')
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(16000)
                wf.writeframes(audio_data.getvalue())
                wf.close()

                with sr.AudioFile(temp_audio.name) as source:
                    audio = recognizer.record(source)

            os.unlink(temp_audio.name)

            text = recognizer.recognize_google(audio, language="es-ES")
            text = self.format_transcription(text)
            pyperclip.copy(text)
            self.log_message(f"Transcripción con Google: {text}")
            self.icon.icon = self.create_icon_image("green")
            self.paste_transcription()
        except sr.UnknownValueError:
            error_msg = "No se pudo entender el audio."
            self.log_message(f"Error de Transcripción con Google: {error_msg}")
        except sr.RequestError as e:
            error_msg = f"No se pudo solicitar el servicio de Google: {e}"
            self.log_message(f"Error de Transcripción con Google: {error_msg}")
        except Exception as e:
            error_msg = f"Error inesperado durante la transcripción con Google: {e}"
            self.log_message(error_msg)

    def transcribe_with_whisper_groq(self, audio_data):
        if not self.groq_client:
            self.log_message("Advertencia: API key de Groq no proporcionada. La transcripción puede no ser posible.")
            return

        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp_audio:
                wf = wave.open(temp_audio.name, 'wb')
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(16000)
                wf.writeframes(audio_data)
                wf.close()

                with open(temp_audio.name, "rb") as file:
                    transcription = self.groq_client.audio.transcriptions.create(
                        file=file,
                        model="whisper-large-v3",
                        response_format="json",
                        language="es"
                    )

                if isinstance(transcription, dict) and 'text' in transcription:
                    transcribed_text = transcription['text']
                elif hasattr(transcription, 'text'):
                    transcribed_text = transcription.text
                else:
                    raise ValueError("No se pudo encontrar el texto transcrito en la respuesta de la API")

            os.unlink(temp_audio.name)

            transcribed_text = self.format_transcription(transcribed_text)
            pyperclip.copy(transcribed_text)
            self.log_message(f"Transcripción con Whisper (Groq): {transcribed_text}")
            self.icon.icon = self.create_icon_image("green")
            self.paste_transcription()
        except Exception as e:
            error_msg = f"Error de Transcripción con Whisper (Groq): {e}"
            self.log_message(error_msg)

    def format_transcription(self, text):
        """Formatea la transcripción para eliminar espacios en blanco, 
        asegurar que la primera letra sea mayúscula y que no termine en punto.
        """
        text = text.strip() 
        text = text.capitalize()
        if text.endswith('.'):
            text = text[:-1]
        return text

    def paste_transcription(self):
        keyboard.press_and_release('ctrl+v')

    def change_groq_api_key(self):
        new_api_key = simpledialog.askstring("Groq API Key", "Ingrese su API key de Groq:", show='*')
        if new_api_key:
            self.groq_api_key = new_api_key
            self.groq_client = Groq(api_key=self.groq_api_key)
            self.save_groq_api_key_to_registry(new_api_key)
            self.log_message("API key de Groq actualizada.")
        else:
            self.groq_api_key = None
            self.groq_client = None
            self.log_message("API key de Groq eliminada.")
        self.update_api_status_indicators()
        self.check_service_availability()

    def create_system_tray_icon(self):
        image = self.create_icon_image("blue")
        menu = pystray.Menu(
            pystray.MenuItem('Mostrar', self.show_window),
            pystray.MenuItem('Salir', self.quit_window)
        )
        self.icon = pystray.Icon("name", image, "Transcription App", menu)
        threading.Thread(target=self.icon.run, daemon=True).start()

    def create_icon_image(self, color):
        return Image.new('RGB', (64, 64), color=color)

    def show_window(self):
        self.root.deiconify()
        self.root.lift()

    def quit_window(self):
        self.icon.stop()
        self.root.quit()

    def on_closing(self):
        self.root.withdraw()
        return "break"

    def toggle_log(self):
        if self.log_visible:
            self.log_frame.pack_forget()
            self.toggle_log_button.config(text="Mostrar Log")
            self.root.geometry("400x350")
        else:
            self.log_frame.pack(fill=tk.BOTH, expand=True)
            self.toggle_log_button.config(text="Ocultar Log")
            self.root.geometry("400x500")
        self.log_visible = not self.log_visible

    def toggle_recording_hotkey(self):
        if self.recording:
            self.stop_recording()
        else:
            self.start_recording()

if __name__ == "__main__":
    root = tk.Tk()
    app = TranscriptionApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()