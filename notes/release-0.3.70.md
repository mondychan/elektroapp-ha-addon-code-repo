# Release 0.3.70

- Opravena vizuální chyba v tabulce Historie poplatků: kalendář u pole „Platné od“ nyní po kliknutí na datum datum skutečně vybere a editor zůstane otevřený.
- Kalendář se nově otevírá na měsíci aktuálně zvoleného data, nikoli vždy na aktuálním měsíci.
- Dny mimo povolený rozsah (před minimem nebo po maximu) jsou v kalendáři zablokované, takže je nelze omylem vybrat; navigace v měsících je omezena stejným rozsahem.
- Opravena ochrana proti neúplné konfiguraci při přidávání nového období poplatků (`defaultValues` bez vnořených sekcí už nespadne).
- Přihlášena regresní sada testů pro skutečný kalendář (`react-day-picker`), včetně přístupu k vnořenému tlačítku dne a výchozího měsíce.
