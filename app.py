import sqlite3
from datetime import date, datetime
import pandas as pd
import streamlit as st
import os
from dotenv import load_dotenv
import re

# ----------------------------------------
# Carica variabili ambiente
# ----------------------------------------
load_dotenv()
DB_FILE = "bookings.db"

# =====================================================
# 1️⃣ CREAZIONE E POPOLAMENTO DATABASE
# =====================================================
def crea_e_popola_database():
    if os.path.exists(DB_FILE):
        return

    db = sqlite3.connect(DB_FILE)
    cur = db.cursor()

    # Tabella camere
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
    cur.executemany(
        'INSERT INTO camere (room_type, total_rooms, capacity) VALUES (?, ?, ?);',
        camere
    )

    # Tabella prenotazioni
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


# =====================================================
# 2️⃣ MOSTRA DATI
# =====================================================
def mostra_dati_da_db():
    conn = sqlite3.connect(DB_FILE)
    camere_df = pd.read_sql_query("SELECT * FROM camere;", conn)
    prenotazioni_df = pd.read_sql_query("SELECT * FROM prenotazioni;", conn)
    conn.close()
    return camere_df, prenotazioni_df


# =====================================================
# 3️⃣ FUNZIONI UTILI
# =====================================================

# Converte date in italiano in formato leggibile da pandas
def parse_date_italiano(date_str):
    mesi = {
        "gennaio": "Jan", "febbraio": "Feb", "marzo": "Mar", "aprile": "Apr",
        "maggio": "May", "giugno": "Jun", "luglio": "Jul", "agosto": "Aug",
        "settembre": "Sep", "ottobre": "Oct", "novembre": "Nov", "dicembre": "Dec"
    }
    for it, en in mesi.items():
        date_str = re.sub(it, en, date_str, flags=re.IGNORECASE)
    return pd.to_datetime(date_str, dayfirst=True).strftime("%Y-%m-%d")


def calcola_ricavo(period_start: str, period_end: str) -> float:
    conn = sqlite3.connect(DB_FILE)

    def ricavo_per_periodo(check_in_str, check_out_str, price, start_period_str, end_period_str):
        check_in = datetime.strptime(check_in_str, "%Y-%m-%d")
        check_out = datetime.strptime(check_out_str, "%Y-%m-%d")
        start_period = datetime.strptime(start_period_str, "%Y-%m-%d")
        end_period = datetime.strptime(end_period_str, "%Y-%m-%d")
        ci = max(check_in, start_period)
        co = min(check_out, end_period)
        stay_days = (check_out - check_in).days
        overlap_days = (co - ci).days
        if overlap_days <= 0 or stay_days <= 0:
            return 0
        return price * (overlap_days / stay_days)

    conn.create_function("RICAVO_PER_PERIODO", 5, ricavo_per_periodo)
    query = f"""
    SELECT SUM(RICAVO_PER_PERIODO(check_in, check_out, price, '{period_start}', '{period_end}')) as totale
    FROM prenotazioni
    WHERE status='Confermata';
    """
    cur = conn.cursor()
    cur.execute(query)
    result = cur.fetchone()[0] or 0
    conn.close()
    return result


def camere_libere(period_start: str, period_end: str, room_type: str) -> int:
    conn = sqlite3.connect(DB_FILE)
    df_total = pd.read_sql_query("SELECT total_rooms FROM camere WHERE room_type=?", conn, params=(room_type,))
    if df_total.empty:
        conn.close()
        return 0
    total_rooms = int(df_total.iloc[0]["total_rooms"])
    query = """
    SELECT COUNT(*) as occupate
    FROM prenotazioni
    WHERE room_type=? AND status='Confermata' 
      AND check_in < ? AND check_out > ?;
    """
    cur = conn.cursor()
    cur.execute(query, (room_type, period_end, period_start))
    occupate = cur.fetchone()[0] or 0
    conn.close()
    return max(total_rooms - occupate, 0)


