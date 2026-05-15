# DictarApp 0.5

Dictado por voz → texto pegado donde tengas el cursor, en Windows.
Tres backends: **Whisper en Groq** (rápido, nube), **Google** (gratuito, online) y **Whisper local** (offline, privado, con GPU opcional).

## Instalación + uso (recomendado)

**Doble click en `Dictar.bat`.** Eso es todo.

La primera vez crea automáticamente `.venv\`, instala `requirements.txt` y arranca la app. En arranques posteriores solo lanza la GUI (sin consola visible). Si `requirements.txt` cambia, detecta la diferencia por fecha y reinstala solo en ese caso.

- **`Dictar.bat`** — uso normal, silencioso. Ideal para acceso directo en escritorio o `shell:startup` para auto-arranque.
- **`Dictar (debug).bat`** — igual pero deja la consola abierta para ver logs/errores. Úsalo si algo falla.

Requiere Python 3.10+ instalado y en PATH (https://www.python.org/downloads/).

### Instalación manual (alternativa)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
.\.venv\Scripts\python.exe DictarApp.py
```

> `pyaudio` en Windows requiere las "Microsoft C++ Build Tools" o instalar la wheel pre-compilada (`pip install pipwin && pipwin install pyaudio`). Si igual falla, la app cae automáticamente a `sounddevice` y como último recurso a `ffmpeg`.

## Uso de la app

1. La app auto-asigna el micrófono default del sistema (el que toma cualquier app); si tenés otro, elegilo en el combobox **Cambiar:**.
2. Mientras hablás, la barra y el dot verde reaccionan en vivo al nivel de voz.
3. Pestaña **Configuración**: pegá tu Groq API Key (se cifra con DPAPI vía `keyring`). Cambiá el atajo si querés (default `Ctrl+Alt+N`).
4. Pestaña **General**: elegí el servicio de transcripción.
5. Poné el cursor donde quieras dictar y presioná **Ctrl+Alt+N**.
6. Vuelve a presionar para detener; el texto se pega automáticamente. El icono del tray pulsa con tu voz mientras grabás.

## Backends

| Backend            | Modelo          | Internet | Privacidad | Latencia       |
|--------------------|-----------------|----------|------------|----------------|
| Whisper (Groq)     | whisper-large-v3| Sí       | Cloud      | rápido         |
| Google             | endpoint público| Sí       | Cloud      | medio          |
| Whisper local      | tiny → large-v3 | No       | Local      | depende del HW |

Para el local: la 1ra vez descarga el modelo (~50 MB el `tiny`, ~3 GB el `large-v3`) y lo cachea en `~/.cache/huggingface/`.

### GPU (opcional)

Si tenés NVIDIA y `device='cuda'` en la UI, la app intenta usar la GPU. Si las DLLs de CUDA 12 no están en el sistema (`cublas64_12.dll`/`cudnn`), **se reintenta automáticamente en CPU con int8** sin que tengas que hacer nada. Para que la GPU funcione directo, instalá los runtimes:

```powershell
.\.venv\Scripts\pip install nvidia-cublas-cu12 nvidia-cudnn-cu12
```

## Diagnóstico

La ventana de log se abre automáticamente al arrancar. Tiene dos pestañas:
- **Eventos**: trazas detalladas de cada paso (`[REC]`, `[TX]`, `[local-whisper]`, `[DELIVER]`) con tracebacks completos en errores.
- **Transcripciones**: histórico de lo dictado.

Botón **Copiar todo** para volcar todo al portapapeles si necesitás reportar un bug.

## Estructura

```
Dictar.bat              # launcher (doble click → arranca silencioso, auto-instala deps)
Dictar (debug).bat      # launcher con consola visible (debug)
DictarApp.py            # entry point
requirements.txt
dictapp/
  ├── app.py            # orquestador
  ├── config.py         # settings.json + keyring
  ├── audio.py          # PyAudio recorder + enumeración curada de mics
  ├── audio_sd.py       # sounddevice recorder + VU live meter (single-stream)
  ├── audio_ffmpeg.py   # último fallback con ffmpeg/dshow
  ├── theme.py          # tema oscuro ttk
  ├── tray.py           # icono de bandeja con feedback de nivel
  ├── hotkeys.py        # hotkeys globales
  ├── main_window.py    # UI principal
  ├── log_window.py     # ventana flotante con eventos + transcripciones
  ├── whats_new.py      # popup de novedades
  ├── version.py
  └── transcribers/
      ├── base.py
      ├── groq_whisper.py
      ├── google_sr.py
      └── local_whisper.py
```

## Datos y secretos

- Preferencias: `%APPDATA%/DictarApp/settings.json`.
- API key de Groq: `keyring` (Windows Credential Manager / DPAPI).
- La 1ra vez migra automáticamente la key del registro viejo (`HKCU\SOFTWARE\TranscriptionApp\GroqApiKey`).
