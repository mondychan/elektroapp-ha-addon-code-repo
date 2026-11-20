# Release 0.3.71

- Opraveno ukládání historie poplatků: editor posílá snapshot ve stejném schématu, jaké vyžaduje backend (`dph_percent`, `kwh_fees`, `fixed`), takže úprava staršího období už neskončí chybou 400 „Each fee snapshot must contain dph_percent, kwh_fees and fixed.“
- Neznámá pole ve snapshotu historie zůstávají při úpravě zachována; editor už je tiše nezahazuje.
- Nové regresní testy: tvar odesílaného payloadu, přežití cizích polí a přidání období ještě před načtením konfigurace.
