import importlib.util
import sys
import subprocess
import pkg_resources

def check_dependencies():
    """Verifica las dependencias requeridas e intenta instalarlas si faltan."""
    required_packages = [
        'pyaudio',
        'wave',
        'pyperclip',
        'groq',
        'pystray',
        'Pillow',  # Para PIL
        'keyboard',
        'SpeechRecognition'  # Opcional para Google service
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            pkg_resources.require(package)
        except (pkg_resources.DistributionNotFound, pkg_resources.VersionConflict):
            missing_packages.append(package)
    
    if missing_packages:
        print("Faltan las siguientes dependencias:")
        for pkg in missing_packages:
            print(f"- {pkg}")
        
        try:
            print("\nIntentando instalar dependencias faltantes...")
            subprocess.check_call([sys.executable, "-m", "pip", "install"] + missing_packages)
            print("Dependencias instaladas exitosamente!")
        except subprocess.CalledProcessError as e:
            print(f"\nError al instalar dependencias: {e}")
            print("\nPor favor, instale manualmente las dependencias faltantes usando:")
            print(f"pip install {' '.join(missing_packages)}")
            sys.exit(1)

# Verificar dependencias antes de importar
if __name__ == "__main__":
    check_dependencies()

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
        self.root.resizable(False, False)

        # Estado de la aplicación
        self.recording = False
        self.always_on_top = False
        self.service = "Whisper (Groq)"
        self.log_visible = True
        self.minimized = False  # Estado del modo minimizado

        # Inicialización de la API de Groq
        self.groq_api_key = self.get_groq_api_key_from_registry()
        self.groq_client = Groq(api_key=self.groq_api_key) if self.groq_api_key else None

        # Crear elementos de la interfaz
        self.create_widgets()
        self.check_service_availability()

        # Crear icono en la bandeja del sistema
        self.create_system_tray_icon()

        # Configurar hotkeys
        keyboard.add_hotkey('ctrl+alt+n', self.toggle_recording_hotkey)

        # Mostrar el log inicialmente
        self.log_frame.pack(fill=tk.BOTH, expand=True)

    def get_groq_api_key_from_registry(self):
        """Obtiene la API key de Groq desde el registro de Windows."""
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"SOFTWARE\TranscriptionApp", 0, winreg.KEY_READ)
            value, _ = winreg.QueryValueEx(key, "GroqApiKey")
            winreg.CloseKey(key)
            return value
        except WindowsError:
            return None

    def save_groq_api_key_to_registry(self, api_key):
        """Guarda la API key de Groq en el registro de Windows."""
        try:
            key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"SOFTWARE\TranscriptionApp")
            winreg.SetValueEx(key, "GroqApiKey", 0, winreg.REG_SZ, api_key)
            winreg.CloseKey(key)
        except WindowsError as e:
            messagebox.showerror("Error", f"No se pudo guardar la API key en el registro: {e}")

    def create_widgets(self):
        """Crea y organiza todos los widgets de la interfaz."""
        self.main_frame = tk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # Frame superior para controles principales
        self.top_frame = tk.Frame(self.main_frame)
        self.top_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=10)

        # Botón de inicio/detención de grabación
        self.start_button = tk.Button(self.top_frame, text="Iniciar Grabación", command=self.toggle_recording, width=20, height=2)
        self.start_button.pack(pady=5)

        # Botón para mantener siempre visible
        self.always_on_top_button = tk.Button(self.top_frame, text="Siempre Visible: Apagado", command=self.toggle_always_on_top)
        self.always_on_top_button.pack(pady=5)

        # Etiqueta de estado
        self.status_label = tk.Label(self.top_frame, text="Estado: Inactivo")
        self.status_label.pack(pady=5)

        # Selección de servicio de transcripción
        self.service_label = tk.Label(self.top_frame, text="Selecciona el servicio de transcripción:")
        self.service_label.pack(pady=5)

        self.service_var = tk.StringVar(value="Whisper (Groq)")
        self.service_radio_whisper = tk.Radiobutton(
            self.top_frame, text="Whisper (Groq)", variable=self.service_var,
            value="Whisper (Groq)", command=self.change_service
        )
        self.service_radio_whisper.pack(anchor='w')

        self.service_radio_google = tk.Radiobutton(
            self.top_frame, text="Google", variable=self.service_var,
            value="Google", command=self.change_service
        )
        self.service_radio_google.pack(anchor='w')

        # Botón para mostrar/ocultar el log
        self.toggle_log_button = tk.Button(self.top_frame, text="Ocultar Log", command=self.toggle_log)
        self.toggle_log_button.pack(pady=5)

        # Botón para alternar entre modo normal y minimizado
        self.toggle_mode_button = tk.Button(self.top_frame, text="Modo Minimizado", command=self.toggle_mode)
        self.toggle_mode_button.pack(pady=5)

        # Frame para el log
        self.log_frame = tk.Frame(self.main_frame)
        self.log_text = scrolledtext.ScrolledText(self.log_frame, wrap=tk.WORD, state="disabled", height=10)
        self.log_text.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        # Frame inferior
        self.bottom_frame = tk.Frame(self.main_frame)
        self.bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=10)

        # Botón para cambiar la API key de Groq
        self.change_api_key_button = tk.Button(self.bottom_frame, text="Cambiar API Key de Groq", command=self.change_groq_api_key)
        self.change_api_key_button.pack(side=tk.LEFT, padx=5)

        # Indicadores de estado de las APIs
        self.api_status_frame = tk.Frame(self.bottom_frame)
        self.api_status_frame.pack(side=tk.RIGHT, padx=5)

        self.groq_status_label = tk.Label(self.api_status_frame, text="Groq API:")
        self.groq_status_label.pack(side=tk.LEFT)

        self.groq_status_indicator = tk.Canvas(self.api_status_frame, width=15, height=15)
        self.groq_status_indicator.pack(side=tk.LEFT, padx=(5, 10))

        self.google_status_label = tk.Label(self.api_status_frame, text="Google API:")
        self.google_status_label.pack(side=tk.LEFT)

        self.google_status_indicator = tk.Canvas(self.api_status_frame, width=15, height=15)
        self.google_status_indicator.pack(side=tk.LEFT, padx=5)

        # Información del micrófono
        self.mic_label = tk.Label(self.top_frame, text="Micrófono en uso: Desconocido")
        self.mic_label.pack(pady=5)
        self.update_mic_info()

        # Frame esencial para modo minimizado
        self.minimized_frame = tk.Frame(self.main_frame)
        # En modo minimizado, solo este frame será visible
        self.minimized_start_button = tk.Button(self.minimized_frame, text="Iniciar Grabación", command=self.toggle_recording, width=15, height=1)
        self.minimized_start_button.pack(pady=5)

        self.minimized_status_frame = tk.Frame(self.minimized_frame)
        self.minimized_status_frame.pack(pady=5)

        self.minimized_groq_status_indicator = tk.Canvas(self.minimized_status_frame, width=10, height=10)
        self.minimized_groq_status_indicator.pack(side=tk.LEFT, padx=2)
        self.minimized_groq_status_label = tk.Label(self.minimized_status_frame, text="G")
        self.minimized_groq_status_label.pack(side=tk.LEFT)

        self.minimized_google_status_indicator = tk.Canvas(self.minimized_status_frame, width=10, height=10)
        self.minimized_google_status_indicator.pack(side=tk.LEFT, padx=2)
        self.minimized_google_status_label = tk.Label(self.minimized_status_frame, text="G")
        self.minimized_google_status_label.pack(side=tk.LEFT)

    def update_mic_info(self):
        """Actualiza la información del micrófono en uso."""
        try:
            p = pyaudio.PyAudio()
            default_mic = p.get_default_input_device_info()
            mic_name = default_mic['name']
            self.mic_label.config(text=f"Micrófono en uso: {mic_name}")
            p.terminate()
        except Exception as e:
            self.mic_label.config(text="Micrófono en uso: Error al obtener información")
            self.log_message(f"Error al obtener información del micrófono: {e}")

    def update_api_status_indicators(self):
        """Actualiza los indicadores de estado de las APIs de Groq y Google."""
        # Indicador de Groq
        self.groq_status_indicator.delete("all")
        self.minimized_groq_status_indicator.delete("all")
        if self.groq_client:
            color = "green"
        elif self.groq_api_key is None:
            color = "gray"
        else:
            color = "red"
        self.groq_status_indicator.create_oval(2, 2, 13, 13, fill=color, outline="")
        self.minimized_groq_status_indicator.create_oval(2, 2, 9, 9, fill=color, outline="")

        # Indicador de Google
        self.google_status_indicator.delete("all")
        self.minimized_google_status_indicator.delete("all")
        color = "green" if google_service_available else "red"
        self.google_status_indicator.create_oval(2, 2, 13, 13, fill=color, outline="")
        self.minimized_google_status_indicator.create_oval(2, 2, 9, 9, fill=color, outline="")

    def log_message(self, message):
        """Añade un mensaje al log."""
        self.log_text.config(state="normal")
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.config(state="disabled")
        self.log_text.see(tk.END)

    def check_service_availability(self):
        """Verifica la disponibilidad de los servicios de transcripción."""
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
        """Alterna el estado de grabación."""
        if self.recording:
            self.stop_recording()
        else:
            self.start_recording()

    def start_recording(self):
        """Inicia la grabación de audio."""
        self.recording = True
        self.status_label.config(text="Estado: Grabando...")
        self.start_button.config(text="Detener Grabación")
        self.minimized_start_button.config(text="Detener Grabación")
        self.log_message("Grabación iniciada.")
        self.icon.icon = self.create_icon_image("red")
        threading.Thread(target=self.record_audio, daemon=True).start()

    def stop_recording(self):
        """Detiene la grabación de audio."""
        self.recording = False
        self.status_label.config(text="Estado: Inactivo")
        self.start_button.config(text="Iniciar Grabación")
        self.minimized_start_button.config(text="Iniciar Grabación")
        self.log_message("Grabación detenida.")
        self.icon.icon = self.create_icon_image("blue")

    def toggle_always_on_top(self):
        """Alterna la opción de mantener la ventana siempre visible."""
        self.always_on_top = not self.always_on_top
        self.root.attributes("-topmost", self.always_on_top)
        estado = "Encendido" if self.always_on_top else "Apagado"
        self.always_on_top_button.config(text=f"Siempre Visible: {estado}")
        self.log_message(f"Siempre Visible: {estado}")

    def change_service(self):
        """Cambia el servicio de transcripción seleccionado."""
        self.service = self.service_var.get()
        self.log_message(f"Servicio de transcripción cambiado a: {self.service}")

    def record_audio(self):
        """Graba el audio desde el micrófono y lo envía para transcripción."""
        p = pyaudio.PyAudio()
        try:
            stream = p.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=1024)
        except Exception as e:
            self.log_message(f"Error al abrir el micrófono: {e}")
            self.stop_recording()
            return

        frames = []

        while self.recording:
            try:
                data = stream.read(1024)
                frames.append(data)
            except Exception as e:
                self.log_message(f"Error durante la grabación: {e}")
                break

        stream.stop_stream()
        stream.close()
        p.terminate()

        audio_data = b''.join(frames)
        self.log_message("Audio grabado, iniciando transcripción...")

        if self.service == "Whisper (Groq)":
            self.transcribe_with_whisper_groq(audio_data)
        elif self.service == "Google":
            self.transcribe_with_google(io.BytesIO(audio_data))
        else:
            self.log_message("Servicio de transcripción no reconocido.")

    def transcribe_with_google(self, audio_data):
        """Transcribe el audio utilizando Google Cloud Speech-to-Text."""
        recognizer = sr.Recognizer()
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp_audio:
                wf = wave.open(temp_audio.name, 'wb')
                wf.setnchannels(1)
                wf.setsampwidth(pyaudio.PyAudio().get_sample_size(pyaudio.paInt16))
                wf.setframerate(16000)
                wf.writeframes(audio_data.read())
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
        """Transcribe el audio utilizando Whisper de Groq."""
        if not self.groq_client:
            self.log_message("Advertencia: API key de Groq no proporcionada. La transcripción puede no ser posible.")
            return

        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp_audio:
                wf = wave.open(temp_audio.name, 'wb')
                wf.setnchannels(1)
                wf.setsampwidth(2)  # 16 bits
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

            os.unlink(temp_audio.name)

            # Procesar la respuesta de la API
            transcribed_text = transcription.get('text') if isinstance(transcription, dict) else getattr(transcription, 'text', None)

            if not transcribed_text:
                raise ValueError("No se pudo encontrar el texto transcrito en la respuesta de la API")

            transcribed_text = self.format_transcription(transcribed_text)
            pyperclip.copy(transcribed_text)
            self.log_message(f"Transcripción con Whisper (Groq): {transcribed_text}")
            self.icon.icon = self.create_icon_image("green")
            self.paste_transcription()
        except Exception as e:
            error_msg = f"Error de Transcripción con Whisper (Groq): {e}"
            self.log_message(error_msg)

    def format_transcription(self, text):
        """
        Formatea el texto de transcripción:
        - Elimina espacios al inicio y al final.
        - Elimina un punto al final si existe.
        - Mantiene la capitalización original.
        """
        text = text.strip()
        if text.endswith('.'):
            text = text[:-1]
        return text

    def paste_transcription(self):
        """Pega el texto transcrito en la ubicación actual del cursor."""
        keyboard.press_and_release('ctrl+v')

    def change_groq_api_key(self):
        """Permite al usuario cambiar la API key de Groq."""
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
        """Crea y configura el icono de la bandeja del sistema."""
        image = self.create_icon_image("blue")
        menu = pystray.Menu(
            pystray.MenuItem('Mostrar', self.show_window),
            pystray.MenuItem('Salir', self.quit_window)
        )
        self.icon = pystray.Icon("TranscriptionApp", image, "Transcription App", menu)
        threading.Thread(target=self.icon.run, daemon=True).start()

    def create_icon_image(self, color):
        """Crea una imagen simple para el icono de la bandeja del sistema."""
        img = Image.new('RGB', (64, 64), color=color)
        return img

    def show_window(self, icon=None, item=None):
        """Muestra la ventana principal de la aplicación."""
        self.root.deiconify()
        self.root.lift()
        self.root.attributes("-topmost", True)
        self.root.after_idle(self.root.attributes, "-topmost", False)

    def quit_window(self, icon=None, item=None):
        """Cierra la aplicación."""
        self.icon.stop()
        self.root.quit()

    def on_closing(self):
        """Maneja el evento de cierre de la ventana principal."""
        self.root.withdraw()

    def toggle_log(self):
        """Alterna la visibilidad del log."""
        if self.log_visible:
            self.log_frame.pack_forget()
            self.toggle_log_button.config(text="Mostrar Log")
            if not self.minimized:
                self.root.geometry("400x350")
        else:
            self.log_frame.pack(fill=tk.BOTH, expand=True)
            self.toggle_log_button.config(text="Ocultar Log")
            if not self.minimized:
                self.root.geometry("400x500")
        self.log_visible = not self.log_visible

    def toggle_recording_hotkey(self):
        """Alterna la grabación cuando se presiona el hotkey."""
        self.toggle_recording()

    def toggle_mode(self):
        """Alterna entre modo normal y modo minimizado."""
        if not self.minimized:
            # Cambiar a modo minimizado
            self.log_frame.pack_forget()
            self.service_label.pack_forget()
            self.service_radio_whisper.pack_forget()
            self.service_radio_google.pack_forget()
            self.toggle_log_button.pack_forget()
            self.mic_label.pack_forget()
            self.change_api_key_button.pack_forget()
            self.api_status_frame.pack_forget()

            self.minimized_frame.pack(fill=tk.BOTH, expand=True)

            self.root.geometry("200x100")
            self.root.attributes("-topmost", True)

            self.toggle_mode_button.config(text="Modo Normal")
            self.minimized = True
        else:
            # Cambiar a modo normal
            self.minimized_frame.pack_forget()

            self.service_label.pack(pady=5)
            self.service_radio_whisper.pack(anchor='w')
            self.service_radio_google.pack(anchor='w')
            self.toggle_log_button.pack(pady=5)
            self.mic_label.pack(pady=5)
            self.change_api_key_button.pack(side=tk.LEFT, padx=5)
            self.api_status_frame.pack(side=tk.RIGHT, padx=5)

            if self.log_visible:
                self.log_frame.pack(fill=tk.BOTH, expand=True)

            self.root.geometry("400x500")
            self.root.attributes("-topmost", self.always_on_top)

            self.toggle_mode_button.config(text="Modo Minimizado")
            self.minimized = False

    def update_minimized_status(self):
        """Actualiza los indicadores de estado en modo minimizado."""
        # Actualizar indicadores de Groq
        self.minimized_groq_status_indicator.delete("all")
        if self.groq_client:
            color = "green"
        elif self.groq_api_key is None:
            color = "gray"
        else:
            color = "red"
        self.minimized_groq_status_indicator.create_oval(2, 2, 9, 9, fill=color, outline="")

        # Actualizar indicadores de Google
        self.minimized_google_status_indicator.delete("all")
        color = "green" if google_service_available else "red"
        self.minimized_google_status_indicator.create_oval(2, 2, 9, 9, fill=color, outline="")

if __name__ == "__main__":
    root = tk.Tk()
    app = TranscriptionApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()
