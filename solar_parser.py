import streamlit as st
import pandas as pd
import re
from io import BytesIO

# ------------------------------------------------------
# APPENS HOVEDDEL
# ------------------------------------------------------
st.set_page_config(page_title="Solar Faktura Parser", layout="wide")

st.title("Solar Faktura – Pris per enhet")
st.markdown("""
Last opp en Solar-faktura (.xlsx) → appen prøver å finne alle varer og regne ut **nettobeløp ÷ antall**  
(den takler den typiske rotete strukturen med flere rader per vare)
""")

uploaded_file = st.file_uploader("Velg Solar Excel-fil", type=["xlsx", "xls"])

if uploaded_file is not None:
    with st.spinner("Leser og behandler filen..."):
        try:
            # Les filen som bytes
            excel_bytes = BytesIO(uploaded_file.read())
            df_raw = pd.read_excel(excel_bytes, sheet_name=0, header=None, dtype=str)
            df_raw = df_raw.fillna("")

            # ------------------------------------------------------
            # Parsing-logikk
            # ------------------------------------------------------
            items = []
            current = None

            for _, row in df_raw.iterrows():
                row_text = " ".join(str(x) for x in row if pd.notna(x) and str(x).strip())

                # Ny varelinje starter ofte med "1 ", "2 ", "3 " osv. i første kolonne
                first_cell = str(row[0]).strip()
                if re.match(r'^\d+$', first_cell) or re.match(r'^\d+\s', first_cell):
                    if current:
                        items.append(current)
                    current = {
                        "Nr": first_cell,
                        "Beskrivelse": "",
                        "Antall": None,
                        "Enhet": "each",
                        "Nettobeløp": None
                    }

                if current:
                    # Antall + enhet
                    antall_match = re.search(r'(\d+[.,]?\d*)\s*(m|each|stk|roll|set)?', row_text, re.I)
                    if antall_match and current["Antall"] is None:
                        current["Antall"] = float(antall_match.group(1).replace(",", "."))
                        if antall_match.group(2):
                            current["Enhet"] = antall_match.group(2).lower()

                    # Nettobeløp (tallet før "NOK")
                    netto_match = re.search(r'([\d\s,.]+)\s*NOK', row_text)
                    if netto_match and current["Nettobeløp"] is None:
                        val = netto_match.group(1).replace(" ", "").replace(",", ".")
                        try:
                            current["Nettobeløp"] = float(val)
                        except:
                            pass

                    # Beskrivelse – ta den lengste meningsfulle teksten
                    if len(row_text.strip()) > 15 and not current["Beskrivelse"]:
                        desc = row_text.strip()
                        # Fjern ting vi ikke vil ha i beskrivelsen
                        desc = re.sub(r'(Standard ID|Ordrelinjenummer|Baskvantitet|Rabat).*', '', desc, flags=re.I)
                        current["Beskrivelse"] = desc[:180].strip()

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

                # Nedlasting
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
                st.warning("Fant ingen gyldige varelinjer med både antall og nettobeløp.")

        except Exception as e:
            st.error(f"Noe gikk galt under lesing/behandling:\n{str(e)}")
            st.info("Prøv å laste opp fila på nytt, eller send meg feilmeldingen hvis problemet fortsetter.")

st.markdown("---")
st.caption("Laget med Streamlit • Parsing basert på typisk Solar-faktura-struktur • Februar 2026")