import streamlit as st
import pandas as pd
import re
from io import BytesIO
import pdfplumber

st.set_page_config(page_title="Solar Faktura Parser (PDF)", layout="wide")

st.title("Solar Faktura – Pris per enhet (PDF)")
st.markdown("""
Last opp Solar-faktura som PDF. Appen ekstraherer tabeller og regner ut pris per enhet (nettobeløp ÷ antall).
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

            if not all_tables:
                st.warning("Ingen tabeller funnet i PDF-en. Filen kan være bildebasert eller ha uvanlig layout.")
            else:
                df_raw = pd.concat(all_tables, ignore_index=True).fillna("")

                # Debug: Vis rådata for å se hva pdfplumber fanger
                st.subheader("Rå ekstrahert tabell (debug)")
                st.dataframe(df_raw.head(20))

                # Normaliser kolonner – ofte er de numeriske eller None
                if all(isinstance(c, int) or c is None for c in df_raw.columns):
                    cols = ["Nr", "Artikkelnr", "Beskrivelse", "Antall", "Enhet", "A-pris", "MVA-sats", "Nettobeløp"]
                    df_raw.columns = cols[:len(df_raw.columns)]

                # Rense antall og nettobeløp-kolonner
                for col in ["Antall", "Nettobeløp"]:
                    if col in df_raw.columns:
                        df_raw[col] = df_raw[col].astype(str).str.replace(r'[^\d.,]', '', regex=True).str.replace(",", ".").replace("", float("nan"))
                        df_raw[col] = pd.to_numeric(df_raw[col], errors='coerce')

                # ------------------------------------------------------
                # Forbedret parsing: Loop gjennom rader og samle data
                # ------------------------------------------------------
                items = []
                current = None

                for _, row in df_raw.iterrows():
                    nr = str(row.get("Nr", "")).strip()
                    if re.match(r'^\d+$', nr):
                        if current:
                            items.append(current)
                        current = {
                            "Nr": nr,
                            "Beskrivelse": str(row.get("Beskrivelse", "")).strip(),
                            "Antall": None,
                            "Enhet": str(row.get("Enhet", "?")).strip(),
                            "Nettobeløp": None
                        }

                        # Hent antall og netto direkte fra kolonner hvis de finnes
                        antall_val = row.get("Antall")
                        if pd.notna(antall_val):
                            current["Antall"] = antall_val

                        netto_val = row.get("Nettobeløp")
                        if pd.notna(netto_val):
                            current["Nettobeløp"] = netto_val

                    if current:
                        # Fallback regex hvis kolonner ikke traff
                        row_text = " ".join(str(v) for v in row if pd.notna(v))
                        if current["Antall"] is None:
                            antall_match = re.search(r'(\d+[.,]?\d*)\s*(m|each|stk|roll)?', row_text, re.I)
                            if antall_match:
                                current["Antall"] = float(antall_match.group(1).replace(",", "."))
                                if antall_match.group(2):
                                    current["Enhet"] = antall_match.group(2).lower()

                        if current["Nettobeløp"] is None:
                            netto_match = re.search(r'([\d\s,.]+)\s*NOK', row_text)
                            if netto_match:
                                val = netto_match.group(1).replace(" ", "").replace(",", ".")
                                current["Nettobeløp"] = float(val)

                if current:
                    items.append(current)

                # Filtrer og beregn pris per enhet
                result = []
                for item in items:
                    if item["Antall"] and item["Nettobeløp"] and item["Antall"] > 0:
                        pris = round(item["Nettobeløp"] / item["Antall"], 2)
                        result.append({
                            "Nr": item["Nr"],
                            "Beskrivelse": item["Beskrivelse"][:100] + "..." if len(item["Beskrivelse"]) > 100 else item["Beskrivelse"],
                            "Antall": item["Antall"],
                            "Enhet": item["Enhet"],
                            "Nettobeløp": item["Nettobeløp"],
                            "Pris per enhet": pris
                        })

                if result:
                    df_result = pd.DataFrame(result)
                    st.success(f"Fant {len(df_result)} varelinjer!")
                    st.dataframe(df_result.style.format({
                        "Nettobeløp": "{:,.2f} NOK",
                        "Pris per enhet": "{:,.2f} NOK"
                    }), use_container_width=True)

                    csv = df_result.to_csv(index=False).encode('utf-8-sig')
                    st.download_button("Last ned som CSV", csv, "solar_priser.csv", "text/csv")
                else:
                    st.warning("Ingen gyldige linjer funnet. Sjekk rå-tabellen over – kanskje kolonnene er feilplassert.")

        except Exception as e:
            st.error(f"Feil under behandling: {str(e)}")
            st.info("Prøv en annen PDF eller send feilmeldingen for hjelp.")

st.markdown("---")
st.caption("PDF-parser med pdfplumber • Oppdatert versjon")
