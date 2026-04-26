"""Diagnóstico exhaustivo de audio.

Prueba TODAS las combinaciones (host_api × device × rate × channels × dtype)
con sounddevice y reporta cuáles funcionan.

Uso:
    python diag_audio.py
"""
from __future__ import annotations

import sys
import time

try:
    import numpy as np
    import sounddevice as sd
except Exception as e:
    print(f"Falta sounddevice/numpy: {e}")
    print("Instala: pip install sounddevice numpy")
    sys.exit(1)


SAMPLE_RATES = [16000, 44100, 48000]
CHANNELS = [1, 2]
DTYPES = ["float32", "int16"]


def main() -> None:
    print("=" * 70)
    print("DIAGNÓSTICO DE AUDIO — DictarApp")
    print("=" * 70)
    print()

    # host APIs
    print("Host APIs:")
    for h in sd.query_hostapis():
        print(f"  - {h['name']}  default_input_idx={h.get('default_input_device')}")
    print()

    devices = sd.query_devices()
    inputs = [(i, d) for i, d in enumerate(devices) if int(d.get("max_input_channels", 0)) > 0]

    print(f"Encontrados {len(inputs)} mics. Probaré "
          f"{len(SAMPLE_RATES)*len(CHANNELS)*len(DTYPES)} combinaciones por cada uno…")
    print()

    successes: list[tuple[int, str, int, int, str]] = []
    for idx, dev in inputs:
        host_apis = sd.query_hostapis()
        ha_name = host_apis[int(dev.get("hostapi", 0))]["name"]
        native_rate = int(dev.get("default_samplerate", 0) or 0)
        native_ch = int(dev.get("max_input_channels", 1))
        print(f"[mic#{idx}] {dev['name'][:50]!r} host={ha_name} "
              f"native={native_rate}Hz {native_ch}ch")

        for rate in SAMPLE_RATES + [native_rate]:
            if not rate:
                continue
            for ch in CHANNELS:
                if ch > native_ch:
                    continue
                for dtype in DTYPES:
                    label = f"  rate={rate:>5} ch={ch} dtype={dtype:>7}"
                    try:
                        # callback puro para que WDM-KS también funcione
                        got = {"frames": 0}

                        def cb(indata, _frames, _time, _status):
                            got["frames"] += int(indata.shape[0])

                        s = sd.InputStream(samplerate=rate, channels=ch, dtype=dtype,
                                           device=idx, blocksize=512, callback=cb)
                        s.start()
                        time.sleep(0.20)
                        s.stop()
                        s.close()
                        if got["frames"] > 0:
                            print(f"{label}  ✓ OK ({got['frames']} frames)")
                            successes.append((idx, dev["name"], rate, ch, dtype))
                        else:
                            print(f"{label}  ⚠ abrió pero NO recibió audio (mic mute?)")
                            successes.append((idx, dev["name"], rate, ch, dtype))
                    except Exception as e:
                        msg = str(e).split("[")[0].strip()
                        print(f"{label}  ✗ {msg}")
        print()

    print("=" * 70)
    if successes:
        print(f"COMBINACIONES QUE FUNCIONAN ({len(successes)}):")
        for idx, name, rate, ch, dtype in successes:
            print(f"  • mic#{idx} '{name[:40]}' rate={rate} ch={ch} dtype={dtype}")
        print()
        # recomendación
        idx, name, rate, ch, dtype = successes[0]
        print("RECOMENDACIÓN: usar la primera combinación exitosa.")
        print(f"  mic_index={idx}  rate={rate}  channels={ch}  dtype={dtype}")
    else:
        print("NINGUNA combinación funcionó. Causas posibles:")
        print("  1) Permisos de Windows (Privacidad → Micrófono).")
        print("  2) Antivirus bloqueando acceso a audio.")
        print("  3) Driver de audio dañado — reinstala drivers AMD/Realtek.")
        print("  4) Otra app tiene el mic en exclusivo (Teams, Zoom, OBS, Discord).")


if __name__ == "__main__":
    main()
