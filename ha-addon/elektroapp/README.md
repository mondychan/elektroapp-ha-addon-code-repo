<!-- AUTO-SYNCED FROM mondychan/elektroapp-ha-addon-code-repo:ha-addon/elektroapp/README.md -->
# Elektroapp Home Assistant Add-on

Elektroapp je Home Assistant add-on pro sledovani cen elektriny, vypocet nakladu,
vypocet trzeb z exportu a pokrocilejsi energeticky prehled (baterie, bilance,
historie). UI bezi pres Home Assistant Ingress.

## Co add-on umi

- denni ceny (dnes/zitra) a jejich prepocet na finalni cenu podle poplatku a DPH
- naklady podle importu energie z InfluxDB
- trzby podle exportu energie z InfluxDB
- mesicni souhrn a odhad vyuctovani (mesic/rok)
- planovac spotrebicu (nejlevnejsi okna podle delky programu)
- panel baterie (SoC, vykon, projekce, ETA)
- detailni energeticka bilance (tyden/mesic/rok)
- mesicni heatmapa (cena / nakup / export)
- lokalni cache pro ceny, spotrebu a export kvuli stabilite a mensi zatezi zdroju

## Zdroje cen

Volba pres `price_provider`:

- `spotovaelektrina` (spotovaelektrina.cz)
- `ote` (OTE + prevod EUR/CZK dle CNB)

## Instalace

1. V Home Assistant otevri `Settings > Add-ons > Add-on Store > ... > Repositories`.
2. Pridej URL repozitare s add-onem.
3. V seznamu vyber `Elektroapp` a klikni `Install`.
4. Vypln konfiguraci add-onu.
5. Spust add-on a otevri panel pres Ingress.

## Pouziti

- Otevri Elektroapp z postranniho panelu Home Assistantu.
- V rezimu `Prehled` sleduj ceny, naklady, export, billing a planner.
- V rezimu `Detail` otevres energetickou bilanci, heatmapu a podrobny bateriovy panel.
- V konfiguraci je dostupne rucni obnoveni cen a historie poplatku.

## Konfigurace

Nastaveni se nacita z Home Assistant options (Supervisor).

### Zakladni cast

- `dph`: sazba DPH v procentech (napr. `21`)
- `price_provider`: `spotovaelektrina.cz` nebo `ote-cr.cz`
- `poplatky`: komodita, OZE, dan, systemove sluzby, distribuce VT/NT
- `fixni`: denni/mesicni fixni slozky
- `tarif.vt_periods`: VT intervaly (`HH-HH`, oddelene carkou)
- `prodej.koeficient_snizeni_ceny`: koeficient snizeni ceny denniho trhu (Kc/MWh)

### InfluxDB

- `influxdb.host`, `influxdb.port`, `influxdb.database`
- `influxdb.retention_policy` (volitelne, typicky `autogen`)
- `influxdb.measurement`, `influxdb.field`
- `influxdb.entity_id` (import)
- `influxdb.export_entity_id` (export)
- `influxdb.username`, `influxdb.password`
- `influxdb.timezone` (napr. `Europe/Prague`)
- `influxdb.interval` (napr. `15m`)

### Baterie, energie, forecast

- `battery.*`: entity pro SoC/vykon a parametry baterie
- `energy.*`: entity domu, gridu a PV pro bilanci
- `forecast_solar.*`: entity Forecast.Solar pro projekce

Pokud tyto sekce nejsou kompletni, add-on zustane funkcni i bez pokrocilych
panelu, ale cast metrik/projekci nebude dostupna.

## Poznamky

- Add-on je urceny primarne pro HA Ingress (port 8000 se bezne nepublikuje ven).
- Historie cen zustava v lokalni cache (`/config/elektroapp/prices-cache`).
- `tarif.vt_periods` se na backendu normalizuje na seznam intervalu.
- Pri zmene poplatku se uklada historie, aby starsi vypocty zustaly konzistentni.
