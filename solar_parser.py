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
            st.subheader("Ekstrahert tekst fra PDF (første 5000 tegn)")
            st.text(full_text[:5000] + "..." if len(full_text) > 5000 else full_text)

            lines = [line.strip() for line in full_text.splitlines() if line.strip()]

            items = []
            current = None

            for line in lines:
                # Ny varelinje: starter med "1 " eller "2 " osv. etterfulgt av artikkelnr
                nr_art_match = re.match(r'^(\d+)\s+(\d+)\s+(.*)', line)
                if nr_art_match:
                    if current:
                        items.append(current)

                    nr = nr_art_match.group(1)
                    artnr = nr_art_match.group(2)
                    rest = nr_art_match.group(3).strip()

                    current = {
                        "Nr": nr,
                        "Artikkelnr": artnr,
                        "Beskrivelse": rest,
                        "Antall": None,
                        "Enhet": "?",
                        "Nettobeløp": None
                    }

                    # Prøv å finne antall/enhet i samme linje (vanlig mønster)
                    antall_match = re.search(r'(\d+[.,]?\d*)\s*(m|each|stk|roll|set|pcs|pakke)\b', rest, re.I)
                    if antall_match:
                        current["Antall"] = float(antall_match.group(1).replace(",", "."))
                        current["Enhet"] = antall_match.group(2).lower()

                    # Nettobeløp i samme linje
                    netto_match = re.search(r'([\d\s,.]+)\s*NOK', rest)
                    if netto_match:
                        val = netto_match.group(1).replace(" ", "").replace(",", ".")
                        try:
                            current["Nettobeløp"] = float(val)
                        except:
                            pass

                    continue

                if current:
                    # Legg til ekstra info til beskrivelse
                    if line.startswith(("Rabatt:", "Standard ID:", "Ordrelinjenummer:", "Baskvantitet:")):
                        current["Beskrivelse"] += " " + line.strip()

                    # Fallback: søk antall/enhet i ekstra linjer
                    if current["Antall"] is None:
                        antall_match = re.search(r'(\d+[.,]?\d*)\s*(m|each|stk|roll|set|pcs|pakke)\b', line, re.I)
                        if antall_match:
                            current["Antall"] = float(antall_match.group(1).replace(",", "."))
                            current["Enhet"] = antall_match.group(2).lower()

                    # Fallback nettobeløp
                    if current["Nettobeløp"] is None:
                        netto_match = re.search(r'([\d\s,.]+)\s*NOK', line)
                        if netto_match:
                            val = netto_match.group(1).replace(" ", "").replace(",", ".")
                            try:
                                current["Nettobeløp"] = float(val)
                            except:
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
