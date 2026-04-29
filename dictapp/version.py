APP_NAME = "DictarApp"
VERSION = "0.5.0"

WHATS_NEW = {
    "version": VERSION,
    "title": "DictarApp 0.5 — selector de mic limpio y feedback en vivo",
    "tagline": "Un mic, una barra que se mueve, un icono que respira.",
    "sections": [
        {
            "icon": "*",
            "title": "Selección de micrófono simplificada",
            "items": [
                "Auto-asigna el mic default del sistema (el que toma cualquier app).",
                "Combobox con alternativas curadas: solo WASAPI (o MME si no hay), sin duplicados de host APIs.",
                "Una sola fila con dot de voz + nombre + barra de nivel en vivo.",
            ],
        },
        {
            "icon": "+",
            "title": "Indicador de voz en tiempo real",
            "items": [
                "VU meter continuo (single-stream) en lugar del scanner round-robin congelado.",
                "Mientras grabás, la barra sigue moviéndose con tu voz.",
                "El icono del tray pulsa: anillo rojo + disco interno que crece con el nivel.",
            ],
        },
        {
            "icon": "?",
            "title": "Diagnóstico mejorado",
            "items": [
                "La ventana de log se abre automáticamente con trazas detalladas (REC / TX / DELIVER).",
                "Botón 'Copiar todo' para mandar el log completo al portapapeles.",
                "Tracebacks completos en errores de transcripción.",
            ],
        },
        {
            "icon": ">",
            "title": "Robustez",
            "items": [
                "trim_silence ahora es adaptativo (15% del pico real) y respeta el sample rate del recorder.",
                "Auto-fallback CUDA → CPU si faltan las DLLs de cuBLAS/cuDNN.",
                "Safety net: si trim_silence dejaría < 25% del audio, devuelve el original.",
            ],
        },
    ],
    "try_this": [
        "1. Abrí la app: el mic default ya está asignado y la barra se mueve al hablar.",
        "2. Si querés cambiar de mic, usá el combobox 'Cambiar:' (solo mics reales, sin duplicados).",
        "3. Presioná Ctrl+Alt+N para grabar — la barra y el icono del tray reaccionan a tu voz.",
        "4. Si algo falla, abrí el log y mandá 'Copiar todo'.",
    ],
}
