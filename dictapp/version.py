APP_NAME = "DictarApp"
VERSION = "0.4.0"

WHATS_NEW = {
    "version": VERSION,
    "title": "DictarApp 0.4 — recargado",
    "tagline": "Más rápido, más seguro, ahora también offline.",
    "sections": [
        {
            "icon": "*",
            "title": "Whisper local (offline)",
            "items": [
                "Nuevo backend con faster-whisper: dicta sin internet y sin enviar audio a la nube.",
                "Modelos seleccionables: tiny / base / small / medium / large-v3.",
                "Auto-detecta CUDA si tienes GPU NVIDIA; cae a CPU con int8 si no.",
            ],
        },
        {
            "icon": "#",
            "title": "Claves seguras",
            "items": [
                "La API key de Groq ya no vive en texto plano en el registro.",
                "Ahora se guarda con keyring (DPAPI en Windows) y se migra automáticamente la primera vez.",
                "Se mantiene un settings.json para preferencias no sensibles.",
            ],
        },
        {
            "icon": "+",
            "title": "Audio mejorado",
            "items": [
                "Selector de micrófono en vivo (no más 'Desconocido').",
                "Recorte de silencios al inicio/final.",
                "Restaura tu portapapeles después del autopaste.",
                "Logging thread-safe (sin congelar la UI).",
            ],
        },
        {
            "icon": ">",
            "title": "UI nueva",
            "items": [
                "Tema oscuro con ttk, tipografía legible, layout en pestañas.",
                "Hotkey configurable desde la UI (default Ctrl+Alt+N).",
                "Indicadores de estado más claros (idle / grabando / transcribiendo / OK / error).",
                "Modo compacto con un click, siempre encima.",
            ],
        },
        {
            "icon": "?",
            "title": "Robustez",
            "items": [
                "Limpieza segura de archivos temporales.",
                "Manejo correcto de errores de Groq, Google y modelo local.",
                "Hotkey global no se pisa con la tecla de pegado.",
            ],
        },
    ],
    "try_this": [
        "1. Abre Configuración -> pega tu Groq API Key (se cifra al guardar).",
        "2. Cambia el backend a 'Whisper local' y elige modelo 'base'. Espera a que descargue (1ra vez).",
        "3. Pon el cursor en cualquier app, presiona Ctrl+Alt+N, dicta, vuelve a presionar.",
        "4. Activa 'Modo compacto' y 'Siempre encima' para usarlo flotando.",
        "5. Si tienes GPU NVIDIA, en Configuración fuerza device='cuda' y usa modelo 'medium'.",
    ],
}
