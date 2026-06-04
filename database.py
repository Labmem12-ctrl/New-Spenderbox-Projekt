import sqlite3

def get_db():
    # Verbindung zur Datenbankdatei herstellen
    # (wird automatisch erstellt wenn sie nicht existiert)
    conn = sqlite3.connect("spenderbox.db")
    conn.row_factory = sqlite3.Row  # damit wir Spalten beim Namen nennen können
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    # Tabelle für Magic Links
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS magic_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            token TEXT UNIQUE NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            used INTEGER DEFAULT 0
        )
    """)

    # Tabelle für Ausgabe-Protokoll
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dispense_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            product_type TEXT NOT NULL,
            dispensed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Tabelle für Lagerbestand
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS lagerbestand (
            produkt TEXT PRIMARY KEY,
            anzahl INTEGER DEFAULT 0
        )
    """)

    # Startwerte für Lagerbestand (nur wenn noch nicht vorhanden)
    cursor.execute("INSERT OR IGNORE INTO lagerbestand (produkt, anzahl) VALUES ('binde', 0)")
    cursor.execute("INSERT OR IGNORE INTO lagerbestand (produkt, anzahl) VALUES ('desinfektion', 0)")

    conn.commit()
    conn.close()
    print("Datenbank erfolgreich erstellt!")

# Wenn wir diese Datei direkt ausführen, wird die DB erstellt
if __name__ == "__main__":
    init_db()
    