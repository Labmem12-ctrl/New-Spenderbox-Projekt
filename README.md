# YoBo – YourBox · HS Esslingen

Eine Webapp zur Steuerung einer automatischen Spenderbox für Hygieneprodukte an der Hochschule Esslingen.

## Was macht die App?

- Studierende loggen sich mit ihrer **HS-Esslingen E-Mail** ein (Magic Link)
- Sie wählen ein Produkt (**Binde** oder **Desinfektionstuch**)
- Die Box gibt das Produkt aus
- Ein **60-Minuten Cooldown** verhindert mehrfache Entnahme
- Ein **Admin-Bereich** zeigt Statistiken und Lagerbestand
- **Zweisprachig** (Deutsch / Englisch) für Austauschstudierende

## Sicherheit

- Token-Hashing mit SHA-256
- Rate Limiting (3 Anfragen pro 10 Minuten pro IP)
- Magic Links sind nur 15 Minuten gültig und einmalig nutzbar
- Cooldown verhindert mehrfache Entnahme

## Voraussetzungen

- Python 3.x
- Raspberry Pi 4B (für den echten Betrieb)

## Installation

**1. Repository klonen:**
```
git clone https://github.com/st174761/Spenderbox.git
cd Spenderbox
```

**2. Bibliotheken installieren:**
```
pip install flask flask-mail flask-limiter python-dotenv pillow
```

**3. `.env` Datei erstellen:**
```
MAIL_USER=deine@gmail.com
MAIL_PASSWORD=dein-app-passwort
SECRET_KEY=irgendein-langer-zufallsstring
ADMIN_PASSWORT=deinAdminPasswort
BASE_URL=http://localhost:5000
```

> Für den Betrieb auf dem Raspberry Pi: `BASE_URL=http://192.168.0.110:5000`

**4. App starten:**
```
python app.py
```

Die App läuft dann auf `http://localhost:5000`

## Admin-Bereich

Erreichbar unter `/admin` — nur mit Passwort aus der `.env` Datei.

Zeigt:
- Anzahl ausgegebener Produkte (gesamt, diese Woche, diesen Monat)
- Binden vs. Desinfektionstücher Vergleich
- Unique Nutzerinnen
- Lagerbestand (manuell anpassbar)
- Protokoll der letzten 20 Ausgaben

## Projektstruktur

```
Spenderbox/
├── app.py              # Haupt-App, alle Routes
├── database.py         # Datenbank-Setup
├── translations.py     # Übersetzungen (DE/EN)
├── .env                # Sensible Daten (nicht auf GitHub!)
├── static/
│   ├── logo.png             # Logo für die WebApp
│   └── logo_email.png       # Logo für E-Mails (optimiert)
├── templates/
│   ├── index.html           # Startseite
│   ├── produkte.html        # Produktauswahl
│   ├── bestaetigung.html    # Bestätigung nach Ausgabe
│   ├── mail_verschickt.html # Nach E-Mail Anfrage
│   ├── gesperrt.html        # Cooldown-Seite mit Live-Timer
│   ├── fehler.html          # Fehlerseite
│   ├── 404.html             # Seite nicht gefunden
│   ├── admin_login.html     # Admin Login
│   └── admin_dashboard.html # Admin Dashboard
```

## Deployment auf Raspberry Pi

Der Pi bekommt im Labor der HS Esslingen die feste IP `192.168.0.110` (LAN).

```bash
# 1. Repository klonen
git clone https://github.com/st174761/Spenderbox.git
cd Spenderbox

# 2. Abhängigkeiten installieren
pip install flask flask-mail flask-limiter python-dotenv pillow

# 3. .env Datei anlegen
nano .env

# 4. App starten
python app.py
```

## Nächste Schritte

- [ ] Hardware-Integration (Motor, LED, Lichtschranke) via Python GPIO
- [ ] Automatischer Lagerbestand über Lichtschranke
- [ ] App als systemd-Dienst auf dem Pi einrichten (Autostart)
