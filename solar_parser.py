import streamlit as st
import pandas as pd
import re
from io import BytesIO
import pdfplumber

st.set_page_config(page_title="Solar Faktura Parser (PDF)", layout="wide")

st.title("Solar Faktura – Pris per enhet (PDF)")
st.markdown("""
Last opp Solar PDF-faktura. Appen parser teksten og finner alle varer med riktig antall og nettobeløp.
""")

uploaded_file = st.file_uploader("Velg PDF-fil", type=["pdf"])

if uploaded_file is not None:
    with st.spinner("Leser og parser PDF..."):
        try:
            pdf_bytes = BytesIO(uploaded_file.read())
            full_text = ""

            with pdfplumber.open(pdf_bytes) as pdf:
                for page in pdf.pages:
                    text = page.extract_text(layout=True)
                    if text:
                        full_text += text + "\n\n"

            # Debug: Vis tekst (kan fjernes senere)
            st.subheader("Ekstrahert tekst (første 4000 tegn)")
            st.text(full_text[:4000] + "..." if len(full_text) > 4000 else full_text)

            lines = [line.strip() for line in full_text.splitlines() if line.strip()]

            items = []
            current = None

            for line in lines:
                # Ny varelinje: starter med "1 ", "2 " osv. etterfulgt av artikkelnr
                match = re.match(r'^(\d+)\s+(\d{6,})\s+(.*)', line)
                if match:
                    if current:
                        items.append(current)

                    nr = match.group(1)
                    artnr = match.group(2)
                    desc = match.group(3).strip()

                    current = {
                        "Nr": nr,
                        "Artikkelnr": artnr,
                        "Beskrivelse": desc,
                        "Antall": None,
                        "Enhet": "?",
                        "Nettobeløp": None
                    }
                    continue

                if current:
                    # Antall + enhet (vanlig mønster: tall + mellomrom + enhet)
                    antall_match = re.search(r'(\d+[.,]?\d*)\s*(m|each|stk|roll|set|pcs|pakke)\b', line, re.I)
                    if antall_match and current["Antall"] is None:
                        current["Antall"] = float(antall_match.group(1).replace(",", "."))
                        current["Enhet"] = antall_match.group(2).lower()

                    # Nettobeløp (tall + mellomrom + NOK)
                    netto_match = re.search(r'([\d\s,.]+)\s*NOK', line)
                    if netto_match and current["Nettobeløp"] is None:
                        val_str = netto_match.group(1).replace(" ", "").replace(",", ".")
                        try:
                            current["Nettobeløp"] = float(val_str)
                        except:
                            pass

                    # Legg til ekstra info til beskrivelse (rabatt, ID, etc.)
                    if line.startswith(("Rabatt:", "Standard ID:", "Ordrelinjenummer:", "Baskvantitet:")):
                        current["Beskrivelse"] += " " + line.strip()

            if current:
                items.append(current)

            # Lag resultat-tabell
            result = []
            for item in items:
                if item["Antall"] is not None and item["Nettobeløp"] is not None and item["Antall"] > 0:
                    pris = round(item["Nettobeløp"] / item["Antall"], 2)
                    result.append({
                        "Nr": item["Nr"],
                        "Artikkelnr": item["Artikkelnr"],
                        "Beskrivelse": item["Beskrivelse"].strip()[:150] + "..." if len(item["Beskrivelse"]) > 150 else item["Beskrivelse"].strip(),
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
                st.download_button("Last ned resultat som CSV", csv, "solar_priser.csv", "text/csv")
            else:
                st.warning("Fant ingen gyldige linjer. Sjekk ekstrahert tekst over – kanskje mønsteret varierer.")

        except Exception as e:
            st.error(f"Feil under behandling: {str(e)}")
            st.info("Prøv på nytt eller send feilmeldingen.")

st.caption("PDF-parser – tilpasset Solar-tekst • Hele fila sendes hver gang")
