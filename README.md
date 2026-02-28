# Elektroapp Home Assistant Add-on

Elektroapp je Home Assistant add-on, ktery zobrazuje spotove ceny elektriny a
pocita naklady podle spotreby z InfluxDB. UI je dostupne pres Home Assistant
Ingress (panel v postrannim menu).

## Co to dela
- nacte spotove ceny (dnes/zitra) z konfigurovatelneho zdroje (`spotovaelektrina` nebo `ote`)
- historicka data drzi v lokalni cache po dnech (`prices-cache`)
- prepocita cenu na "konecna cena" podle DPH, OZE, dane, systemovych sluzeb a distribuce (VT/NT)
- nacte spotrebu z InfluxDB a spocte naklady za vybrany den
- zobrazi denni graf nakladu/spotreby a mesicni souhrn

## Struktura projektu
- `app/backend` - FastAPI backend (API + vypocty + InfluxDB dotazy)
- `app/backend/main.py` - bootstrap aplikace (container + routery + staticke soubory)
- `app/backend/app_service.py` - business logika a handlery endpointu
- `app/backend/routers/api_router.py` - API routy (`/api/*`)
- `app/backend/container.py` - config/dependency container
- `app/backend/services/influx_service.py` - Influx query service vrstva
- `app/backend/pricing.py` - cenove a tarifni vypocty
- `app/backend/influx.py` - helpery pro Influx query formaty/intervaly
- `app/backend/billing.py` - vypocty fixnich slozek vyuctovani
- `app/backend/battery.py` - helpery pro slotovy profil baterie/spotreby
- `app/backend/cache.py` - helpery pro cache stari a kompletni dny
- `app/backend/api.py` - casova API utilita (timezone, parse range)
- `app/frontend` - React frontend (grafy a UI)
- `ha-addon/elektroapp` - Home Assistant add-on manifest a metadata
- `dockerfile` - multi-stage build (frontend build -> backend image)
- `.github/workflows/ci.yml` - CI (backend lint/test, frontend lint/test, docker build)
- `.github/workflows/release.yml` - release po tagu (docker publish + sync HA repo)

## Dva repozitare a jejich role
Tento repo (`elektroapp-ha-addon-code-repo`) obsahuje zdrojaky a build add-onu.
Druhy repo (`elektroapp-ha-addon`) slouzi jen jako Home Assistant add-on store
repo, ze ktereho Supervisor nacita metadata a soubory add-onu.

Synchronizace slozky `ha-addon/elektroapp` do `elektroapp-ha-addon` probiha
automaticky v release workflow po uspesnem Docker publish.

## Instalace do Home Assistant
1. V HA: Settings > Add-ons > Add-on Store > ... > Repositories.
2. Pridat URL GitHub repozitare s add-onem.
3. V seznamu add-onu vybrat "Elektroapp" a kliknout Install.
4. Otevrit konfiguraci add-onu, vyplnit InfluxDB a tarifni parametry.
5. Start add-onu a otevrit panel (Ingress).

Detailni navod i seznam konfiguracnich poli je v `ha-addon/elektroapp/README.md`.

## Konfigurace (zaklad)
Konfigurace se nacita z HA options (`/data/options.json`), pro lokalni beh z
`app/backend/config.yaml`.

Nejdulezitejsi polozky:
- `dph` - DPH v procentech (napr. `21`)
- `price_provider` - zdroj cen (`spotovaelektrina` nebo `ote`)
- `poplatky.*` - komodita, OZE, dan, systemove sluzby, distribuce (VT/NT)
- `fixni.*` - fixni poplatky (denni/mesicni)
- `tarif.vt_periods` - VT intervaly ve formatu `HH-HH`, oddelene carkou
- `influxdb.*` - host/port, database, measurement, field, entity_id, timezone
- `influxdb.export_entity_id` - entity_id pro export (prodej) energie
- `prodej.koeficient_snizeni_ceny` - koeficient snizeni ceny denniho trhu (Kc/MWh)

