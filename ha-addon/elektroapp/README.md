# Elektroapp Home Assistant Add-on

Add-on zobrazuje spotove ceny elektriny a vypocitane naklady na zaklade spotreby
z InfluxDB. UI je dostupne pres Home Assistant Ingress (panel v postrannim menu).

# Zdroj dat
Zdroj cen je volitelny pres `price_provider`:
- `spotovaelektrina` (default)
- `ote` (OTE + prevod EUR/CZK dle CNB)

## Instalace

1. V Home Assistant: Settings > Add-ons > Add-on Store > ... > Repositories.
2. Pridat URL GitHub repozitare s add-onem.
3. V seznamu add-onu vybrat "Elektroapp" a kliknout Install.
4. Otevrit konfiguraci add-onu, vyplnit InfluxDB a tarifni parametry.
5. Start add-onu a otevrit panel (Ingress).

## Pouziti

- Otevri Elektroapp z postranniho panelu Home Assistantu.
- Vyber datum pro denni graf "Naklady a spotreba".
- Volitelne zobraz mesicni souhrn a tabulku po dnech.
- Odhad vyuctovani ukazuje realny stav a projekci pro mesic/rok.
- Planovac spotrebicu najde nejlevnejsi okna pro zadanou delku.

## Konfigurace

Add-on nacita nastaveni z Home Assistant options (Supervisor). 

### `dph`
- Vyse DPH v procentech, napr. `21`.

### `poplatky`
- Vsechny hodnoty jsou bez DPH (Kc / kWh). DPH se aplikuje az ve vypoctu.
- `komodita_sluzba`: Poplatek za sluzbu obchodu.
- `oze`: Cena na podporu vykupu elektiny (OZE/POZE).
- `dan`: Dan z elektriny.
- `systemove_sluzby`: Systemove sluzby (CEPS).
- `distribuce.NT`: Distribuce pro nizky tarif.
- `distribuce.VT`: Distribuce pro vysoky tarif.

### `fixni`
- Fixni poplatky bez DPH (Kc / den, Kc / mesic).
- `denni.staly_plat`: Staly plat (Kc/den).
- `mesicni.provoz_nesitove_infrastruktury`: Nesitova infrastruktura (Kc/mesic).
- `mesicni.jistic`: Jistic (Kc/mesic).

### `tarif.vt_periods`
- Casove intervaly VT (vysoky tarif), format `HH-HH` oddeleny carkou.
- Priklad: `6-7,9-10,13-14,16-17`.
- Pouziva se pro urceni VT/NT pri vypoctu ceny.

### `influxdb`
- `host`: IP nebo hostname InfluxDB.
- `port`: Port InfluxDB (defaultne 8086).
- `database`: Jmeno databaze.
- `retention_policy`: Volitelne, napr. `autogen`.
- `measurement`: Nazev measurement (napr. `kWh`).
- `field`: Nazev field (napr. `value`).
- `entity_id`: ID entity (napr. `solax_drinov_today_s_import_energy`).
- `export_entity_id`: ID entity pro export (napr. `solax_drinov_today_s_export_energy`).
- `username`: Volitelne uzivatelske jmeno.
- `password`: Volitelne heslo.
- `timezone`: Casove pasmo (napr. `Europe/Prague`).
- `interval`: Interval spotreby (napr. `15m`).

### `prodej`
- `koeficient_snizeni_ceny`: Koeficient snizeni ceny denniho trhu (Kc/MWh).

### `price_provider`
- Zdroj cen pro dnesek/zitrek (`spotovaelektrina.cz` nebo `ote-cr.cz`).
- V konfiguraci add-onu je tato polozka jako vyber (radio volby).
- Historie v lokalni cache (`/config/elektroapp/prices-cache`) zustava zachovana.

## Poznamky

- Add-on bezi na portu 8000, ale primarne se pouziva Ingress panel v HA.
- `tarif.vt_periods` se uklada jako retezec a na backendu se prevadi na seznam.
- Odhad vyuctovani pocita fixni poplatky za cely mesic a variabilni naklady z namerene spotreby.
- Projekce vyuctovani vychazi z prumeru dosavadnich dni v mesici.
- Poplatky se ukladaji do historie podle data zmeny konfigurace, aby zpetne vypocty drzely puvodni hodnoty.
