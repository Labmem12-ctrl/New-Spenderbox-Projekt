import time
import threading
import requests

# --- KONFIGURATION ---
# Lichtschranke an GPIO 24 (VCC -> 3.3V, GND -> GND, OUT -> GPIO 24)
LICHTSCHRANKE_PIN = 24
NODE_RED_URL = "http://localhost:1880/api/dispense"

# Versuchen, die speziellen Bibliotheken für das PCA9685-Board zu laden.
try:
    from adafruit_servokit import ServoKit
    # Initialisiert das Board mit 16 Kanälen
    pca = ServoKit(channels=16)
    SIMULATION = False
    print("\n[HARDWARE] 🟢 PCA9685 Servo-Board erfolgreich initialisiert.")
except (ImportError, NotImplementedError):
    SIMULATION = True
    print("\n[HARDWARE] 🟡 Simulationsmodus aktiv (Keine Raspberry Pi / PCA9685 Hardware erkannt).")


def send_signal_to_nodered(produkt_typ):
    """Sendet ein HTTP-Signal an Node-RED, um den dortigen Flow zu triggern."""
    try:
        payload = {"produkt": produkt_typ.lower()}
        response = requests.post(NODE_RED_URL, json=payload, timeout=1.5)
        print(f"[NODE-RED] 🌐 Signal erfolgreich gesendet. Status: {response.status_code}")
    except Exception as e:
        print(f"[NODE-RED] ⚠️ Hinweis: Node-RED unter {NODE_RED_URL} nicht erreichbar (evtl. läuft Node-RED gerade nicht).")


def produkt_ausgeben(produkt_typ):
    """
    Steuert jeweils ZWEI Servomotoren über das PCA9685-Board an 
    und informiert parallel Node-RED.
    """
    produkt = produkt_typ.lower()
    
    # Zuweisung der 4 Motoren (2 pro Produkt)
    if produkt == 'binde':
        kanale = [0, 1]  # Produkt 1 nutzt Kanal 0 und 1
    elif produkt == 'desinfektion':
        kanale = [2, 3]  # Produkt 2 nutzt Kanal 2 und 3
    else:
        print(f"[HARDWARE] ❌ Unbekannter Produkttyp: {produkt_typ}")
        return False

    # Parallel Node-RED benachrichtigen
    send_signal_to_nodered(produkt)

    if SIMULATION:
        print(f"\n[HARDWARE-SIM] ⚙️ [Kanäle {kanale}] Drehe BEIDE Servos für '{produkt.upper()}' auf 90 Grad...")
        time.sleep(1.5)
        print(f"[HARDWARE-SIM] ⚙️ [Kanäle {kanale}] Drehe Servos zurück auf 0 Grad...")
        time.sleep(0.5)
        print(f"[HARDWARE-SIM] ✅ Ausgabe für '{produkt.upper()}' erfolgreich im Terminal simuliert.\n")
        return True
        
    else:
        print(f"\n[HARDWARE] 🚀 Starte echte 2-Motor-Ausgabe für: {produkt.upper()}")
        try:
            # 1. Startposition für beide Motoren sicherstellen (0 Grad)
            for kanal in kanale:
                pca.servo[kanal].angle = 0
            time.sleep(0.3)
            
            # 2. Beide Motoren auf 90 Grad drehen
            print(f"[HARDWARE] Drehe Kanäle {kanale} auf 90 Grad...")
            for kanal in kanale:
                pca.servo[kanal].angle = 90
            
            time.sleep(1.5)  # Warten, bis das Produkt physisch gefallen ist
            
            # 3. Wieder zurück auf Ausgangsposition drehen
            print(f"[HARDWARE] Drehe Kanäle {kanale} zurück auf 0 Grad...")
            for kanal in kanale:
                pca.servo[kanal].angle = 0
            time.sleep(0.3)
            
            print(f"[HARDWARE] ✅ Ausgabe auf Kanälen {kanale} erfolgreich abgeschlossen.\n")
            return True
            
        except Exception as e:
            print(f"[HARDWARE] ❌ Fehler bei der echten Servo-Ansteuerung auf Kanälen {kanale}: {e}")
            return False


# ─── LICHTSCHRANKE HINTERGRUND-ÜBERWACHUNG ───────────────────
def lichtschranke_ueberwachung():
    if SIMULATION:
        print("[HARDWARE-SIM] 🔍 Lichtschranken-Überwachung läuft passiv im Simulationsmodus.")
        return
    
    try:
        import RPi.GPIO as GPIO
        GPIO.setmode(GPIO.BCM)
        # Meistens schalten Lichtschranken gegen GND (Pull-Up nötig)
        GPIO.setup(LICHTSCHRANKE_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        
        print(f"[HARDWARE] 🔍 Echte Lichtschranken-Überwachung auf GPIO-Pin {LICHTSCHRANKE_PIN} gestartet.")
        
        def callback_ausgeloest(kanal):
            print("\n[LICHTSCHRANKE] 🚨 Lichtschranke wurde ausgelöst! Ein Produkt ist vorbeigefallen.")
            
        # Erkennt, wenn der Lichtstrahl unterbrochen wird (FALLING Edge)
        GPIO.add_event_detect(LICHTSCHRANKE_PIN, GPIO.FALLING, callback=callback_ausgeloest, bouncetime=400)
    except Exception as e:
        print(f"[HARDWARE] ❌ Fehler bei der Initialisierung der Lichtschranke: {e}")

# Startet die Lichtschranke sofort im Hintergrund, damit Flask nicht blockiert wird
threading.Thread(target=lichtschranke_ueberwachung, daemon=True).start()