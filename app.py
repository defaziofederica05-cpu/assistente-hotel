import sqlite3
from datetime import date
import pandas as pd
import streamlit as st
import os
from dotenv import load_dotenv

from langchain_community.utilities import SQLDatabase
from langchain_openai import ChatOpenAI
from langchain_community.agent_toolkits import create_sql_agent, SQLDatabaseToolkit

# Carica le variabili d'ambiente (es. OPENAI_API_KEY dal file .env)
load_dotenv()

# Nome del file del database
DB_FILE = "bookings.db"

# =====================================
# 1️⃣ CREAZIONE E POPOLAMENTO DATABASE
# =====================================
def crea_e_popola_database():
    """
    Crea un database SQLite con le tabelle 'camere' e 'prenotazioni'
    e lo popola con dati di esempio. La funzione viene eseguita solo se il
    database non esiste già.
    """
    db = sqlite3.connect(DB_FILE)
    cur = db.cursor()

    # --- TABELLA CAMERE ---
    # Contiene l'inventario totale delle camere per tipologia.
    cur.execute('''
    CREATE TABLE IF NOT EXISTS camere (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        room_type TEXT NOT NULL UNIQUE,
        total_rooms INTEGER NOT NULL,
        capacity INTEGER NOT NULL
    )
    ''')

    # Inserisce i dati solo se la tabella è vuota
    cur.execute("SELECT COUNT(*) FROM camere")
    if cur.fetchone()[0] == 0:
        camere = [
            ("Standard", 6, 2),
            ("Deluxe", 4, 2),
            ("Executive", 4, 2),
            ("Junior Suite", 2, 4),  # 2 adulti + 2 bambini
            ("Suite", 1, 2)
        ]
        cur.executemany('INSERT INTO camere (room_type, total_rooms, capacity) VALUES (?, ?, ?);', camere)
        print("Tabella 'camere' popolata.")

    # --- TABELLA PRENOTAZIONI ---
    # Contiene le singole prenotazioni.
    cur.execute('''
    CREATE TABLE IF NOT EXISTS prenotazioni (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guest_name TEXT,
        room_type TEXT,
        check_in DATE,
        check_out DATE,
        num_guests INT,
        price REAL,
        status TEXT, -- Es: 'Confermata', 'Cancellata', 'In attesa'
        booking_date DATE
    )
    ''')
    
    # Inserisce i dati solo se la tabella è vuota
    cur.execute("SELECT COUNT(*) FROM prenotazioni")
    if cur.fetchone()[0] == 0:
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
        print("Tabella 'prenotazioni' popolata.")

    db.commit()
    db.close()


# =====================================
# 2️⃣ CONNESSIONE AL DATABASE + VERIFICA
# =====================================
def mostra_dati_da_db():
    """Legge i dati dalle tabelle del database e li restituisce come DataFrame Pandas."""
    try:
        conn = sqlite3.connect(DB_FILE)
        camere_df = pd.read_sql_query("SELECT * FROM camere;", conn)
        prenotazioni_df = pd.read_sql_query("SELECT * FROM prenotazioni;", conn)
        conn.close()
        return camere_df, prenotazioni_df
    except Exception as e:
        st.error(f"Errore nella lettura del database: {e}")
        return pd.DataFrame(), pd.DataFrame()


# =====================================
# 3️⃣ LLM + LANGCHAIN SQL AGENT
# =====================================
def crea_sql_agent():
    """
    Configura e restituisce un agente LangChain in grado di interrogare
    il database SQL in linguaggio naturale.
    """
    # Prompt di sistema per guidare il comportamento dell'agente
    system_prompt = f"""
    Sei un assistente virtuale altamente qualificato per l'hotel "Chalet Monte Bianco".
    La data odierna è {date.today().strftime("%Y-%m-%d")}.

    Il tuo compito è rispondere alle domande dei clienti o del management interrogando un database SQL.
    Hai accesso a due tabelle:
    1. `camere`: contiene l'inventario totale delle camere. Colonne: `id`, `room_type`, `total_rooms`, `capacity`.
    2. `prenotazioni`: contiene le prenotazioni dei clienti. Colonne: `id`, `guest_name`, `room_type`, `check_in`, `check_out`, `num_guests`, `price`, `status`, `booking_date`.

    Linee guida fondamentali:
    - Per calcolare la disponibilità di un tipo di camera in un certo periodo, devi:
      1. Trovare il numero totale di camere di quel tipo dalla tabella `camere`.
      2. Contare quante di quelle camere hanno prenotazioni `Confermata` che si sovrappongono a quelle date.
      3. Sottrarre il numero di camere prenotate dal numero totale.
    - Considera una prenotazione come attiva se il suo stato è 'Confermata'. Ignora quelle 'Cancellata' o 'In attesa' per i calcoli di occupazione.
    - Rispondi sempre in italiano, con un tono cortese e professionale.
    - Non mostrare MAI le query SQL all'utente finale. Fornisci solo la risposta in linguaggio naturale.
    - Se una domanda è ambigua, chiedi chiarimenti.
    """

    # Connessione al database tramite LangChain
    db = SQLDatabase.from_uri(f"sqlite:///{DB_FILE}")

    # Scelta del modello LLM (consigliato gpt-4o-mini per un buon rapporto costo/prestazioni)
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

    # Creazione del toolkit che l'agente userà per interagire con il DB
    toolkit = SQLDatabaseToolkit(db=db, llm=llm)

    # Creazione dell'agente SQL
    agent_executor = create_sql_agent(
        llm=llm,
        toolkit=toolkit,
        verbose=True,  # Mostra i pensieri dell'agente nel terminale (utile per debug)
        agent_type="openai-tools",
        system_prefix=system_prompt
    )
    return agent_executor


# =====================================
# 4️⃣ STREAMLIT APP
# =====================================
def main():
    st.set_page_config(page_title="Smart Reservation Assistant", page_icon="🏨")
    st.title("🏨 Smart Reservation Assistant")
    st.markdown("### Chalet Monte Bianco")

    # Creazione del database e popolamento (solo se non esiste)
    crea_e_popola_database()

    # Mostra i dati di esempio in un'area espandibile
    with st.expander("📂 Visualizza Dati del Database di Esempio"):
        camere_df, prenotazioni_df = mostra_dati_da_db()
        st.subheader("Inventario Camere")
        st.dataframe(camere_df, use_container_width=True)
        st.subheader("Elenco Prenotazioni")
        st.dataframe(prenotazioni_df, use_container_width=True)

    # Inizializzazione dell'agente
    # Usiamo st.cache_resource per evitare di ricreare l'agente ad ogni interazione
    @st.cache_resource
    def get_agent():
        return crea_sql_agent()

    agent = get_agent()

    # Area di chat
    st.subheader("💬 Chiedi all'Assistente Virtuale")
    
    # Esempi di domande per l'utente
    st.info("""
    **Puoi chiedere cose come:**
    - "Quante camere Standard sono libere per il 25 dicembre 2025?"
    - "Quali sono le date di check-in e check-out per la prenotazione di Mario Rossi?"
    - "Qual è il ricavo totale generato dalle prenotazioni confermate nel mese di dicembre 2025?"
    - "Qual è il tasso di occupazione per le suite domani?"
    """)

    query = st.text_input("La tua domanda:", key="user_query")

    if query:
        with st.spinner("Sto elaborando la tua richiesta..."):
            try:
                response = agent.invoke({"input": query})
                st.success("**Risposta:**")
                st.write(response["output"])
            except Exception as e:
                st.error(f"Si è verificato un errore: {e}")


if __name__ == "__main__":
    main()