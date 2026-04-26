"""Orquestador: une config + audio + transcribers + UI + tray + hotkeys."""
from __future__ import annotations

import threading
import time
import tkinter as tk

import pyperclip

from . import audio as audio_mod
from . import whats_new
from .audio_sd import SDRecorder, SDMeterScanner, SD_AVAILABLE
from .audio_ffmpeg import (
    FFmpegRecorder,
    FFMPEG_AVAILABLE,
    find_ffmpeg,
    list_dshow_input_devices,
)
from .config import Config, KEYRING_OK
from .hotkeys import HotkeyManager, KEYBOARD_AVAILABLE
from .log_window import LogWindow
from .main_window import MainWindow
from .theme import apply_dark_theme
from .tray import TrayIcon, TRAY_AVAILABLE
from .transcribers import (
    GROQ_AVAILABLE,
    GOOGLE_AVAILABLE,
    LOCAL_AVAILABLE,
    GoogleTranscriber,
    GroqWhisperTranscriber,
    LocalWhisperTranscriber,
    Transcriber,
    TranscriptionError,
)
from .version import VERSION


class App:
    def __init__(self) -> None:
        self.config = Config()
        self.root = tk.Tk()
        apply_dark_theme(self.root)

        self.recorder = audio_mod.AudioRecorder(
            mic_index=int(self.config.get("mic_index", -1)),
            log_fn=lambda m: self._log(m),
        )
        # backup recorder con sounddevice
        self.sd_recorder: SDRecorder | None = None
        if SD_AVAILABLE:
            self.sd_recorder = SDRecorder(
                mic_index=int(self.config.get("mic_index", -1)),
                log_fn=lambda m: self._log(m),
            )
        # último recurso: ffmpeg (cuando AV/EDR bloquea Win32 audio APIs)
        self.ff_recorder: FFmpegRecorder | None = None
        if FFMPEG_AVAILABLE:
            self.ff_recorder = FFmpegRecorder(
                device_name=self.config.get("ffmpeg_device") or None,
                log_fn=lambda m: self._log(m),
            )
        # qué backend está activo (alterna a sd / ffmpeg si pyaudio falla)
        self._backend: str = "pyaudio"  # "pyaudio" | "sd" | "ffmpeg"
        self.hotkey = HotkeyManager()

        # transcribers
        self.groq = GroqWhisperTranscriber(api_key=self.config.get_groq_key())
        self.google = GoogleTranscriber()
        self.local = LocalWhisperTranscriber(
            model_size=self.config.get("local_model"),
            device=self.config.get("local_device"),
            compute_type=self.config.get("local_compute_type"),
        )

        # log window flotante
        self.log_window = LogWindow(self.root)

        # UI
        self.window = MainWindow(
            self.root,
            self.config,
            on_toggle_recording=self.toggle_recording,
            on_change_service=self.change_service,
            on_change_groq_key=self.change_groq_key,
            on_change_hotkey=self.change_hotkey,
            on_change_local_model=self.change_local_model,
            on_change_local_device=self.change_local_device,
            on_change_mic=self.change_mic,
            on_change_setting=self.change_setting,
            on_warm_up_local=self.warm_up_local,
            on_toggle_log=self.toggle_log,
            on_change_ffmpeg_device=self.change_ffmpeg_device,
            list_ffmpeg_devices=list_dshow_input_devices,
            on_close=self.on_window_close,
        )
        # inyectar el sumidero de log
        self.window.log = self._log  # type: ignore[method-assign]

        # tray
        self.tray = TrayIcon(
            on_show=self.window.show_window,
            on_quit=self.quit,
            on_toggle=self.toggle_recording,
        )
        self.tray.start()

        self._log_initial_status()
        self._register_hotkey()

        # popup what's new si versión cambió
        if whats_new.should_show(self.config.get("last_seen_version", "")):
            self.root.after(250, self._show_whats_new)

    # ---------------------------------------------------------- logging
    def _log(self, message: str) -> None:
        self.root.after(0, self.log_window.log_event, message)

    def toggle_log(self) -> None:
        self.log_window.toggle()
        # actualizar texto del botón
        try:
            self.window.log_btn.config(
                text="Ocultar log" if self.log_window.is_open else "Mostrar log"
            )
        except Exception:
            pass

    # ---------------------------------------------------------- arranque
    def _log_initial_status(self) -> None:
        self.window.log(f"DictarApp {VERSION} listo.")
        if not KEYRING_OK:
            self.window.log("⚠ keyring no disponible — instala 'keyring' para guardar la API key cifrada.")
        if not KEYBOARD_AVAILABLE:
            self.window.log("⚠ módulo 'keyboard' no disponible — sin hotkeys globales.")
        if not TRAY_AVAILABLE:
            self.window.log("⚠ pystray/Pillow no disponibles — sin icono en bandeja.")
        if not GROQ_AVAILABLE:
            self.window.log("• Groq SDK no instalado.")
        if not GOOGLE_AVAILABLE:
            self.window.log("• SpeechRecognition no instalado (backend Google).")
        if not LOCAL_AVAILABLE:
            self.window.log("• faster-whisper no instalado (backend local).")
        if SD_AVAILABLE:
            self.window.log("Backend de audio: sounddevice disponible.")
        else:
            self.window.log("Backend de audio: PyAudio (sounddevice no instalado).")
        if FFMPEG_AVAILABLE:
            self.window.log(f"Backend de audio: ffmpeg disponible en {find_ffmpeg()} (último recurso para entornos con AV/EDR).")
        else:
            self.window.log("Backend de audio: ffmpeg NO encontrado (último fallback no disponible).")
        # diagnóstico de audio
        try:
            self.window.log("Audio: " + audio_mod.host_apis_summary())
            for d in audio_mod.list_input_devices():
                tag = " [DEFAULT]" if d.is_default else ""
                self.window.log(
                    f"  mic#{d.index} hostApi={d.host_api_name!r}({d.host_api}) "
                    f"ch={d.max_input_channels} rate={d.default_sample_rate} {d.name!r}{tag}"
                )
        except Exception as e:
            self.window.log(f"No se pudo enumerar audio: {e}")

        # devices DirectShow vistos por ffmpeg
        if FFMPEG_AVAILABLE:
            try:
                ff_devs = list_dshow_input_devices()
                self.window.log(f"ffmpeg/dshow ve {len(ff_devs)} devices de audio:")
                for d in ff_devs:
                    self.window.log(f"  - {d.name!r}")
                # autoconfigurar si no hay device elegido
                if not self.config.get("ffmpeg_device") and ff_devs:
                    self.config.set("ffmpeg_device", ff_devs[0].name)
                    if self.ff_recorder is not None:
                        self.ff_recorder.device_name = ff_devs[0].name
                    self.window.log(f"ffmpeg device por defecto: {ff_devs[0].name!r}")
            except Exception as e:
                self.window.log(f"No se pudo enumerar devices de ffmpeg: {e}")
        self._refresh_service_status()

    def _show_whats_new(self) -> None:
        try:
            whats_new.show(self.root)
        except Exception as e:
            self.window.log(f"No se pudo mostrar 'What's New': {e}")
        self.config.set("last_seen_version", VERSION)

    def _register_hotkey(self) -> None:
        ok, msg = self.hotkey.register(self.config.get("hotkey"), self.toggle_recording)
        self.window.log(msg)

    # ---------------------------------------------------------- transcribers
    def _current_transcriber(self) -> Transcriber:
        svc = self.config.get("service")
        if svc == "Google":
            return self.google
        if svc == "Whisper local":
            return self.local
        return self.groq

    def _refresh_service_status(self) -> None:
        t = self._current_transcriber()
        ok, msg = t.is_ready()
        prefix = "✓" if ok else "✗"
        # versión corta para el footer, completa al log si hay error
        short = msg if len(msg) <= 60 else msg[:57] + "…"
        self.window.set_service_status(f"{prefix} {t.name}: {short}")
        if not ok and len(msg) > 60:
            self.window.log(f"[{t.name}] {msg}")

    # ---------------------------------------------------------- callbacks UI
    def change_service(self, service: str) -> None:
        self.config.set("service", service)
        self.window.log(f"Servicio: {service}")
        self._refresh_service_status()

    def change_groq_key(self, key: Optional[str]) -> None:
        try:
            self.config.set_groq_key(key)
        except Exception as e:
            self.window.log(f"No se pudo guardar la API key: {e}")
            return
        self.groq = GroqWhisperTranscriber(api_key=key)
        if key:
            self.window.log("API key de Groq guardada (cifrada con DPAPI).")
        else:
            self.window.log("API key de Groq eliminada.")
        self._refresh_service_status()

    def change_hotkey(self, combo: str) -> tuple[bool, str]:
        if not combo:
            return False, "Hotkey vacío."
        ok, msg = self.hotkey.register(combo, self.toggle_recording)
        if ok:
            self.config.set("hotkey", combo)
        return ok, msg

    def change_local_model(self, model: str) -> None:
        self.config.set("local_model", model)
        self.local = LocalWhisperTranscriber(
            model_size=model,
            device=self.config.get("local_device"),
            compute_type=self.config.get("local_compute_type"),
        )
        self.window.log(f"Modelo local seleccionado: {model}")
        self._refresh_service_status()

    def change_local_device(self, device: str) -> None:
        self.config.set("local_device", device)
        self.local = LocalWhisperTranscriber(
            model_size=self.config.get("local_model"),
            device=device,
            compute_type=self.config.get("local_compute_type"),
        )
        self.window.log(f"Device local: {device}")
        self._refresh_service_status()

    def change_ffmpeg_device(self, name: str) -> None:
        if not name or name.startswith("("):
            return
        self.config.set("ffmpeg_device", name)
        if self.ff_recorder is not None:
            self.ff_recorder.device_name = name
        self.window.log(f"ffmpeg device: {name!r}")

    def change_mic(self, index: int) -> None:
        self.config.set("mic_index", index)
        self.recorder.mic_index = index
        if self.sd_recorder is not None:
            self.sd_recorder.mic_index = index
        self.window.log(f"Micrófono: index={index}")

    def change_setting(self, key: str, value: object) -> None:
        self.config.set(key, value)
        self.window.log(f"{key} = {value}")

    def warm_up_local(self) -> None:
        if not LOCAL_AVAILABLE:
            self.window.log("faster-whisper no instalado.")
            return
        self.window.log(f"Cargando modelo local '{self.config.get('local_model')}'…")

        def worker():
            try:
                self.local.warm_up()
                self.window.log("Modelo local listo.")
            except Exception as e:
                self.window.log(f"Error cargando modelo: {e}")
            self._refresh_service_status()
        threading.Thread(target=worker, daemon=True).start()

    # ---------------------------------------------------------- grabación
    def toggle_recording(self) -> None:
        rec = self._active_recorder()
        if rec.recording:
            self.stop_recording_and_transcribe()
        else:
            self.start_recording()

    def _active_recorder(self):
        if self._backend == "ffmpeg" and self.ff_recorder:
            return self.ff_recorder
        if self._backend == "sd" and self.sd_recorder:
            return self.sd_recorder
        return self.recorder

    def _try_start_chain(self) -> tuple[object, str] | None:
        """Intenta arrancar pyaudio → sd → ffmpeg. Devuelve (recorder, backend) o None."""
        # 1) pyaudio
        self.recorder.start()
        if not self.recorder.error:
            return (self.recorder, "pyaudio")
        self.window.log("PyAudio no pudo abrir el mic, intento con sounddevice…")

        # 2) sounddevice
        if self.sd_recorder is not None:
            self.sd_recorder.mic_index = self.recorder.mic_index
            self.sd_recorder.start()
            if not self.sd_recorder.error:
                return (self.sd_recorder, "sd")
            self.window.log("sounddevice tampoco abrió el mic, intento con ffmpeg…")

        # 3) ffmpeg
        if self.ff_recorder is not None:
            # si no hay device configurado, intentar autodetectar el más probable
            if not self.ff_recorder.device_name:
                devs = list_dshow_input_devices()
                if devs:
                    chosen = devs[0]
                    self.ff_recorder.device_name = chosen.name
                    self.config.set("ffmpeg_device", chosen.name)
                    self.window.log(f"ffmpeg device autoseleccionado: {chosen.name!r}")
            self.ff_recorder.start()
            if not self.ff_recorder.error:
                return (self.ff_recorder, "ffmpeg")

        return None

    def start_recording(self) -> None:
        t = self._current_transcriber()
        ok, msg = t.is_ready()
        if not ok:
            self.window.log(f"No se puede grabar: {msg}")
            self.window.set_status(f"Error: {msg}", color="err")
            return
        self.window.stop_mic_meter()
        time.sleep(0.25)

        result = self._try_start_chain()
        if result is None:
            errs = []
            if self.recorder.error:
                errs.append(f"pyaudio: {self.recorder.error}")
            if self.sd_recorder and self.sd_recorder.error:
                errs.append(f"sd: {self.sd_recorder.error}")
            if self.ff_recorder and self.ff_recorder.error:
                errs.append(f"ffmpeg: {self.ff_recorder.error}")
            self.window.log("Ningún backend pudo abrir el mic. " + " | ".join(errs))
            self.window.set_status("Error", color="err")
            self.tray.set_state("error")
            return

        rec, backend = result
        self._backend = backend
        self.window.set_recording_button(True)
        self.window.set_status("Grabando…", color="err")
        self.tray.set_state("recording")
        self.window.log(f"Grabación iniciada ({backend}).")

    def stop_recording_and_transcribe(self) -> None:
        rec = self._active_recorder()
        pcm = rec.stop()
        self.window.set_recording_button(False)
        # restaurar VU meters tras dar tiempo a PortAudio a liberar
        self.root.after(600, self.window.refresh_microphones)
        if rec.error:
            self.window.log(rec.error)
        if not pcm:
            self.window.set_status("Sin audio", color="warn")
            self.tray.set_state("idle")
            return
        rate = rec.sample_rate
        seconds = audio_mod.duration_seconds(pcm, sample_rate=rate)
        self.window.log(f"Grabación detenida. {seconds:.1f}s capturados @ {rate} Hz.")

        if self.config.get("trim_silence"):
            pcm = audio_mod.trim_silence(pcm)

        self.window.set_status("Transcribiendo…", color="warn")
        self.tray.set_state("transcribing")
        threading.Thread(target=self._transcribe_worker, args=(pcm, rate), daemon=True).start()

    def _transcribe_worker(self, pcm: bytes, sample_rate: int) -> None:
        t = self._current_transcriber()
        try:
            with audio_mod.pcm_to_wav_temp(pcm, sample_rate=sample_rate) as wav_path:
                result = t.transcribe(wav_path, language=self.config.get("language", "es"))
        except TranscriptionError as e:
            self.window.log(f"Error: {e}")
            self.window.set_status("Error", color="err")
            self.tray.set_state("error")
            return
        except Exception as e:
            self.window.log(f"Error inesperado: {e}")
            self.window.set_status("Error", color="err")
            self.tray.set_state("error")
            return

        text = self._format(result.text)
        self.window.log(f"[{result.backend} · {result.seconds:.1f}s] {text}")
        self.root.after(0, self.log_window.log_transcript, text, result.backend, result.seconds)
        self._deliver(text)
        self.window.set_status(f"Listo ({result.seconds:.1f}s)", color="ok")
        self.tray.set_state("ok")

    @staticmethod
    def _format(text: str) -> str:
        text = (text or "").strip()
        # quitar punto final si parece una sola frase corta
        if text.endswith(".") and text.count(".") == 1:
            text = text[:-1]
        return text

    def _deliver(self, text: str) -> None:
        if not text:
            return
        try:
            pyperclip.copy(text)
        except Exception as e:
            self.window.log(f"No se pudo copiar al portapapeles: {e}")
            return
        if self.config.get("auto_paste"):
            try:
                self.hotkey.send_paste()
            except Exception as e:
                self.window.log(f"No se pudo auto-pegar: {e}")

    # ---------------------------------------------------------- ciclo de vida
    def on_window_close(self) -> None:
        # minimizar a tray si está disponible; si no, salir
        if TRAY_AVAILABLE:
            self.window.hide_window()
        else:
            self.quit()

    def quit(self) -> None:
        try:
            self.window.stop_mic_meter()
        except Exception:
            pass
        try:
            self.hotkey.unregister()
        except Exception:
            pass
        try:
            self.tray.stop()
        except Exception:
            pass
        try:
            self.root.quit()
            self.root.destroy()
        except Exception:
            pass

    def run(self) -> None:
        try:
            self.root.mainloop()
        finally:
            self.quit()
