import streamlit as st
import pandas as pd
import re
from io import BytesIO
import pdfplumber

# ------------------------------------------------------
# APPENS HOVEDDEL
# ------------------------------------------------------
st.set_page_config(page_title="Solar Faktura Parser (PDF)", layout="wide")

st.title("Solar Faktura – Pris per enhet (PDF-utgave)")
st.markdown("""
Last opp en Solar-faktura som PDF → appen prøver å finne alle varer og regne ut **nettobeløp ÷ antall**.  
Den takler rotete strukturer med rabattlinjer og ekstra info.
""")

uploaded_file = st.file_uploader("Velg Solar PDF-fil", type=["pdf"])

if uploaded_file is not None:
    with st.spinner("Leser og behandler PDF-filen..."):
        try:
            pdf_bytes = BytesIO(uploaded_file.read())
            all_tables = []

            with pdfplumber.open(pdf_bytes) as pdf:
                for page in pdf.pages:
                    tables = page.extract_tables()
                    if tables:
                        for table in tables:
                            # Gjør om tabell til DataFrame – bruk første rad som header hvis mulig
                            df_table = pd.DataFrame(table[1:], columns=table[0] if table[0] else None)
                            all_tables.append(df_table)

            if all_tables:
                # Slå sammen alle tabeller fra alle sider
                df_raw = pd.concat(all_tables, ignore_index=True).fillna("")

                # Fiks kolonnenavn hvis de er numeriske eller feil
                if all(isinstance(col, int) or col is None for col in df_raw.columns):
                    df_raw.columns = ["Nr", "Artikkelnr", "Beskrivelse", "Antall", "Enhet", "A-pris", "MVA-sats", "Nettobeløp"]

                # Fiks kolonner med feil data (f.eks. tomme overskrifter)
                df_raw = df_raw.rename(columns={None: ""})

                # ------------------------------------------------------
                # Parsing-logikk – tilpasset Solar-tabeller
                # ------------------------------------------------------
                items = []
                current = None

                for _, row in df_raw.iterrows():
                    # Slå sammen alle kolonner til en streng for regex-søk
                    row_text = " ".join(str(val).strip() for val in row if val)

                    # Ny vare starter ofte med tall i "Nr"-kolonnen
                    nr = str(row.get("Nr", "")).strip()
                    if re.match(r'^\d+$', nr):
                        if current:
                            items.append(current)
                        current = {
                            "Nr": nr,
                            "Beskrivelse": "",
                            "Antall": None,
                            "Enhet": "?",
                            "Nettobeløp": None
                        }

                    if current:
                        # Samle beskrivelse fra "Beskrivelse"-kolonnen eller hele raden
                        desc = row.get("Beskrivelse", row_text).strip()
                        if desc and not current["Beskrivelse"]:
                            current["Beskrivelse"] = desc

                        # Finn antall fra "Antall"-kolonnen eller regex i row_text
                        antall_str = str(row.get("Antall", "")).strip()
                        if antall_str and current["Antall"] is None:
                            antall_str = antall_str.replace(",", ".")
                            try:
                                current["Antall"] = float(antall_str)
                            except ValueError:
                                pass  # Prøv regex som fallback

                        if current["Antall"] is None:
                            antall_match = re.search(r'(\d+[.,]?\d*)\s*(m|each|stk|roll|set)?', row_text, re.I)
                            if antall_match:
                                current["Antall"] = float(antall_match.group(1).replace(",", "."))
                                if antall_match.group(2):
                                    current["Enhet"] = antall_match.group(2).lower()

                        # Finn nettobeløp fra "Nettobeløp"-kolonnen eller regex
                        netto_str = str(row.get("Nettobeløp", "")).strip()
                        if netto_str and "NOK" in netto_str:
                            netto_val = re.search(r'([\d\s,.]+)\s*NOK', netto_str)
                            if netto_val:
                                val = netto_val.group(1).replace(" ", "").replace(",", ".")
                                current["Nettobeløp"] = float(val)

                # Ikke glem siste vare
                if current:
                    items.append(current)

                # ------------------------------------------------------
                # Lag resultat-tabell
                # ------------------------------------------------------
                result = []
                for item in items:
                    if item["Antall"] and item["Nettobeløp"] and item["Antall"] > 0:
                        pris_enhet = round(item["Nettobeløp"] / item["Antall"], 2)
                        result.append({
                            "Nr": item["Nr"],
                            "Beskrivelse": item.get("Beskrivelse", "–"),
                            "Antall": item["Antall"],
                            "Enhet": item["Enhet"],
                            "Nettobeløp": item["Nettobeløp"],
                            "Pris per enhet": pris_enhet
                        })

                if result:
                    df_result = pd.DataFrame(result)
                    st.success(f"Fant {len(df_result)} varelinjer!")
                    st.dataframe(df_result.style.format({
                        "Nettobeløp": "{:,.2f} NOK",
                        "Pris per enhet": "{:,.2f} NOK"
                    }), use_container_width=True)

                    # Nedlasting som CSV
                    csv_buffer = BytesIO()
                    df_result.to_csv(csv_buffer, index=False, encoding='utf-8-sig')
                    csv_buffer.seek(0)
                    st.download_button(
                        label="Last ned resultat som CSV",
                        data=csv_buffer,
                        file_name="solar_priser.csv",
                        mime="text/csv"
                    )
                else:
                    st.warning("Fant ingen gyldige varelinjer med både antall og nettobeløp. Prøv en annen PDF eller sjekk parsing.")

            else:
                st.warning("Fant ingen tabeller i PDF-en. Denne PDF-en kan være bildebasert – kontakt støtte for OCR-oppsett.")

        except Exception as e:
            st.error(f"Noe gikk galt under lesing/behandling: {str(e)}")
            st.info("Prøv å laste opp fila på nytt, eller send feilmeldingen for hjelp.")

st.markdown("---")
st.caption("Laget med Streamlit og pdfplumber • PDF-utgave, februar 2026")
