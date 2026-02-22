# Changelog

## 0.1.57
- Baterie/Forecast entities: tolerantnejsi nacitani z InfluxDB pri rozdilu `entity_id` formatu (`sensor.xxx` vs `xxx`), aby nove battery/forecast sekce fungovaly bez rucniho upravovani prefixu.

## 0.1.56
- Baterie: novy panel "Baterie a projekce" (SoC, tok, ETA, historie, projekce) + podpora Forecast.Solar metrik.
- Baterie: hybridni projekce SoC (Forecast.Solar + historicky profil spotreby/PV) s fallbackem na trend; rozliseni pracovni den/vikend.
- UI: horni KPI pas (cena ted, dnes min/max, naklad, export, netto, stav baterie).
- UI: novy rezim "Detail" s full-width rozlozenim.
- UI/API: novy modul "Vyroba vs spotreba" (tyden/mesic/rok; PV, spotreba domu, grid import/export).
- UI/API: nova mesicni heatmapa historie (cena / nakup / export) s klikem na den pro detail.
- Grafy: jemne anotace v detailu (VT/NT podbarveni, markery start/stop nakupu/exportu).
- Konfigurace: nove sekce `battery`, `energy`, `forecast_solar` v add-on options/schema.

## 0.1.55
- Cache spotreby/exportu: historicky den se uz nebere z nedokoncene cache vytvorene behem dne (donuti se refresh z InfluxDB).
- Cache spotreby/exportu: verze klice cache navysena, aby se prepoctly starsi cache po oprave logiky vykresleni useku.

## 0.1.54
- Naklady/nakup: opraven vypocet po preruseni nakupu behem dne (novy usek se znovu vykresli po navratu odberu ze site).
- Export/prodej: stejna oprava pri resetu/poklesu kumulativniho citace behem dne.

## 0.1.53
- Release: navyseni verze addonu na `0.1.53`.

## 0.1.52
- Ceny: pro vypocty `costs/export` se pri dotazu na dnesek netaha zbytecne i zitrsi den.
- Provider: odstraneny cross-fallback mezi zdroji; pouziva se striktne jen zvoleny `price_provider` (+ jeho cache).
- Influx fallback: presnejsi UI hlaska (`Dotaz na InfluxDB selhal...`) misto zavadejiciho textu.
- Influx fallback: detailnejsi logovani duvodu (napr. 401/timeout) pri prepnuti na cache.

## 0.1.51
- OTE SOAP request: doplnen `SOAPAction` pro `GetDamPricePeriodE`.
- OTE endpoint: fallback pokus pres `http://www.ote-cr.cz/services/PublicDataService`, pokud `https` selze.
- Stabilita: dalsi zjemneni fallback logiky pri docasnych chybach OTE.
- Ceny: dotazy pro `costs/export` dnes uz nestahuji i zitrsi den.
- Influx fallback: upraven text hlasky v UI a pridane detailnejsi logovani duvodu fallbacku.

## 0.1.50
- OTE: odolnost proti HTTP 500 (fallback na cache/spot provider), aby API nepadalo 500.
- OTE: cooldown po chybe, aby se pri vypadku zbytecne neopakovaly requesty.
- HA konfigurace: `price_provider` je vyber (radio volby) s hodnotami `spotovaelektrina.cz` a `ote-cr.cz`.
- Provider parser: akceptuje i alias `ote.cz`.

## 0.1.49
- Ceny: pridana podpora volby zdroje (`spotovaelektrina` / `ote`).
- OTE: nacitani dat z ote-cr.cz + prevod EUR/CZK podle CNB.
- API/UI: rucni refresh cen dnes/zitra a zobrazeni aktivniho zdroje.
- Cache: zachovana kompatibilita historickych dat v `prices-cache`.

## 0.1.48
- UI: premenovani nakupu/prodeje v souhrnu a vyuctovani + barevne odliseni.
- Historie poplatku: koeficient snizeni ceny i pro historicke vypocty.

## 0.1.47
- Prodej: podpora exportu z InfluxDB + koeficient snizeni ceny denniho trhu.
- UI: novy graf prodeje/exportu a rozsireny mesicni souhrn.

## 0.1.46
- Docker: update runtime base image to python:3.14-slim.

## 0.1.45
- Docker: update base images to node:22-alpine and python:3.13-slim.
- Backend: FastAPI/Uvicorn loosened to latest compatible versions at build time.

## 0.1.44
- Konfigurace: potvrzeni smazani ma 5s odpoctem + cervene zvyrazneni.

## 0.1.43
- Konfigurace: oprava tlacitek Upravit/Smazat u historickych poplatku.

## 0.1.42
- Spotreba: cache spotreby z InfluxDB (lokalni zaloha + mene dotazu).
- Konfigurace: prehled cache cen a spotreby v konfiguraci.
- UI: oznaceni dat z cache pri nakladech/spotrebe.

