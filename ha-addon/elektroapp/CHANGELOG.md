# Changelog

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
