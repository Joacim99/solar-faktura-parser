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
    with st.spinner("Leser PDF og parser tekst..."):
        try:
            pdf_bytes = BytesIO(uploaded_file.read())
            full_text = ""

            with pdfplumber.open(pdf_bytes) as pdf:
                for page in pdf.pages:
                    text = page.extract_text(layout=True)
                    if text:
                        full_text += text + "\n\n"

            # Debug: Vis ekstrahert tekst
            st.subheader("Ekstrahert tekst fra PDF (første 6000 tegn)")
            st.text(full_text[:6000] + "..." if len(full_text) > 6000 else full_text)

            lines = [line.strip() for line in full_text.splitlines() if line.strip()]

            items = []
            current = None

            for line in lines:
                # Matcher hele varelinje: Nr + Artikkelnr + Beskrivelse + Antall + Enhet + A-pris + MVA + Netto NOK
                # Fleksibel nok til å matche variasjoner i mellomrom og enhet
                match = re.match(r'^(\d+)\s+(\d+)\s+(.+?)\s+(\d+[.,]?\d*)\s*(m|each|stk|roll|set|pcs|pakke)?\s+(\d+[.,]?\d*)\s+25,00 %\s+([\d\s,.]+)\s*NOK', line, re.I | re.DOTALL)
                if match:
                    if current:
                        items.append(current)

                    nr = match.group(1)
                    artnr = match.group(2)
                    desc = match.group(3).strip()
                    antall_str = match.group(4).replace(",", ".")
                    antall = float(antall_str)
                    enhet = match.group(5).lower() if match.group(5) else "?"
                    a_pris = match.group(6)
                    netto_str = match.group(7).replace(" ", "").replace(",", ".")
                    netto = float(netto_str)

                    current = {
                        "Nr": nr,
                        "Artikkelnr": artnr,
                        "Beskrivelse": desc,
                        "Antall": antall,
                        "Enhet": enhet,
                        "Nettobeløp": netto
                    }
                    continue

                # Legg til ekstra info (rabatt, ID, ordrelinje, baskvantitet) til beskrivelse
                if current and (line.startswith("Rabatt:") or "Standard ID:" in line or "Ordrelinjenummer:" in line or "Baskvantitet:" in line):
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
                st.warning("Fant ingen gyldige linjer. Sjekk ekstrahert tekst over – mønsteret kan variere.")

        except Exception as e:
            st.error(f"Feil under behandling: {str(e)}")
            st.info("Prøv på nytt eller send feilmeldingen.")

st.caption("PDF-parser – tekstbasert, tilpasset Solar-struktur • Hele fila sendes hver gang")