## 0.1.41
- Konfigurace: editace Platne od/do u historickych poplatku + kontrola prekryvu.

## 0.1.40
- Konfigurace: mazani historickych poplatku s dvojitym potvrzenim (mimo aktualni).
- Konfigurace: kontrola duplicitnich datumu v historii poplatku.

## 0.1.39
- UI: ikony auto-refresh prepinace vlevo/vpravo pro jasny stav.

## 0.1.38
- UI: opravene zobrazeni ikon v prepinaci auto-refresh.

## 0.1.37
- UI: auto-refresh grafu (ceny + naklady dnes) s prepinacem.
- Konfigurace: historie poplatku s moznosti uprav (bez mazani).
- API: /api/fees-history pro cteni a ukladani historie poplatku.

## 0.1.36
- UI: zvyrazneni aktualniho 15m slotu v grafu cen (carkovana cara).
- UI: Odhad vyuctovani prehled (sjednocene fixni poplatky, upravene popisky).
- Billing: rocni prehled nehada chybu pri mesicich bez dat.

## 0.1.35
- UI: temny/svetly prepinac s ikonami a opravenym zarovnanim.

## 0.1.34
- API: spatne formaty date/start/end vraci 400 misto 500.
- UI: refaktor do komponent + presun inline stylu do CSS.

## 0.1.33
- UI: grafy cen v blokovem ramecku.

## 0.1.32
- InfluxDB: chyba i v "Naklady a spotreba" pri spatnem entity_id.

## 0.1.31
- InfluxDB: jasna chyba pri spatnem entity_id (souhrn/odhad/naklady).
- Konfigurace: cache bez sloupce jednotka.

## 0.1.30
- Konfigurace: zarovnani sloupcu v cache tabulce.

## 0.1.29
- Konfigurace: pevne sirky sloupcu v tabulce.

## 0.1.28
- Konfigurace: cache prehled sjednocen do tabulky.

## 0.1.27
- Odhad vyuctovani: upravene popisky + projekce skryta pro minulost.
- Konfigurace: prehled jako tabulka.
- Ceny zitra: oprava cache prazdnych dat.

## 0.1.26
- Ceny: DPH v % + poplatky bez DPH (vc. fixnich).
- Vyuctovani: odhad mesic/rok + projekce a historie poplatku.

## 0.1.25
- Planovac: ulozeni posledni delky + spusteni pres Enter.

## 0.1.24
- Planovac: oprava zadavani delky (backspace) + validace 1-360 minut.

## 0.1.23
- Aktualizace release postupu v README.

## 0.1.22
- Planovac: delka 1-360 minut, bez auto-doplnovani 15.

## 0.1.21
- Planovac: input delky programu jako text (bez auto-doplnovani).

## 0.1.20
- Oprava ESLint warning (nepouzity ComposedChart).

## 0.1.19
- Planovac: oprava inputu pro delku programu.

## 0.1.18
- Fix: storage path fallback na /config/elektroapp pri prazdnem ELEKTROAPP_STORAGE.

## 0.1.17
- Cache vzdy zapis do /config/elektroapp (bez fallbacku na lokalni slozku).

## 0.1.16
- Vytvoreni /config/elektroapp pri startu + backup konfigurace pri ulozeni.

## 0.1.15
- Persistentni uloziste v /config/elektroapp pro cache i backup nastaveni.

## 0.1.14
- Graf nakladu/spotreby rozdelen na dva panely.
- Upravena barva odkazu ve footeru.

## 0.1.13
- Planovac: zobrazeni casu do startu okna.

## 0.1.12
- Planovac: jen budoucnost, top 3 neprekryvaji se, den odstranen.
- Planovac a souhrn zarovnany podle poradi tlacitek.

## 0.1.11
- Planovac tlacitko presunuto k prepinacum.
- Dark mode pozadi sjednoceno s HA (#1C1C1C).

## 0.1.10
- Planovac schovany pod tlacitko + jen top 1 navrh s jasnym datumem.

## 0.1.9
- Planovac spotrebicu (navrhy oken podle ceny).
- Casovac pro prednacteni zitrka (kazdou hodinu od 13:05).

## 0.1.8
- Linka = cena (Kc), sloupce = spotreba (kWh).

## 0.1.7
- Zobrazeni verze doplnku ve footeru misto aktualniho casu.
- UI hlaska pri chybe pripojeni na InfluxDB.
- Konfigurace rozdelena na ceny a cache ve dvou sloupcich.

## 0.1.6
- Osa grafu nakladu/spotreby spravne mapuje Kc a kWh.

## 0.1.5
- Skryt cache status v konfiguraci + velikost cache.
- Mesicni souhrn necte budoucni dny.
- Odkaz na GitHub repo v manifestu.

## 0.1.4
- Cache cen do /data + logy cache pri startu a pri stahovani.

## 0.1.3
- Prvni verejna verze add-onu.
