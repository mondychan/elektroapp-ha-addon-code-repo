<!-- AUTO-SYNCED FROM mondychan/elektroapp-ha-addon-code-repo:ha-addon/elektroapp/README.md -->
# Elektroapp Home Assistant Add-on

Elektroapp je panel pro domaci energetiku v Home Assistantu. Bere spotove ceny elektriny, prepocita je podle vlastniho tarifu a spoji je s realnymi daty ze senzoru, InfluxDB, baterie, fotovoltaiky a Portalu namerenych dat CEZ Distribuce.

Vysledkem je jedno misto, kde je videt cena, spotreba, vyroba, export, baterie, odhad vyuctovani a rozdil mezi lokalnim merenim a oficialnim elektromerem.

## K cemu slouzi

- Ukazuje spotove ceny dnes a zitra jako konecnou cenu v Kc/kWh vcetne DPH, distribuce, OZE, dane a vlastnich stalych plateb.
- Pocita naklady na spotrebu a vynos z exportu podle 15minutovych slotu a dat ulozenych v InfluxDB.
- Zobrazuje prehled domu: spotreba, vyroba FV, import ze site, export do site a stav baterie.
- Odhaduje mesicni a rocni vyuctovani podle skutecne spotreby, exportu, tarifu a fixnich plateb.
- Porovnava lokalni mereni ze stridace s oficialnimi daty z PND, pokud je PND zapnute.
- Pripravuje doporuceni pro spotrebu, baterii a export. Doporuceni jsou informacni, doplnek sam neridi Home Assistant automatizace.
- Umi zobrazit vlastni Home Assistant entity v samostatne sekci HP, pokud je zapnes v konfiguraci.

## Hlavni sekce v UI

- **Prehled**: rychly stav cen, toku energie, baterie, FV predpovedi, denni bilance a mesicniho souhrnu.
- **Detail**: graf ceny, nakladu, exportu, heatmapa historie a prace s konkretnim dnem.
- **Doporuceni**: akcni radky typu spustit spotrebic, setrit baterii, nabit baterii, exportovat nebo bez akce.
- **Baterie**: SoC, vykon, denni nabijeni/vybijeni a odhad casu do nabiti nebo vybiti.
- **Solary / FV**: forecast vyroby a navazujici cenovy kontext.
- **Sit / PND**: import dat z Portalu namerenych dat CEZ Distribuce a srovnani s lokalnimi senzory.
- **Mesicni prehled**: souhrny spotreby, exportu, nakladu a odhad vyuctovani.
- **Statistiky**: srovnani vykonu a energeticka bilance za tyden, mesic nebo rok.
- **Nastaveni**: kontrola konfigurace, cache, diagnostika a historie poplatku.

## Co je potreba nakonfigurovat

Zakladni nastaveni se vyplnuje v konfiguraci add-onu v Home Assistantu.

- `price_provider`: zdroj spotovych cen, bud `spotovaelektrina.cz`, nebo `ote-cr.cz`.
- `poplatky`, `fixni`, `tarif`: slozky ceny, VT/NT intervaly a stale platby.
- `influxdb`: pripojeni k InfluxDB a entity pro import/export energie.
- `battery`: entity baterie, kapacita, rezerva, ucinnost a limity pro odhad nabijeni/vybijeni.
- `energy`: entity pro spotrebu domu, import/export ze site a FV vykon.
- `forecast_solar`: volitelne Forecast.Solar entity pro predpoved FV vyroby.
- `pnd`: volitelne prihlaseni do Portalu namerenych dat CEZ Distribuce.
- `hp`: volitelna sekce HP pro sledovani vybranych Home Assistant entit.

## Instalace

1. V Home Assistantu otevri `Settings > Add-ons > Add-on Store`.
2. V menu repozitaru pridej URL `https://github.com/mondychan/elektroapp-ha-addon`.
3. Vyber add-on `Elektroapp` a nainstaluj ho.
4. Vypln konfiguraci podle svych senzoru, tarifu a zdroju dat.
5. Spust add-on a otevri ho z postranniho panelu Home Assistantu.

## Data a cache

- Historie cen a PND dat se uklada lokalne, aby prehled fungoval i pri docasnem vypadku externich sluzeb.
- Spotove ceny se nacitaji ze zvoleneho zdroje a pri vypoctech se kombinuji s nastavenymi poplatky.
- PND import je volitelny. Bez nej funguje cenovy prehled, InfluxDB vypocty, baterie, FV i doporuceni podle dostupnych lokalnich dat.
- InfluxDB je potreba pro historicke vypocty spotreby, exportu, bilance a vyuctovani.
