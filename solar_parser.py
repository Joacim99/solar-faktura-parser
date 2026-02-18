# Inne i elif file_ext == 'pdf': blokken, erstatt fra "all_tables = []" og nedover med dette:

all_tables = []
with pdfplumber.open(pdf_bytes) as pdf:
    for page in pdf.pages:
        tables = page.extract_tables()
        if tables:
            for table in tables:
                # Prøv å bruke første rad som header
                header = table[0] if table else None
                df_table = pd.DataFrame(table[1:], columns=header)
                all_tables.append(df_table)

if all_tables:
    df_raw = pd.concat(all_tables, ignore_index=True).fillna("")

    # Debug: Vis rå ekstrahert tabell til deg
    st.subheader("Rå ekstrahert tabell fra PDF (for feilsøking)")
    st.dataframe(df_raw.head(20))

    # Fiks kolonnenavn manuelt hvis de er ødelagte
    possible_cols = ["Nr", "Artikkelnr", "Beskrivelse", "Antall", "Enhet", "A-pris", "MVA-sats", "Nettobeløp"]
    if len(df_raw.columns) >= len(possible_cols):
        df_raw = df_raw.iloc[:, :len(possible_cols)]
        df_raw.columns = possible_cols[:len(df_raw.columns)]

    # Alternativt: Bruk posisjonsbasert hvis navn mangler
    if "Antall" not in df_raw.columns:
        if len(df_raw.columns) > 3:
            df_raw["Antall"] = df_raw.iloc[:, 3]  # ofte 4. kolonne
    if "Nettobeløp" not in df_raw.columns:
        if len(df_raw.columns) > 7:
            df_raw["Nettobeløp"] = df_raw.iloc[:, -1]  # ofte siste kolonne

    # Rense kolonner
    if "Antall" in df_raw.columns:
        df_raw["Antall"] = df_raw["Antall"].astype(str).str.replace(",", ".").str.extract(r'(\d+\.?\d*)', expand=False).astype(float, errors='ignore')
    if "Nettobeløp" in df_raw.columns:
        df_raw["Nettobeløp"] = df_raw["Nettobeløp"].astype(str).str.replace(" ", "").str.replace(",", ".").str.extract(r'(\d+\.?\d*)', expand=False).astype(float, errors='ignore')

    # ------------------------------------------------------
    # Parsing-logikk – enklere versjon basert på kolonner
    # ------------------------------------------------------
    items = []

    for _, row in df_raw.iterrows():
        nr = str(row.get("Nr", "")).strip()
        if re.match(r'^\d+$', nr):  # Ny varelinje
            antall = row.get("Antall", None)
            netto_str = str(row.get("Nettobeløp", ""))
            netto_match = re.search(r'([\d\s,.]+)', netto_str) if netto_str else None

            if antall is not None and netto_match:
                try:
                    antall_val = float(antall) if isinstance(antall, (int, float)) else float(antall)
                    netto_val = float(netto_match.group(1).replace(" ", "").replace(",", "."))
                    if antall_val > 0 and netto_val > 0:
                        pris_enhet = round(netto_val / antall_val, 2)
                        items.append({
                            "Nr": nr,
                            "Beskrivelse": row.get("Beskrivelse", "–"),
                            "Antall": antall_val,
                            "Enhet": row.get("Enhet", "?"),
                            "Nettobeløp": netto_val,
                            "Pris per enhet": pris_enhet
                        })
                except:
                    pass  # Hopp over ugyldige rader

    if items:
        df_result = pd.DataFrame(items)
        st.success(f"Fant {len(df_result)} gyldige varelinjer!")
        st.dataframe(df_result.style.format({
            "Nettobeløp": "{:,.2f} NOK",
            "Pris per enhet": "{:,.2f} NOK"
        }), use_container_width=True)

        # CSV-nedlasting
        csv = df_result.to_csv(index=False).encode('utf-8-sig')
        st.download_button("Last ned CSV", csv, "solar_priser.csv", "text/csv")

    else:
        st.warning("Fant ingen linjer med gyldig antall + netto. Sjekk rå-tabellen over og se om kolonnene stemmer.")

else:
    st.warning("Ingen tabeller ekstrahert fra PDF-en. Prøv pdfplumber med annen strategi eller send PDF for manuell sjekk.")
