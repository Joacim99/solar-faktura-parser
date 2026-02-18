import streamlit as st
import pandas as pd
import re
from io import BytesIO
import pdfplumber

st.set_page_config(page_title="Solar Faktura Parser (PDF)", layout="wide")

st.title("Solar Faktura – Pris per enhet (PDF)")
st.markdown("""
Last opp Solar-faktura som PDF. Appen ekstraherer tekst/tabeller og regner ut pris per enhet.
""")

uploaded_file = st.file_uploader("Velg PDF-fil", type=["pdf"])

if uploaded_file is not None:
    with st.spinner("Behandler PDF..."):
        try:
            pdf_bytes = BytesIO(uploaded_file.read())
            all_tables = []

            with pdfplumber.open(pdf_bytes) as pdf:
                for page in pdf.pages:
                    tables = page.extract_tables()
                    if tables:
                        for table in tables:
                            header = table[0] if table else None
                            df_table = pd.DataFrame(table[1:], columns=header)
                            all_tables.append(df_table)

            if all_tables:
                df_raw = pd.concat(all_tables, ignore_index=True).fillna("")
                st.subheader("Rå ekstrahert tabell (debug – første 20 rader)")
                st.dataframe(df_raw.head(20))

                # Normaliser kolonner hvis de er numeriske/None
                if all(isinstance(c, int) or c is None for c in df_raw.columns):
                    cols = ["Nr", "Artikkelnr", "Beskrivelse", "Antall", "Enhet", "A-pris", "MVA-sats", "Nettobeløp"]
                    df_raw.columns = cols[:len(df_raw.columns)]

                # Rense tallkolonner
                for col in ["Antall", "Nettobeløp"]:
                    if col in df_raw.columns:
                        df_raw[col] = df_raw[col].astype(str).str.replace(r'[^\d.,]', '', regex=True).str.replace(",", ".").replace("", pd.NA)
                        df_raw[col] = pd.to_numeric(df_raw[col], errors='coerce')

                items = []
                for _, row in df_raw.iterrows():
                    nr = str(row.get("Nr", "")).strip()
                    if re.match(r'^\d+$', nr):
                        antall = row.get("Antall")
                        if pd.isna(antall) or antall == 0:
                            # Fallback: se i Beskrivelse-kolonnen
                            desc = str(row.get("Beskrivelse", "")).strip()
                            antall_match = re.search(r'(\d+[.,]?\d*)\s*(m|each|stk|roll|set|pcs|pakke)?', desc, re.I)
                            if antall_match:
                                antall = float(antall_match.group(1).replace(",", "."))
                                enhet = antall_match.group(2).lower() if antall_match.group(2) else "?"
                            else:
                                continue  # hopp over hvis ingen antall funnet

                        netto = row.get("Nettobeløp")
                        if pd.isna(netto):
                            netto_str = str(row.iloc[-1])  # ofte siste kolonne
                            netto_match = re.search(r'([\d\s,.]+)', netto_str)
                            if netto_match:
                                netto = float(netto_match.group(1).replace(",", "."))
                            else:
                                continue

                        if antall > 0 and netto > 0:
                            pris = round(netto / antall, 2)
                            items.append({
                                "Nr": nr,
                                "Beskrivelse": str(row.get("Beskrivelse", "–"))[:120] + "..." if len(str(row.get("Beskrivelse", ""))) > 120 else str(row.get("Beskrivelse", "–")),
                                "Antall": antall,
                                "Enhet": str(row.get("Enhet", "?")) or "?",
                                "Nettobeløp": netto,
                                "Pris per enhet": pris
                            })

                if items:
                    df_result = pd.DataFrame(items)
                    st.success(f"Fant {len(df_result)} varelinjer!")
                    st.dataframe(df_result.style.format({
                        "Nettobeløp": "{:,.2f} NOK",
                        "Pris per enhet": "{:,.2f} NOK"
                    }), use_container_width=True)

                    csv = df_result.to_csv(index=False).encode('utf-8-sig')
                    st.download_button("Last ned som CSV", csv, "solar_priser.csv", "text/csv")
                else:
                    st.warning("Fant ingen linjer med gyldig antall + netto. Sjekk rå-tabellen over.")

            else:
                st.warning("Ingen tabeller ekstrahert. Prøver tekst-fallback...")
                # Legg til tekst-fallback hvis ønskelig (si ifra hvis du vil ha det utvidet)

        except Exception as e:
            st.error(f"Feil: {str(e)}")

st.caption("Oppdatert PDF-parser – hele fila sendes hver gang")