Priklad:
```yaml
dph: 21
price_provider: spotovaelektrina
poplatky:
  komodita_sluzba: 0.35
  oze: 0.0
  dan: 0.0283
  systemove_sluzby: 0.16424
  distribuce:
    NT: 0.1165
    VT: 0.75477
fixni:
  denni:
    staly_plat: 4.18
  mesicni:
    provoz_nesitove_infrastruktury: 12.87
    jistic: 710
tarif:
  vt_periods: "6-7,9-10,13-14,16-17"
influxdb:
  host: "192.168.1.10"
  port: 8086
  database: "homeassistant"
  retention_policy: "autogen"
  measurement: "kWh"
  field: "value"
  entity_id: "your_entity_id"
  export_entity_id: "your_export_entity_id"
  username: "elektroapp"
  password: "CHANGE_ME"
  timezone: "Europe/Prague"
  interval: "15m"
prodej:
  koeficient_snizeni_ceny: 390
```

Poznamka: v InfluxDB je potreba mit uzivatele a spravne credentials.


## Automatizovany release flow
Release je rozdelen na:
- lokalni pripravu release (`tools/release.ps1`)
- CI publish po pushi tagu `vX.Y.Z` (`.github/workflows/release.yml`)

### 1) Jednorazove nastaveni GitHub secrets
V code repo nastav:
- `DOCKERHUB_USERNAME` - username do Docker Hubu
- `DOCKERHUB_TOKEN` - Docker Hub access token s push opravnenim
- `HA_REPO_TOKEN` - GitHub PAT s write pristupem do `mondychan/elektroapp-ha-addon`

### 2) Priprava release lokalne
Vytvor release notes soubor, napr. `notes/0.1.61.md`:
```md
- kratky souhrn zmen
- dalsi bod changelogu
```

Spust:
```powershell
powershell -ExecutionPolicy Bypass -File .\tools\release.ps1 `
  -Version 0.1.61 `
  -NotesFile notes/0.1.61.md
```

Skript:
- zvedne verzi v `ha-addon/elektroapp/config.yaml` (`version` i `ADDON_VERSION`)
- vlozi novou sekci `## 0.1.61` do `ha-addon/elektroapp/CHANGELOG.md`
- vytvori commit `Release 0.1.61`
- vytvori tag `v0.1.61`
- pushne commit i tag na `origin`
- toleruje necommitnuty `notes/X.Y.Z.md` soubor (do commitu ho nepridava)

### 3) CI po tagu udela publish
Workflow `release.yml` po pushi tagu:
1. zkontroluje shodu tagu s verzemi v `ha-addon/elektroapp/config.yaml`
2. udela Docker buildx multi-arch build (`linux/amd64`, `linux/arm64/v8`)
3. pushne image do Docker Hubu:
   - `mondychan/elektroapp-ha:X.Y.Z`
   - `mondychan/elektroapp-ha:latest`
4. synchronizuje `ha-addon/elektroapp` do repo `mondychan/elektroapp-ha-addon`
   a provede commit `Release X.Y.Z`

## Aktualizace add-onu v Home Assistant
1. Dokonci release flow vyse (lokalni skript + uspesny CI workflow).
2. V Home Assistant otevri Add-on Store a dej "Check for updates".
3. U add-onu "Elektroapp" klikni Update a pak Restart.

Poznamka: pokud se update nezobrazi, pomuze restart Home Assistant Supervisoru
nebo docasne odinstalovani a znovu nainstalovani add-onu.

## Plny postup pri zmene kodu (release flow)
1. Uprav kod (backend/frontend/add-on).
2. Priprav `notes/X.Y.Z.md` s body changelogu.
3. Spust `tools/release.ps1 -Version X.Y.Z -NotesFile notes/X.Y.Z.md`.
4. Pockej na dokonceni GitHub Actions workflow `Release`.
5. V Home Assistant: Add-on Store -> "Check for updates" -> Update -> Restart.

Poznamky:
- Tag `vX.Y.Z` musi odpovidat hodnotam `version` a `ADDON_VERSION`.
- Pokud release workflow selze, image ani HA metadata se nepublikuji.
- Pokud HA update nevidi, pomuze restart Supervisoru nebo reinstall add-onu.

## API
Backend poskytuje napr.:
- `GET /api/prices` (spotove ceny + vypoctena cena)
- `POST /api/prices/refresh` (vynucene obnoveni cen pro dnesek/zitrek)
- `GET /api/costs?date=YYYY-MM-DD` (naklady podle spotreby)
- `GET /api/export?date=YYYY-MM-DD` (prodej podle exportu)
- `GET /api/daily-summary?month=YYYY-MM` (mesicni souhrn)
