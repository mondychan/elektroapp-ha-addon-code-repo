# Elektroapp Home Assistant Add-on

Add-on zobrazuje spotove ceny elektriny a vypocitane naklady na zaklade spotreby
z InfluxDB. UI je dostupne pres Home Assistant Ingress (panel v postrannim menu).

# Zdroj dat
Veskera data se stahuji z spotovaelektrina.cz.

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

## Konfigurace

Add-on nacita nastaveni z Home Assistant options (Supervisor). 

### `dph`
- Nasobic DPH, napr. `1.21`.

### `poplatky`
- `komodita_sluzba`: Poplatek za sluzbu obchodu (Kc bez DPH / kWh).
- `poze`: Poplatek POZE (Kc vc DPH / kWh).
- `dan`: Dan z elektriny (Kc vc DPH / kWh).
- `distribuce.NT`: Distribuce pro nizky tarif (Kc vc DPH / kWh).
- `distribuce.VT`: Distribuce pro vysoky tarif (Kc vc DPH / kWh).

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
- `username`: Volitelne uzivatelske jmeno.
- `password`: Volitelne heslo.
- `timezone`: Casove pasmo (napr. `Europe/Prague`).
- `interval`: Interval spotreby (napr. `15m`).

## Poznamky

- Add-on bezi na portu 8000, ale primarne se pouziva Ingress panel v HA.
- `tarif.vt_periods` se uklada jako retezec a na backendu se prevadi na seznam.
