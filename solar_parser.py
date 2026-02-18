import streamlit as st
import pandas as pd
import re
from io import BytesIO
import pdfplumber

st.set_page_config(page_title="Solar Faktura Parser (PDF)", layout="wide")

st.title("Solar Faktura – Pris per enhet (PDF)")
st.markdown("""
Last opp Solar-faktura som PDF. Appen parser teksten og finner varer, antall og nettobeløp.
""")

uploaded_file = st.file_uploader("Velg PDF-fil", type=["pdf"])

if uploaded_file is not None:
    with st.spinner("Leser PDF og parser..."):
        try:
            pdf_bytes = BytesIO(uploaded_file.read())
            full_text = ""

            with pdfplumber.open(pdf_bytes) as pdf:
                for page in pdf.pages:
                    text = page.extract_text(layout=True)  # Bevarer mellomrom bedre
                    if text:
                        full_text += text + "\n\n"

            # Debug: Vis tekst
            st.subheader("Ekstrahert tekst (første 4000 tegn)")
            st.text(full_text[:4000] + "..." if len(full_text) > 4000 else full_text)

            lines = [line.strip() for line in full_text.splitlines() if line.strip()]

            items = []
            current = None

            i = 0
            while i < len(lines):
                line = lines[i]

                # Ny vare: starter med Nr + artikkelnr (f.eks. "1 1355221 ...")
                nr_art_match = re.match(r'^(\d+)\s+(\d{6,})\s+', line)
                if nr_art_match:
                    if current:
                        items.append(current)

                    current = {
                        "Nr": nr_art_match.group(1),
                        "Artikkelnr": nr_art_match.group(2),
                        "Beskrivelse": line[nr_art_match.end():].strip(),
                        "Antall": None,
                        "Enhet": "?",
                        "Nettobeløp": None
                    }
                    i += 1
                    continue

                if current:
                    # Fortsett beskrivelse hvis ikke rabatt eller totalsum
                    if not line.startswith(("Rabatt:", "Standard ID:", "Ordrelinjenummer:", "Baskvantitet:")) and not "Total" in line and not "Å betale" in line:
                        current["Beskrivelse"] += " " + line.strip()

                    # Antall + enhet (ser etter tall + enhet i linjen)
                    antall_match = re.search(r'(\d+[.,]?\d*)\s*(m|each|stk|roll|set|pcs|pakke)\b', line, re.I)
                    if antall_match and current["Antall"] is None:
                        current["Antall"] = float(antall_match.group(1).replace(",", "."))
                        current["Enhet"] = antall_match.group(2).lower()

                    # Nettobeløp
                    netto_match = re.search(r'([\d\s,.]+)\s*NOK', line)
                    if netto_match and current["Nettobeløp"] is None:
                        val = netto_match.group(1).replace(" ", "").replace(",", ".")
                        try:
                            current["Nettobeløp"] = float(val)
                        except:
                            pass

                    # Hvis rabatt eller ekstra info – legg til beskrivelse
                    if line.startswith("Rabatt:") or "Standard ID:" in line or "Ordrelinjenummer:" in line:
                        current["Beskrivelse"] += " " + line.strip()

                i += 1

            if current:
                items.append(current)

            # Lag resultat
            result = []
            for item in items:
                if item["Antall"] is not None and item["Nettobeløp"] is not None and item["Antall"] > 0:
                    pris = round(item["Nettobeløp"] / item["Antall"], 2)
                    result.append({
                        "Nr": item["Nr"],
                        "Artikkelnr": item.get("Artikkelnr", ""),
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
                st.warning("Fant ingen gyldige linjer med antall + nettobeløp. Sjekk ekstrahert tekst over.")

        except Exception as e:
            st.error(f"Feil under behandling: {str(e)}")
            st.info("Prøv på nytt eller send feilmeldingen.")

st.caption("PDF-parser med tekstbasert parsing – tilpasset Solar • Hele fila sendes hver gang")
