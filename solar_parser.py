import streamlit as st
import pandas as pd
import re
from io import BytesIO
import pdfplumber

st.set_page_config(page_title="Solar Faktura Parser (PDF)", layout="wide")

st.title("Solar Faktura – Pris per enhet (PDF)")
st.markdown("""
Last opp Solar-faktura som PDF. Appen leser teksten og finner varer, antall, nettobeløp og regner ut pris per enhet.
""")

uploaded_file = st.file_uploader("Velg PDF-fil", type=["pdf"])

if uploaded_file is not None:
    with st.spinner("Leser PDF og parser tekst..."):
        try:
            pdf_bytes = BytesIO(uploaded_file.read())
            full_text = ""

            with pdfplumber.open(pdf_bytes) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        full_text += text + "\n\n"

            # Debug: Vis ekstrahert tekst
            st.subheader("Ekstrahert tekst fra PDF (første 3000 tegn – for feilsøking)")
            st.text(full_text[:3000] + "..." if len(full_text) > 3000 else full_text)

            # Split i linjer
            lines = [line.strip() for line in full_text.splitlines() if line.strip()]

            items = []
            current = None

            for line in lines:
                # Ny varelinje: starter med "1 ", "2 ", osv. (ofte med mellomrom etter Nr)
                nr_match = re.match(r'^(\d+)\s', line)
                if nr_match:
                    if current:
                        items.append(current)
                    current = {
                        "Nr": nr_match.group(1),
                        "Beskrivelse": line[nr_match.end():].strip(),  # alt etter Nr
                        "Antall": None,
                        "Enhet": "?",
                        "Nettobeløp": None
                    }

                if current:
                    # Legg til mer beskrivelse hvis linjen ikke starter med tall eller NOK/Rabatt
                    if not re.match(r'^\d', line) and not line.startswith("Rabatt:") and "NOK" not in line:
                        current["Beskrivelse"] += " " + line

                    # Antall + enhet (fleksibel regex)
                    antall_match = re.search(r'(\d+[.,]?\d*)\s*(m|each|stk|roll|set|pcs|pakke)?\b', line, re.I)
                    if antall_match and current["Antall"] is None:
                        current["Antall"] = float(antall_match.group(1).replace(",", "."))
                        if antall_match.group(2):
                            current["Enhet"] = antall_match.group(2).lower()

                    # Nettobeløp (tall + NOK)
                    netto_match = re.search(r'([\d\s,.]+)\s*NOK', line)
                    if netto_match and current["Nettobeløp"] is None:
                        val = netto_match.group(1).replace(" ", "").replace(",", ".")
                        try:
                            current["Nettobeløp"] = float(val)
                        except ValueError:
                            pass

            if current:
                items.append(current)

            # Lag resultat-tabell
            result = []
            for item in items:
                if item["Antall"] is not None and item["Nettobeløp"] is not None and item["Antall"] > 0:
                    pris = round(item["Nettobeløp"] / item["Antall"], 2)
                    result.append({
                        "Nr": item["Nr"],
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
                st.warning("Fant ingen linjer med både antall og nettobeløp. Sjekk ekstrahert tekst over – kanskje mønsteret varierer.")

        except Exception as e:
            st.error(f"Feil under behandling: {str(e)}")
            st.info("Prøv på nytt eller send feilmeldingen for hjelp.")

st.markdown("---")
st.caption("Tekstbasert PDF-parser med pdfplumber • Oppdatert for bedre vare-gjenkjenning • Hele fila sendes hver gang")

