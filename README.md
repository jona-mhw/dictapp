# DictarApp 0.4

Dictado por voz → texto pegado donde tengas el cursor, en Windows.
Tres backends: **Whisper en Groq** (rápido, nube), **Google** (gratuito, online) y **Whisper local** (offline, privado, con GPU opcional).

## Instalación

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

> `pyaudio` en Windows requiere las "Microsoft C++ Build Tools" o instalar la wheel pre-compilada (`pip install pipwin && pipwin install pyaudio`).

## Uso

```bash
python DictarApp.py
```

1. Abre la pestaña **Configuración** y guarda tu Groq API Key (se cifra con DPAPI vía `keyring`).
2. En **General** elige el servicio de transcripción.
3. Pon el cursor donde quieras dictar y presiona **Ctrl+Alt+N** (configurable).
4. Vuelve a presionar el atajo para detener; el texto se pega automáticamente.

## Backends

| Backend            | Modelo          | Internet | Privacidad | Latencia |
|--------------------|-----------------|----------|------------|----------|
| Whisper (Groq)     | whisper-large-v3| Sí       | Cloud      | ~rápido  |
| Google             | endpoint público| Sí       | Cloud      | medio    |
| Whisper local      | tiny → large-v3 | No       | Local      | depende  |

Para el local: la 1ra vez descarga el modelo (~50 MB el `tiny`, ~3 GB el `large-v3`) y lo cachea en `~/.cache/huggingface/`. Si tienes GPU NVIDIA, en **Configuración** pon `device = cuda` y prueba `medium`.

## Estructura

```
DictarApp.py            # entry point
requirements.txt
dictapp/
  ├── app.py            # orquestador
  ├── config.py         # settings.json + keyring
  ├── audio.py          # grabación, VAD, mic
  ├── theme.py          # tema oscuro ttk
  ├── tray.py           # icono de bandeja
  ├── hotkeys.py        # hotkeys globales
  ├── main_window.py    # UI
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
