import sqlite3
import pandas as pd
import streamlit as st
import os
from dotenv import load_dotenv
import dateparser
import re
from datetime import datetime, date

load_dotenv()
DB_FILE = "bookings.db"

# ====================================
# 1️⃣ CREAZIONE E POPOLAMENTO DATABASE
# ====================================
def crea_e_popola_database():
    if os.path.exists(DB_FILE):
        return

    db = sqlite3.connect(DB_FILE)
    cur = db.cursor()

    cur.execute('''
    CREATE TABLE IF NOT EXISTS camere (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        room_type TEXT NOT NULL UNIQUE,
        total_rooms INTEGER NOT NULL,
        capacity INTEGER NOT NULL
    )
    ''')

    camere = [
        ("Standard", 6, 2),
        ("Deluxe", 4, 2),
        ("Executive", 4, 2),
        ("Junior Suite", 2, 4),
        ("Suite", 1, 2)
    ]
    cur.executemany('INSERT INTO camere (room_type, total_rooms, capacity) VALUES (?, ?, ?);', camere)

    cur.execute('''
    CREATE TABLE IF NOT EXISTS prenotazioni (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guest_name TEXT,
        room_type TEXT,
        check_in DATE,
        check_out DATE,
        num_guests INT,
        price REAL,
        status TEXT,
        booking_date DATE
    )
    ''')

    prenotazioni = [
        ("Mario Rossi", "Standard", "2025-11-20", "2025-11-23", 2, 210.0, "Confermata", "2025-10-29"),
        ("Lucia Bianchi", "Deluxe", "2025-11-25", "2025-11-28", 2, 400.0, "Confermata", "2025-10-27"),
        ("Giovanni Verdi", "Suite", "2025-12-01", "2025-12-05", 2, 900.0, "In attesa", "2025-10-30"),
        ("Elena Neri", "Executive", "2025-11-22", "2025-11-24", 2, 250.0, "Confermata", "2025-10-25"),
        ("Roberto Gialli", "Junior Suite", "2025-11-29", "2025-12-03", 4, 600.0, "Confermata", "2025-10-24"),
        ("Chiara Blu", "Standard", "2025-12-12", "2025-12-13", 2, 90.0, "Cancellata", "2025-10-22"),
        ("Luca Viola", "Deluxe", "2025-12-14", "2025-12-17", 2, 380.0, "Confermata", "2025-10-20"),
        ("Alessia Rossa", "Executive", "2025-12-18", "2025-12-21", 2, 300.0, "Confermata", "2025-10-18"),
        ("Giulia Azzurra", "Junior Suite", "2025-12-10", "2025-12-15", 4, 700.0, "In attesa", "2025-11-01"),
        ("Andrea Neri", "Suite", "2025-12-20", "2025-12-22", 2, 950.0, "Confermata", "2025-10-30"),
        ("Marco Galli", "Standard", "2025-12-15", "2025-12-17", 2, 200.0, "Confermata", "2025-11-02"),
        ("Paola Bruni", "Deluxe", "2025-12-23", "2025-12-26", 2, 420.0, "Confermata", "2025-11-05"),
        ("Stefano Fabbri", "Executive", "2025-12-25", "2025-12-28", 2, 270.0, "Confermata", "2025-11-02"),
        ("Pietro Riva", "Standard", "2025-12-20", "2025-12-24", 2, 300.0, "Confermata", "2025-11-10"),
        ("Giada Rossi", "Deluxe", "2025-12-22", "2025-12-26", 2, 480.0, "Confermata", "2025-11-12"),
        ("Valentina Grassi", "Executive", "2025-12-28", "2026-01-02", 2, 550.0, "Confermata", "2025-11-15")
    ]
    cur.executemany('''
    INSERT INTO prenotazioni (
        guest_name, room_type, check_in, check_out, num_guests, price, status, booking_date
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', prenotazioni)

    db.commit()
    db.close()

# ====================================
# 2️⃣ FUNZIONI UTILI
# ====================================
def parse_date_italiano(date_str):
    dt = dateparser.parse(date_str, languages=['it'])
    if dt:
        return dt.strftime("%Y-%m-%d")
    return None

def calcola_ricavo(start, end):
    conn = sqlite3.connect(DB_FILE)

    def ricavo(check_in_str, check_out_str, price, start_str, end_str):
        try:
            check_in = datetime.strptime(check_in_str, "%Y-%m-%d")
            check_out = datetime.strptime(check_out_str, "%Y-%m-%d")
            start_dt = datetime.strptime(start_str, "%Y-%m-%d")
            end_dt = datetime.strptime(end_str, "%Y-%m-%d")
            ci = max(check_in, start_dt)
            co = min(check_out, end_dt)
            stay_days = (check_out - check_in).days
            overlap = (co - ci).days
            if stay_days <= 0 or overlap <= 0:
                return 0
            return price * overlap / stay_days
        except:
            return 0

    conn.create_function("RICAVO", 5, ricavo)
    query = f"""
        SELECT SUM(RICAVO(check_in, check_out, price, '{start}', '{end}'))
        FROM prenotazioni WHERE status='Confermata';
    """
    cur = conn.cursor()
    cur.execute(query)
    totale = cur.fetchone()[0] or 0
    conn.close()
    return totale

def camere_libere(start, end, room_type=None):
    conn = sqlite3.connect(DB_FILE)
    df_camere = pd.read_sql_query("SELECT * FROM camere;", conn)
    result = {}
    for _, r in df_camere.iterrows():
        rt = r['room_type']
        total = r['total_rooms']
        if room_type and rt.lower() != room_type.lower():
            continue
        cur = conn.cursor()
        cur.execute("""
            SELECT COUNT(*) FROM prenotazioni
            WHERE room_type=? AND status='Confermata'
              AND check_in <= ? AND check_out > ?;
        """, (rt, end, start))
        occupate = cur.fetchone()[0] or 0
        result[rt] = total - occupate
    conn.close()
    if room_type:
        return result.get(room_type, 0)
    return result

def notti_ospite(guest_name):
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT check_in, check_out FROM prenotazioni WHERE guest_name=? AND status='Confermata'", conn, params=(guest_name,))
    conn.close()
    return sum((pd.to_datetime(r.check_out) - pd.to_datetime(r.check_in)).days for _, r in df.iterrows())

def tipo_camera_ospite(guest_name):
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT room_type FROM prenotazioni WHERE guest_name=? AND status='Confermata'", conn, params=(guest_name,))
    conn.close()
    return df['room_type'].tolist() if not df.empty else []

# ====================================
# 3️⃣ STREAMLIT APP
# ====================================
def main():
    st.set_page_config(page_title="Smart Reservation Assistant", page_icon="🏨")
    st.title("🏨 Smart Reservation Assistant")
    st.markdown("### Chalet Monte Bianco")

    crea_e_popola_database()
    st.info("Puoi chiedere: ricavo, camere libere, camere confermate, notti ospite, tipo camera ospite.")

    query = st.text_input("💬 Fai la tua domanda:")

    if query:
        q = query.lower()

        # ----------------- Ricavo -----------------
        if "ricavo" in q:
            dates = re.findall(r"(\d{1,2}\s\w+\s\d{4}|\d{4}-\d{2}-\d{2})", query)
            if len(dates) >= 2:
                start = parse_date_italiano(dates[0])
                end = parse_date_italiano(dates[1])
                totale = calcola_ricavo(start, end)
                st.success(f"💰 Ricavo totale confermato dal {start} al {end}: {totale:.2f} €")
                return
            elif "dicembre" in q:
                totale = calcola_ricavo("2025-12-01", "2025-12-31")
                st.success(f"💰 Ricavo totale confermato a dicembre 2025: {totale:.2f} €")
                return

        # ----------------- Camere libere -----------------
        if "camere" in q:
            dates = re.findall(r"(\d{1,2}\s\w+\s\d{4}|\d{4}-\d{2}-\d{2})", query)
            if len(dates) == 0:
                start = end = date.today().strftime("%Y-%m-%d")
            elif len(dates) == 1:
                start = end = parse_date_italiano(dates[0])
            else:
                start = parse_date_italiano(dates[0])
                end = parse_date_italiano(dates[1])
            room_match = re.search(r"(standard|deluxe|executive|junior suite|suite)", query)
            room_type = room_match.group(1).title() if room_match else None
            disponibile = camere_libere(start, end, room_type)
            if room_type:
                st.success(f"🏨 Camere {room_type} disponibili: {disponibile}")
            else:
                st.success(f"🏨 Camere disponibili dal {start} al {end}: {disponibile}")
            return

        # ----------------- Notti ospite -----------------
        guest_match = re.search(r"([A-Z][a-z]+ [A-Z][a-z]+)", query)
        if "notti" in q and guest_match:
            guest_name = guest_match.group(1)
            totale_notti = notti_ospite(guest_name)
            st.success(f"🛌 {guest_name} ha prenotato {totale_notti} notti confermate")
            return

        # ----------------- Tipo camera ospite -----------------
        if ("tipo di camera" in q or "camera ha prenotato" in q) and guest_match:
            guest_name = guest_match.group(1)
            camere = tipo_camera_ospite(guest_name)
            if camere:
                st.success(f"🛏️ {guest_name} ha prenotato le seguenti camere confermate: {', '.join(camere)}")
            else:
                st.info(f"❌ Nessuna prenotazione confermata trovata per {guest_name}")
            return

        st.info("❓ Domande possibili: ricavo mese/periodo, camere libere/confermate, notti ospite, tipo camera ospite.")


if __name__ == "__main__":
    main()