def notti_ospite(guest_name: str) -> int:
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("""
        SELECT check_in, check_out 
        FROM prenotazioni 
        WHERE guest_name=? AND status='Confermata';
    """, conn, params=(guest_name,))
    conn.close()
    totale_notti = sum((pd.to_datetime(row.check_out) - pd.to_datetime(row.check_in)).days for idx, row in df.iterrows())
    return totale_notti


# =====================================================
# 4️⃣ STREAMLIT APP INTERATTIVA
# =====================================================
def main():
    st.set_page_config(page_title="Smart Reservation Assistant", page_icon="🏨")
    st.title("🏨 Smart Reservation Assistant")
    st.markdown("### Chalet Monte Bianco")

    crea_e_popola_database()

    # 📂 Visualizza dati
    with st.expander("📂 Visualizza Dati del Database"):
        camere_df, prenotazioni_df = mostra_dati_da_db()
        st.subheader("Inventario Camere")
        st.dataframe(camere_df, width="stretch")
        st.subheader("Elenco Prenotazioni")
        st.dataframe(prenotazioni_df, width="stretch")

    st.info("""
    Puoi chiedere:
    - Ricavo totale confermato nel mese o periodo personalizzato
    - Camere libere per periodo e tipo
    - Notti prenotate da un ospite
    """)

    query = st.text_input("💬 Fai la tua domanda:", key="user_query")

    if query:
        with st.spinner("Sto elaborando..."):
            q = query.lower()
            # Ricavo mese dicembre 2025
            if "mese" in q and "dicembre" in q and "2025" in q:
                totale_dicembre = calcola_ricavo("2025-12-01", "2025-12-31")
                st.success(f"💰 Ricavo totale confermato a dicembre 2025: {totale_dicembre:.2f} €")
                return

            # Ricavo per periodo personalizzato
            m = re.findall(r"(\d{1,2}\s\w+\s\d{4}|\d{4}-\d{2}-\d{2})", query)
            if "ricavo" in q and len(m) >= 2:
                try:
                    start = parse_date_italiano(m[0])
                    end = parse_date_italiano(m[1])
                    totale_periodo = calcola_ricavo(start, end)
                    st.success(f"💰 Ricavo totale confermato dal {start} al {end}: {totale_periodo:.2f} €")
                    return
                except Exception:
                    st.info("❌ Non sono riuscito a interpretare le date. Usa AAAA-MM-GG o GG mese AAAA.")

            # Camere libere per tipo e periodo
            if "camere" in q and ("libere" in q or "disponibili" in q):
                room_match = re.search(r"(standard|deluxe|executive|junior suite|suite)", q)
                if room_match:
                    room_type = room_match.group(1).title()
                else:
                    room_type = None

                if len(m) >= 2:
                    start = parse_date_italiano(m[0])
                    end = parse_date_italiano(m[1])
                elif len(m) == 1:
                    start = end = parse_date_italiano(m[0])
                else:
                    st.info("❌ Inserisci almeno una data.")
                    return

                if room_type:
                    disponibili = camere_libere(start, end, room_type)
                    st.success(f"🏨 Camere {room_type} libere dal {start} al {end}: {disponibili}")
                else:
                    st.success("❌ Specifica il tipo di camera (Standard, Deluxe, Executive, Junior Suite, Suite).")
                return

            # Notti prenotate da un ospite
            if "notti" in q or "ospite" in q:
                guest_match = re.search(r"di\s([\w\s]+)", q)
                if guest_match:
                    guest_name = guest_match.group(1).strip().title()
                    totale_notti = notti_ospite(guest_name)
                    st.success(f"🛌 {guest_name} ha prenotato {totale_notti} notti confermate")
                else:
                    st.info("❌ Specifica il nome dell'ospite.")
                return

            st.info("❓ Domande possibili: ricavo mese, ricavo periodo, camere libere, notti ospite.")


if __name__ == "__main__":
    main()
