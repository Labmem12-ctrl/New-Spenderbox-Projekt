from flask import Flask, render_template, request, session, redirect, url_for
from flask_mail import Mail, Message
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from dotenv import load_dotenv
import os
import secrets
import hashlib
import socket
from datetime import datetime, timedelta
from database import get_db, init_db
from translations import TRANSLATIONS
import hardware  # Importiert unsere aktualisierte Hardware-Steuerung

# .env Datei laden
load_dotenv()

app = Flask(__name__)

# E-Mail Einstellungen
app.config["MAIL_SERVER"] = "smtp.gmail.com"
app.config["MAIL_PORT"] = 587
app.config["MAIL_USE_TLS"] = True
app.config["MAIL_USERNAME"] = os.getenv("MAIL_USER")
app.config["MAIL_PASSWORD"] = os.getenv("MAIL_PASSWORD")
app.config["MAIL_DEFAULT_SENDER"] = os.getenv("MAIL_USER")
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")

# --- HIER GEÄNDERT: Wartesperre beträgt nun exakt 1 Minute ---
COOLDOWN_MINUTEN = 1

def get_raspberry_pi_ip():
    """Ermittelt die aktuelle IP-Adresse des Raspberry Pi im lokalen Netzwerk."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "localhost"

# Logo einmalig beim Start laden
_logo_path = os.path.join(os.path.dirname(__file__), "static", "logo_email.png")
with open(_logo_path, "rb") as _f:
    LOGO_DATA = _f.read()

mail = Mail(app)
limiter = Limiter(get_remote_address, app=app, default_limits=[])

with app.app_context():
    init_db()

@app.context_processor
def inject_translations():
    lang = session.get("sprache", "de")
    return dict(t=TRANSLATIONS[lang], lang=lang)

@app.route("/sprache/<lang>")
def sprache(lang):
    if lang in ["de", "en"]:
        session["sprache"] = lang
    return redirect(request.referrer or url_for("startseite"))

@app.route("/")
def startseite():
    return render_template("index.html")

@app.route("/check_mail", methods=["POST"])
@limiter.limit("3 per 10 minutes")
def check_mail():
    email = request.form.get("user_email")

    t = TRANSLATIONS[session.get("sprache", "de")]
    if not email.endswith("@hs-esslingen.de"):
        return render_template("fehler.html",
            titel=t["err_ungueltige_mail_titel"],
            nachricht=t["err_ungueltige_mail_msg"])

    conn = get_db()

    existing = conn.execute(
        "SELECT * FROM magic_links WHERE email = ? AND used = 0 AND expires_at > ?",
        (email, datetime.now())
    ).fetchone()
    if existing:
        conn.close()
        return render_template("mail_verschickt.html", email=email, bereits=True)

    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    expires_at = datetime.now() + timedelta(minutes=15)
    conn.execute(
        "INSERT INTO magic_links (email, token, expires_at) VALUES (?, ?, ?)",
        (email, token_hash, expires_at)
    )
    conn.commit()
    conn.close()

    # --- HIER GEÄNDERT: Nutzt die dynamische Netzwerk-IP des PIs statt localhost ---
    aktueller_pi_ip = get_raspberry_pi_ip()
    link = f"http://{aktueller_pi_ip}:5000/login?token={raw_token}"

    msg = Message(
        subject="🌸 Dein YoBo Login-Link",
        sender=os.getenv("MAIL_USER"),
        recipients=[email]
    )

    msg.body = f"Hallo!\n\nHier ist dein Login-Link für YoBo:\n\n{link}\n\nDer Link ist 15 Minuten gültig.\n\n– Dein YoBo Team 🌸"

    msg.html = f"""
    <!DOCTYPE html>
    <html lang="de">
    <body style="margin:0; padding:0; background-color:#fce4ec; font-family: Arial, sans-serif;">
        <div style="max-width:480px; margin:40px auto; background:white; border-radius:24px; box-shadow:0 10px 40px rgba(233,30,140,0.15); overflow:hidden;">
            <div style="background:linear-gradient(135deg, #e91e8c, #c2185b); padding:32px; text-align:center;">
                <img src="cid:logo" alt="YoBo Logo" style="width:200px; display:block; margin:0 auto 4px;">
                <p style="color:rgba(255,255,255,0.8); margin:4px 0 0; font-size:13px;">YourBox · HS Esslingen</p>
            </div>
            <div style="padding:40px 32px; text-align:center;">
                <h2 style="color:#c2185b; font-size:20px; margin:0 0 12px;">Dein Login-Link ist bereit!</h2>
                <p style="color:#666; font-size:15px; line-height:1.6; margin:0 0 32px;">Klick auf den Button um dich einzuloggen.<br>Der Link ist <strong>15 Minuten</strong> gültig.</p>
                <a href="{link}" style="display:inline-block; padding:16px 40px; background:linear-gradient(135deg, #e91e8c, #c2185b); color:white; text-decoration:none; border-radius:12px; font-size:16px; font-weight:700; box-shadow:0 6px 20px rgba(233,30,140,0.35);">Jetzt einloggen →</a>
                <p style="color:#bbb; font-size:12px; margin:32px 0 0; line-height:1.6;">Falls der Button nicht funktioniert:<br><a href="{link}" style="color:#e91e8c; word-break:break-all;">{link}</a></p>
            </div>
        </div>
    </body>
    </html>
    """
    msg.attach(filename="logo.png", content_type="image/png", data=LOGO_DATA, disposition="inline", headers={"Content-ID": "<logo>"})

    try:
        mail.send(msg)
    except Exception as e:
        return render_template("fehler.html", titel=t["err_mail_fehl_titel"], nachricht=t["err_mail_fehl_msg"])

    return render_template("mail_verschickt.html", email=email, bereits=False)

@app.route("/login")
def login():
    token = request.args.get("token")
    t = TRANSLATIONS[session.get("sprache", "de")]

    if not token:
        return render_template("fehler.html", titel=t["err_kein_token_titel"], nachricht=t["err_kein_token_msg"])

    token_hash = hashlib.sha256(token.encode()).hexdigest()

    conn = get_db()
    link = conn.execute("SELECT * FROM magic_links WHERE token = ? AND used = 0", (token_hash,)).fetchone()

    if not link:
        conn.close()
        return render_template("fehler.html", titel=t["err_benutzt_titel"], nachricht=t["err_benutzt_msg"])

    expires_at = datetime.fromisoformat(link["expires_at"])
    if datetime.now() > expires_at:
        conn.execute("UPDATE magic_links SET used = 1 WHERE token = ?", (token_hash,))
        conn.commit()
        conn.close()
        return render_template("fehler.html", titel=t["err_abgelaufen_titel"], nachricht=t["err_abgelaufen_msg"])

    conn.execute("UPDATE magic_links SET used = 1 WHERE token = ?", (token_hash,))
    conn.commit()
    conn.close()

    session["email"] = link["email"]
    return redirect(url_for("produkte"))

@app.route("/produkte")
def produkte():
    if "email" not in session:
        return redirect(url_for("startseite"))
    return render_template("produkte.html", email=session["email"])

@app.route("/dispensiere", methods=["POST"])
@limiter.limit("5 per minute")
def dispensiere():
    if "email" not in session:
        return redirect(url_for("startseite"))

    email = session["email"]
    produkt = request.form.get("produkt")

    conn = get_db()

    # Cooldown prüfen
    letzter = conn.execute(
        "SELECT dispensed_at FROM dispense_log WHERE email = ? ORDER BY dispensed_at DESC LIMIT 1",
        (email,)
    ).fetchone()

    if letzter:
        letzte_zeit = datetime.fromisoformat(letzter["dispensed_at"])
        vergangen = datetime.now() - letzte_zeit
        if vergangen < timedelta(minutes=COOLDOWN_MINUTEN):
            conn.close()
            restzeit = timedelta(minutes=COOLDOWN_MINUTEN) - vergangen
            stunden = int(restzeit.total_seconds() // 3600)
            minuten = int((restzeit.total_seconds() % 3600) // 60)
            sekunden = int(restzeit.total_seconds() % 60)
            return render_template("gesperrt.html", stunden=stunden, minuten=minuten, sekunden=sekunden)

    # In Datenbank speichern
    conn.execute(
        "INSERT INTO dispense_log (email, product_type, dispensed_at) VALUES (?, ?, ?)",
        (email, produkt, datetime.now().isoformat())
    )
    
    # Automatisch Lagerbestand reduzieren bei Ausgabe
    conn.execute("UPDATE lagerbestand SET anzahl = MAX(0, anzahl - 1) WHERE produkt = ?", (produkt,))
    conn.commit()
    conn.close()

    # --- HIER GEÄNDERT: Echte Hardware-Ansteuerung aufrufen ---
    print(f"[SERVER] 🔔 Ausgabe für {email} angefordert.")
    hardware.produkt_ausgeben(produkt)

    return render_template("bestaetigung.html", produkt=produkt)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("startseite"))

# ─── ADMIN-BEREICH ───────────────────────────────────────────

@app.route("/admin")
def admin():
    if not session.get("admin"):
        return redirect(url_for("admin_login"))
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    fehler = None
    if request.method == "POST":
        passwort = request.form.get("passwort")
        if passwort == os.getenv("ADMIN_PASSWORT"):
            session["admin"] = True
            return redirect(url_for("admin_dashboard"))
        else:
            fehler = "Falsches Passwort."
    return render_template("admin_login.html", fehler=fehler)

@app.route("/admin/dashboard")
def admin_dashboard():
    if not session.get("admin"):
        return redirect(url_for("admin_login"))

    conn = get_db()
    gesamt = conn.execute("SELECT COUNT(*) as count FROM dispense_log").fetchone()["count"]
    eine_woche = (datetime.now() - timedelta(days=7)).isoformat()
    diese_woche = conn.execute("SELECT COUNT(*) as count FROM dispense_log WHERE dispensed_at > ?", (eine_woche,)).fetchone()["count"]
    ein_monat = (datetime.now() - timedelta(days=30)).isoformat()
    dieser_monat = conn.execute("SELECT COUNT(*) as count FROM dispense_log WHERE dispensed_at > ?", (ein_monat,)).fetchone()["count"]
    binden = conn.execute("SELECT COUNT(*) as count FROM dispense_log WHERE product_type = 'binde'").fetchone()["count"]
    desinfektion = conn.execute("SELECT COUNT(*) as count FROM dispense_log WHERE product_type = 'desinfektion'").fetchone()["count"]
    unique = conn.execute("SELECT COUNT(DISTINCT email) as count FROM dispense_log").fetchone()["count"]
    lager = conn.execute("SELECT * FROM lagerbestand").fetchall()
    protokoll = conn.execute("SELECT * FROM dispense_log ORDER BY dispensed_at DESC LIMIT 20").fetchall()
    conn.close()

    return render_template("admin_dashboard.html",
        gesamt=gesamt, diese_woche=diese_woche, dieser_monat=dieser_monat,
        binden=binden, desinfektion=desinfektion, unique=unique, lager=lager, protokoll=protokoll
    )

# --- HIER NEU: Route für die Admin Test-Knöpfe ---
@app.route("/admin/test_ausgabe", methods=["POST"])
def admin_test_ausgabe():
    if not session.get("admin"):
        return redirect(url_for("admin_login"))
    
    produkt = request.form.get("produkt")
    if produkt in ["binde", "desinfektion"]:
        print(f"[ADMIN] 🛠️ Manueller Hardwaretest für '{produkt.upper()}' ausgelöst!")
        hardware.produkt_ausgeben(produkt)
        
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/lagerbestand", methods=["POST"])
def admin_lagerbestand():
    if not session.get("admin"):
        return redirect(url_for("admin_login"))

    conn = get_db()
    for produkt in ["binde", "desinfektion"]:
        anzahl = request.form.get(produkt, 0)
        conn.execute("UPDATE lagerbestand SET anzahl = ? WHERE produkt = ?", (int(anzahl), produkt))
    conn.commit()
    conn.close()
    return redirect(url_for("admin_dashboard"))

@app.route("/lagerbestand/reduzieren", methods=["POST"])
def lagerbestand_reduzieren():
    daten = request.get_json()
    if not daten or "produkt" not in daten:
        return {"fehler": "Kein Produkt angegeben"}, 400

    produkt = daten["produkt"]
    if produkt not in ["binde", "desinfektion"]:
        return {"fehler": "Unbekanntes Produkt"}, 400

    conn = get_db()
    eintrag = conn.execute("SELECT anzahl FROM lagerbestand WHERE produkt = ?", (produkt,)).fetchone()

    if eintrag and eintrag["anzahl"] > 0:
        conn.execute("UPDATE lagerbestand SET anzahl = anzahl - 1 WHERE produkt = ?", (produkt,))
        conn.commit()
        conn.close()
        return {"status": "ok", "produkt": produkt}, 200
    else:
        conn.close()
        return {"status": "leer", "produkt": produkt}, 200

@app.route("/admin/logout")
def admin_logout():
    session.pop("admin", None)
    return redirect(url_for("admin_login"))

@app.errorhandler(404)
def seite_nicht_gefunden(e):
    return render_template("404.html"), 404

@app.errorhandler(429)
def zu_viele_anfragen(e):
    t = TRANSLATIONS[session.get("sprache", "de")]
    return render_template("fehler.html", titel=t["err_rate_titel"], nachricht=t["err_rate_msg"]), 429

if __name__ == "__main__":
    local_ip = get_raspberry_pi_ip()
    print("\n" + "="*70)
    print("🚀 YoBo – SERVER ERFOLGREICH GESTARTET!")
    print(f"📢 Erreichbar im selben WLAN unter: http://{local_ip}:5000")
    print("="*70 + "\n")
    app.run(host="0.0.0.0", port=5000, debug=False)