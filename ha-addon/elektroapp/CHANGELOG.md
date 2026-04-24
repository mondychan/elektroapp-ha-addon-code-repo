# Changelog

## 0.3.25
- Oprava spodni mobilni navigace: aktivni prouzek je centrovany bez konfliktu s animacnim transformem a sedi nad aktivni zalozkou.

## 0.3.24
- Oprava mobilniho zobrazeni tabulky Mesicni souhrn: na uzkych displejich se radky skladaji do kompaktniho gridu bez horizontalniho posouvani.
- Tabulka Mesicni souhrn uz nereaguje na horizontalni swipe pro zmenu mesice, aby gesto nekolidovalo s prohlizenim hodnot.

## 0.3.23
- Nova samostatna karta Doporuceni s plannerem dostupnym primo z hlavni navigace.
- Doporuceni a planovac byly odebrany z preplneneho Prehledu a Detailu.
- HP grafy se vykresluji jako spojnicove grafy i u ridkych dat s mezerami.
- HA add-on schema pro zdroj cen zobrazuje jen citelne volby `spotovaelektrina.cz` a `ote-cr.cz`; backend dale pracuje s kompatibilnimi internimi hodnotami.
- Viditelne nazvy cenovych nastaveni v HA add-onu byly sjednoceny pod cenove poplatky pro lepsi orientaci bez breaking migrace ulozenych optionu.

## 0.3.22
- Hotfix: backend uz pri Vite buildu nemountuje neexistujici `frontend_build/static` a podporuje novy `frontend_build/assets` adresar.
- Pridan regresni test, ze Vite assets layout lze servirovat bez CRA `static` slozky.

## 0.3.21
- Frontend build migrovan z CRA/react-scripts na Vite, testy na Vitest a Docker/CI build vystup na `dist`.
- Backend doplnen o explicitni application container, typed request payloady, mutacni API guard, diagnostiku a request latency logging.
- Influx query builder nyni centralne escapuje identifikatory/tag values a validuje intervaly/agregace.
- Cache zapisy jsou atomicke a sdili metadata kontrakt s `cache_version`, `key`, `fetched_at`, `complete_after`, `source` a `status`.
- Dashboard snapshot vraci rozsireny payload pro prvni obrazovku vcetne cen dnes/zitra/vybraneho data, diagnostiky a doporuceni bez duplicitniho prvotniho volani cen.
- Pridana read-only karta Doporuceni a endpoint `/api/recommendations` s akcnimi radky pro spotrebu, baterii, FV vyrobu a export.

# Seznam změn

## 0.3.13
- HP overrides: přidána podpora formátování hodnot pomocí `value_format`, včetně převodu trvání ze sekund, minut nebo hodin do čitelného textu.
- HP UI: do editoru override pravidel přidána pole pro formát hodnoty, styl zobrazení trvání a maximální počet zobrazovaných částí.
- HP karty a tooltipy: formátování trvání se nyní použije v KPI kartách, sekundárních statistikách, status kartách i v tooltipu grafu.

## 0.3.12
- HP discovery: oprava načítání konfigurace, aby parametry `source_mode`, `scan`, `defaults` a `overrides` zůstaly zachovány i za běhu a nebyly zahazovány zavaděčem backendu.
- HP regex/prefix scan: skenované entity se v produkčních sestaveních nyní skutečně načítají z uložené konfigurace.

## 0.3.11
- HP discovery: v režimech `prefix` a `regex` se nyní skenované entity a ručně zadané `hp.entities` slučují, místo aby se vzájemně vylučovaly.
- HP precedence: pokud stejná entita existuje ve výsledcích skenování i v `hp.entities`, má nyní přednost explicitní ruční konfigurace entity.
- HP odolnost: ručně zadané entity zůstávají aktivní, i když je skenování nenajde nebo selže zjišťování stavu v Home Assistantovi.

## 0.3.10
- HP discovery: přidány režimy zdroje `manual | prefix | regex` s nastavením skenování, výchozími hodnotami, filtrováním pomocí allowlistu/blocklistu a přepisováním (overrides) pro jednotlivé entity.
- Integrace Home Assistant: přidána podpora pro hromadné zjišťování stavů a odvozování metadat za běhu pro skenované HP entity.
- HP UI: rozšířen konfigurační panel o náhled zjišťování a úpravu přepisů pro skenované entity.

## 0.3.9
- HP KPI: kliknutí na kartu KPI nyní posune zobrazení na odpovídající graf, pokud má daná entita vykreslený graf.
- HP grafy: vylepšena viditelnost řídkých datových řad pomocí bodových značek a omezení tooltipu vlevo/vpravo, aby zůstal uvnitř viditelné oblasti grafu; řádky tooltipu nyní zalamují dlouhé popisky a hodnoty místo přetékání.
- Synchronizace se Supervisorem: přidána silnější diagnostika za běhu pro selhání synchronizace možností doplňku, včetně podrobností o odeslaných datech a odpovědích z API Supervisora.

## 0.3.8
- Schéma doplňku: sjednocení hodnot `price_provider` s normalizovanými volbami backendu a doplnění chybějícího bloku `alerts` do `options/schema`.
- Oprava synchronizace konfigurace Supervisora: zabránění chybě `400 Bad Request` při ukládání konfigurace z webového rozhraní kvůli neshodě schématu v metadatech doplňku.

## 0.3.7
- Ukládání konfigurace HP: odstranění polí s hodnotou `null` před synchronizací do voleb Supervisora a zobrazení lepších podrobností o chybách Supervisora, což opravuje selhání `POST /api/config` při přidávání HP entit z webového rozhraní.
- Oprávnění doplňku: explicitní povolení `hassio_api` pro přístup k API Supervisora v přísnějších prostředích Home Assistanta.
- HP grafy: obnovena interakce při najetí myší a vykreslování externích tooltipů pro čárové grafy, včetně grafů se skrytými bodovými značkami.

## 0.3.6
- HP grafy: zachování viditelných mezer při chybějících datech místo kreslení souvislé čáry přes výpadky nebo chybějící časové úseky.
- HP KPI: hodnota `LAST` zůstává vázána na poslední aktuální hodnotu, zatímco statistiky období jako `AVG`, `MIN`, `MAX` a další sledují vybraný rozsah grafu.
- HP období: týdenní, měsíční a roční grafy nyní vyplňují chybějící úseky hodnotou `null`, takže chybějící dny nebo měsíce zůstávají viditelně prázdné.

## 0.3.5
- Perzistence konfigurace: ukládání konfigurace doplňku do Home Assistant Supervisora přes `/addons/self/options`, takže nastavení HP po restartu doplňku již nemizí.
- Config API: explicitní selhání požadavku na uložení, pokud synchronizace se Supervisorem selže, místo hlášení falešného úspěchu pouze na lokální úrovni.
- Testy: přidáno regresní pokrytí pro synchronizaci voleb Supervisora a scénář perzistence po restartu pro `hp.enabled` a `hp.entities`.

## 0.3.4
- HP UI: zvětšení a vycentrování hlavní hodnoty KPI, skrytí nadbytečné poznámky v patičce KPI a ponechání AVG/MIN/MAX na stejné kartě.
- HP grafy: přidáno přepínání rozsahů `den / týden / měsíc / rok` s odpovídající podporou dotazů na backendu; roční grafy používají vybraný kalendářní rok od ledna do prosince.
- HP konfigurace: konfigurační panel je nyní sbalitelný a po načtení je ve výchozím nastavení sbalený.
- Varování o neaktuálnosti HP: zobrazení červeného varovného banneru pouze v případě, že zobrazené hodnoty HP jsou starší než 60 minut; v opačném případě se stavový varovný blok nezobrazuje.

## 0.3.3
- HP: oprava načítání grafů a sekundárních statistik KPI pro entity používající měření Influxu založená na jednotkách, jako je `°C`; grafy okamžitých řad se nyní dotazují na průměry časových úseků.
- HP UI: horní dlaždice KPI na kartě HP nyní používají kompaktní rozvržení karet místo roztahování jedné dlaždice přes celý řádek.
- Synchronizace konfigurace: upřednostnění trvalých přizpůsobených zálohovaných voleb před nově vygenerovanými výchozími volbami HA po aktualizaci nebo přeinstalaci doplňku.

## 0.3.2
- Oprava CI vydání: test statického servírování již neimportuje celý bootstrap aplikace FastAPI, takže testy backendu se nepokoušejí inicializovat cesty `/data` v GitHub Actions.

## 0.3.1
- Hotfix: zakázání cachování indexu SPA, aby se předešlo chybám 404 u neaktuálních hashovaných prostředků po aktualizaci nebo restartu doplňku.
- HP: odvozování kandidátů pro měření Influxu z metadat Home Assistanta, vylepšení diagnostiky prázdných dat a zobrazení sekundárních statistik KPI na stejné kartě.

## 0.3.0
- Počáteční integrace tepelného čerpadla: nová karta HP s kartami KPI, stavovými kartami, denními grafy, konfigurovatelnými HP entitami a automatickým vyplňováním metadat z Home Assistanta.

## 0.2.26
- Fix: vrácena exkluzivita process locku schedulerů; čerstvý lock se už nemaže jen kvůli shodnému PID.
- Fix: PND scheduler je zpět kompatibilní se službami a test doubles bez `find_first_missing_date`, takže CI opět prochází.
- Dependencies: backend aktualizován na `fastapi>=0.128.6` a `starlette>=0.41.1`, čímž mizí `python_multipart` deprecation warning v testech.
- Repo cleanup: odstraněn zastaralý `future_implementation_plan.md`.

## 0.2.25
- **PND a robustnost (Fix)**: Vyřešen problém se "zaseknutými" zámky schedulerů v Docker prostředí (HA Addon). Systém nyní spolehlivěji detekuje a uvolňuje staré zámky i při opakovaném přidělení stejného PID po restartu kontejneru.
- **PND doplňování historie (Vylepšení)**: Vylepšena logika detekce mezer v datech. Plánovač již nekontroluje pouze včerejšek, ale prohledává celé 31denní okno a automaticky doplňuje chybějící dny od nejstarší nalezené mezery.

## 0.2.24
- **Hotfix (Plánovače)**: Oprava kritické chyby (Undefined name) v plánovači cen, která znemožňovala start add-onu ve verzi 0.2.23.

## 0.2.23
- **Fix stability (Plánovače)**: Oprava "zaseknutých" zámků po restartu add-onu. Systém nyní detekuje, zda proces držící zámek stále běží, a pokud ne, automaticky jej uvolní. To zajišťuje, že se PND sync a stahování cen spustí okamžitě po každém restartu.

## 0.2.22
- **UI (PND portál)**: Změna formátu data v přehledové tabulce z ISO (`RRRR-MM-DD`) na český standard (`DD.MM.RRRR`).
- **Vylepšení PND (Portálu naměřených dat)**:
    *   Automatické doplňování historie: Plánovač nyní dokáže detekovat mezery v datech a stáhnout až 31 dní historie najednou (původně zkoušel jen včerejšek).
    *   Okamžitý catch-up po startu: Pokud v datech chybí včerejšek, systém se pokusí o stažení hned po startu add-onu, nečeká se na noční okno.
    *   Zvýšení robustnosti detekce "zaseknutého" plánovače.
- **Oprava Odhadu vyúčtování**: V historii i v aktuálním přehledu se nyní zobrazuje "čistý" náklad (Náklady měsíce), který již zahrnuje odečet tržeb z prodeje energie.
- **Fix Baterie a projekce**: Opravena chyba v klíčích historických profilů, která způsobovala, že predikce nákupu/výroby ignorovala denní dobu a používala fixní hodnoty.
- **Vylepšení Srovnání výkonu**:
    *   Srovnání dneška probíhá vůči stejnému času včera a minulý týden (např. do 11:00 vs 11:00), což přináší smysluplná procenta.
    *   Opraveny popisky srovnávaných období (původní "Vloni/Včera" nahrazeno konkrétními názvy).
    *   Opraven výpočet procentuální změny při přechodu mezi náklady a tržbami (zápornými hodnotami).

## 0.2.21
- **Vylepšení PND (Portálu naměřených dat)**:
    *   Automatické doplňování historie: Plánovač nyní dokáže detekovat mezery v datech a stáhnout až 31 dní historie najednou (původně zkoušel jen včerejšek).
    *   Okamžitý catch-up po startu: Pokud v datech chybí včerejšek, systém se pokusí o stažení hned po startu add-onu, nečeká se na noční okno.
    *   Zvýšení robustnosti detekce "zaseknutého" plánovače.
- **Oprava Odhadu vyúčtování**: V historii i v aktuálním přehledu se nyní zobrazuje "čistý" náklad (Náklady měsíce), který již zahrnuje odečet tržeb z prodeje energie.
- **Fix Baterie a projekce**: Opravena chyba v klíčích historických profilů, která způsobovala, že predikce nákupu/výroby ignorovala denní dobu a používala fixní hodnoty.
- **Vylepšení Srovnání výkonu**:
    *   Srovnání dneška probíhá vůči stejnému času včera a minulý týden (např. do 11:00 vs 11:00), což přináší smysluplná procenta.
    *   Opraveny popisky srovnávaných období (původní "Vloni/Včera" nahrazeno konkrétními názvy).
    *   Opraven výpočet procentuální změny při přechodu mezi náklady a tržbami (zápornými hodnotami).

## 0.2.20
- **Oprava Odhadu vyúčtování**: V historii i v aktuálním přehledu se nyní zobrazuje "čistý" náklad (Náklady měsíce), který již zahrnuje odečet tržeb z prodeje energie.
- **Fix Baterie a projekce**: Opravena chyba v klíčích historických profilů, která způsobovala, že predikce nákupu/výroby ignorovala denní dobu a používala fixní hodnoty.
- **Vylepšení Srovnání výkonu**:
    *   Srovnání dneška probíhá vůči stejnému času včera a minulý týden (např. do 11:00 vs 11:00), což přináší smysluplná procenta.
    *   Opraveny popisky srovnávaných období (původní "Vloni/Včera" nahrazeno konkrétními názvy).
    *   Opraven výpočet procentuální změny při přechodu mezi náklady a tržbami (zápornými hodnotami).

## 0.2.19
- fix overnight solar forecast handling so `forecast so far` stays unknown until the first real PV samples arrive
- avoid misleading early-morning `delta so far` when the forecast provider reports `remaining today = 0`
- add regression coverage for the midnight/no-samples scenario

## 0.2.18
- fix solar forecast timezone handling so hourly history/backfill respects configured Influx timezone on Linux/CI
- add regression test for UTC host with Europe/Prague forecast data
- run backend and frontend tests inside release flow before version bump, tag and push

## 0.2.17
- solarni forecast v2 pridava hodinovy bias z historickych dat a systemove upraveny odhad dnes i zitra
- forecast karta nyni ukazuje raw Forecast.Solar vedle lokálně kalibrovanych hodnot a diagnostiku zdroje profilu
- podpora novych Forecast.Solar entit `power_production_next_hour`, `power_production_next_12hours` a `power_production_next_24hours`

## 0.2.16
- solarni forecast nyni umi doplnit historickou kalibraci z InfluxDB bez cekani na nove dny v runtime cache
- backfill preferuje forecast "zitra" z predchoziho dne a pada zpet na denni last/max u `energy_production_today`
- release flow nyni pri vydani pripomina kontrolu `README.md` a `ha-addon/README.md` u novych nebo zasadne zmenenych core funkci

## 0.2.13
- Privacy: generalizace konfiguračních šablon (odstraněny názvy jako 'drinov', IP adresy a konkrétní entity).
- Privacy: důsledná kontrola a ujištění, že v repo nejsou žádná hesla ani osobní údaje.

## 0.2.12
- Design: KPI dlaždice jsou opět statické (klikatelnost zrušena na přání uživatele).

## 0.2.11
- Fix: oprava chyby při buildu (missing tomorowData destructuring).
- Fix: graf cen na zítřek je nyní plně funkční.

## 0.2.10
- Fix: vrácen graf cen pro zítřek na hlavní obrazovku. Graf se zobrazuje automaticky pouze tehdy, když jsou data pro další den k dispozici.
- Fix: stabilizace rozvržení hlavní stránky (tlačítka už neodskakují při otevírání panelů).

## 0.2.8
- Fix: moduly (Statistiky, Baterie, atd.) se nyní otevírají přímo pod svým tlačítkem pro lepší UX.
- Feature: dlaždice KPI (Baterie, Ceny, Náklady) jsou nyní klikatelné a aktivují příslušné sekce nebo pohledy.
- Fix: opraveno nefunkční tlačítko "Baterie a projekce" na hlavní stránce.

## 0.2.7
- Design: vylepšené rozvržení PND srovnávací tabulky s víceúrovňovou hlavičkou pro lepší přehlednost skupin Nákup a Prodej.
- Design: přidáno vizuální oddělení skupin dat pomocí vertikálních linek a upravený tón zápatí tabulky.

## 0.2.6
- Style: srozumitelnější textace chybového stavu v PND sekci ("Nebyla zaznamenána žádná chyba").

## 0.2.5
- Fix: zvýšení robustnosti PND testů (pomocí findByRole a regexů) pro stabilnější proběhnutí v CI prostředí s animacemi.

## 0.2.4
- Fix: aktualizace PND testů tak, aby reflektovaly nové skryté sekce UI.
- Stabilizace CI/CD po restrukturalizaci PND portálu.

## 0.2.3
- Fix: odstraněny nepoužívané proměnné v `OverviewPage.tsx`, které blokovaly CI build.
- Stabilizace produkčního sestavení po refaktoringu navigace.

## 0.2.2
- **PND Srovnání s lokálními daty**: Nová srovnávací tabulka v PND portálu pro přímou kontrolu přesnosti lokálních senzorů proti oficiálním datům z distribuce.
- **Navigace v detailu**: Možnost posunu o jeden den do budoucnosti v sekci Cena (zobrazení zítřka) s upozorněním na dostupnost dat.
- **Solární předpověď**: Redesign karty - čistší design bez textů, KPI mřížka a pokročilé informace pod tlačítkem 'Detail'.
- **Statistiky**: Možnost skrytí panelů výkonu a bilance na hlavní obrazovce pod přepínač 'Statistiky'.
- **Heatmapa historie**: Výraznější barevná paleta (Blue-Red) pro lepší vizuální odlišení cenových výkyvů.
- **PND Layout**: Reorganizace stránky PND (Cache nahoře, stavové bloky pod tlačítky) pro lepší přehlednost na mobilu.

## 0.2.1
- oprava overview nacitani cen: karta `Zitra` uz bere publikovana data z kombinovaneho feedu `dnes + zitra` misto jednodennich snapshot cen
- detail dne nadale pouziva samostatny denni endpoint, takze nedochazi k regresi v historickem prohlizeni
- doplnen regresni frontend test pro publikovana data nasledujiciho dne

## 0.2.0
- velky release 0.2.0 s klicovymi opravami presnosti dat
- oprava PND (Portalu namerenych dat): korektni prevod kW na kWh (4x presnejsi data)
- nova funkce "Smazat cache" v UI pro rucni reset PND dat
- oprava Energeticke bilance: zavedena presna detekce jednotek W/kW z InfluxDB (odstraneni astronomickych chyb u nizkych odberu)
- sjednocena logika vypoctu napric celou aplikaci (BatteryService, Insights, Energeticka bilance)

## 0.1.95
- oprava Energeticke bilance: zavedena detekce jednotek (W vs kW) primo z InfluxDB
- odstranena nespolehliva heuristika, ktery zpusobovala astronomicke hodnoty u Wattovych senzoru s nizkym prikonem
- sjednoceno zpracovani vykonu v BatteryService (vse nyni prepocitavano na Watty pro presnejsi projekce)
- vylepsena diagnostika InfluxDB dotazu o metadata jednotek

## 0.1.94
- oprava testovaci sady v CI po zavedeni robustnejsi diagnostiky jednotek
- stabilizace release pipeline

## 0.1.93
- nova funkce "Smazat cache" v UI pro rucni promazani lokalnich PND dat a raw zaloh
- backend podpora pro bezpecne smazani cache souboru a reset stavu integrace
- vylepseny vizualni styl pro nebezpecna tlacitka (hover efekty)
- oprava parsovani kW na kWh z predchoziho releasu je nyni plne ucinna i po rucnim promazani stare cache

## 0.1.92
- robustnejsi detekce jednotek z PND (kontrola globalniho 'unitY' i per-series metadat)
- oprava konverze kW na kWh v pripadech, kdy je jednotka definovana v rootu response
- doplnena diagnostika do recognized_series pro snadnejsi provereni spravne detekce jednotek
- vynuceni prepersonu 15min intervalu pro Energy (kWh) vypocet

## 0.1.91
- oprava vypoctu energetickych hodnot z PND (prevod kW na kWh pro 15min intervaly)
- sjednoceni vice datovych rad (faze L1, L2, L3) do celkove sumy v ramci intervalu
- ignorovani pomocnych rad (maximalni vykony) pro presnejsi soucty spotreby/vyroby
- sjednoceni logiky vypoctu pro JSON API i CSV exporty z PND

## 0.1.90
- oprava synchronizace konfigurace mezi Elektroapp UI a Home Assistant options, aby se zmeny po restartu nevracely na starsi hodnoty
- load configu nove vybira nejaktualnejsi variantu mezi HA options a lokalnim backupem a druhou kopii na ni zrcadli
- doplnene regresni testy pro obousmerny config sync a restartovy scenar

## 0.1.89
- nova PND zalozka s oddelenou konfiguraci, verify, backfill, lokalni cache a schedulerem pro nocni sync vcerejsich dat
- hardening PND adapteru: sjednocene httpx chyby do PNDServiceError, verify login/dashboard/data contractu a detailni diagnostika zmen endpointu nebo HTML/payload struktury
- konfigurovatelne nocni okno syncu, explicitni stavove hlasky v UI a rozsirene backend/frontend testy pro PND flow

## 0.1.88
- chytrejsi projekce baterie: preferuje blizky stav, ukazuje ETA do plna a navazujici pokles k rezerve podle forecastu
- blokace navigace do budoucnosti napric grafy, tabulkami, heatmapou, vyuctovanim a energetickou bilanci
- kompaktnejsi layout grafovych karet a rozsireni solar/forecast diagnostiky vcetne export cache

## 0.1.87
- fix regressions after backend refactor in price map and energy balance service contracts
- restore daily summary, dashboard snapshot price lookups, and energy balance chart loading
- improve energy balance resilience when one Influx entity query fails and add regression tests

## 0.1.86
### ⚡ Hotfix: Frontend & Backend Synergy
- Fix: "toFixed is not a function" - opraven pád v komponentě `SolarForecastCard` způsobený nesprávným formátem dat z backendu.
- Fix: "TypeError: get_prices() takes 1 positional argument but 4 were given" - opravena volání cenové služby napříč celým backendem (Alerts, Price Map, Dashboard).
- Vylepšena robustnost volání interních služeb (přechod na explicitní pojmenované argumenty).

## 0.1.85
### ⚡ Stabilita
- Fix: Synchronizace `package-lock.json` pro úspěšný CI/CD build. 
- (Zahrnuje všechny novinky a opravy z verze 0.1.80, která neprošla buildem na GitHubu).

## 0.1.80
### 🌟 Novinky
- **Export do CSV**: Do tabulky měsíčního souhrnu přidáno tlačítko pro stažení dat ve formátu CSV.
- **Konfigurovatelné prahy**: V nastavení (`config.yaml`) lze nyní upravit prahy pro nízkou a vysokou cenu, které se promítají do alertů a grafů.

### 📱 UI & UX
- **Rozšířená navigace**: Spodní lišta nyní nabízí jasné přepínání mezi Dashboardem, Náklady, Baterií a Nastavením.
- **Vylepšené tabulky**: 
    - Zvýraznění víkendů pro lepší orientaci v historii.
    - Barevné odlišení Netto hodnot (kWh i Kč) podle bilance (zelená pro zisk/prodej, červená pro nákup/náklady).
    - Oprava řazení a sjednocení vizuálního stylu bez podbarvení buněk.

### ⚡ Stabilita
- **TypeScript**: Dokončena migrace klíčových komponent (`App.tsx`, `MonthlySummaryCard.tsx`) a API vrstvy na striktní TypeScript.
- **CI/CD**: Oprava buildovacího procesu, který blokoval předchozí release.
- **Refaktorizace**: Výrazné zmenšení hlavního souboru `App.tsx` a rozdělení logiky do hooků.

## 0.1.79
## 0.1.79 — Velký update analytiky a UI
Tento release přináší kompletní přepracování vnitřní architektury, výrazné zrychlení díky paralelnímu snapshotování dat a nové analytické nástroje.

### 🌟 Novinky
- **Cenové alerty**: Horní banner s upozorněním na extrémní ceny a doporučením spotřeby.
- **Srovnání výkonu**: Nová sekce zobrazující trend spotřeby a nákladů (včera vs před týdnem, včera vs dnes).
- **Solární předpověď**: Dashboard pro FVE s odhadem výroby, špičkami a zbývající energií pro dnešek/zítřek.
- **Cenové prahy v grafu**: Vodorovné čárkované čáry v cenovém grafu pro rychlou identifikaci levných a drahých hodin.

### 📱 Mobilní optimalizace & UI
- **Bottom Nav**: Nová spodní navigace v mobilní verzi pro pohodlné přepínání mezi přehledem a detailem.
- **Smooth Transitions**: Animované přechody mezi stránkami a prvky pomocí `framer-motion`.
- **System Dark Mode**: Automatické přepínání světlého a tmavého režimu podle OS.

### ⚡ Výkon & Stabilita
- **Dashboard Snapshot API**: Načtení všech dat úvodní obrazovky jediným asynchronním požadavkem.
- **Paralelizace na backendu**: Služby pro ceny, Influx a analytiku běží v `asyncio.gather` paralelně.
- **Connection Pooling**: Optimalizace dotazů do InfluxDB pomocí `requests.Session` (pooling spojení).
- **TypeScript**: Migrace většiny frontendu do TS pro vyšší spolehlivost.

### 🔧 Ostatní
- Rozpad `app_service.py` a `App.js` na menší, udržovatelné moduly.
- Vylepšené tabulky a barevné indikace (Netto v denním souhrnu).

## 0.1.78
- Vizuální redesign tabulek: odstraněno podbarvení pozadí buněk a nahrazeno čistším barevným odlišením samotného textu.
- Barvy textu (červená pro nákup/náklady, zelená pro prodej/zisky) jsou optimalizovány pro vysoký kontrast ve světlém i tmavém režimu.
- Záhlaví tabulek jsou nyní neutrální pro lepší profesionální vzhled.
- Sloupce množství energie (kWh) v měsíčním souhrnu jsou nyní bez barevného odlišení.
- V tabulce Odhad vyúčtování se barva celkových nákladů mění dynamicky (červená při platbě, zelená při celkovém zisku).

## 0.1.77
- Pridany sloupce "Netto (kWh)" a "Netto (Kč)" do mesicniho souhrnu pro lepsi prehled o bilanci.
- Barevne odliseni netto hodnot (cervena pro naklady, zelena pro zisky).
- Zobrazeni kladne/zaporne bilance se znamenkem + / -.
- Tabulka je nyni responsivni, coz zlepsuje citelnost na mobilnich zarizenich.

## 0.1.76
- Graf cen spravne odecita zapornou variabilni slozku nejdriv od fixni casti; pod nulu jde az kdyz spot plne pokryje vsechny fixni poplatky.
- Fixni slozka v grafu je stabilni a uz nezahrnuje DPH z variabilni casti; variabilni slozka se naopak zobrazuje jako realna castka vcetne 21% DPH.
- Tooltipy prehledne rozdeluji fixni slozku, zapornou variabilni slozku a konecnou cenu.
- Vylepsena interakce grafu: tooltip se nyni zobrazuje pri najeti kamkoliv do sloupce casoveho slotu (nemusi se jiz zamerovat primo na barevny blok).
- Opraveno zobrazeni meny z `-Kc` na `-Kč`.
- Vypocet pro cenovy graf je presunut do frontendu, aby nakup i prodej energie pouzivaly konzistentni datovou logiku.

## 0.1.75
- fix battery projection chart so the historical SoC line ends at the last real point and only the forecast continues into the future

## 0.1.74
- improve mobile chart readability with responsive time-axis labels
- clamp chart tooltips to the visible viewport on small screens
- make cost chart CZK line cumulative and remove detail start/stop markers
- fix mobile responsiveness of energy balance and history heatmap charts

## 0.1.73
- fix redraw of Chart.js visuals after light/dark theme switch
- stabilize chart time axes to fixed whole-hour labels instead of drifting from current time
- correct price chart legend semantics, remove in-chart pin/start-stop labels, and make export revenue cumulative
- repair battery timeline rendering and heatmap theme colors in overview and detail views

## 0.1.72
- Oprava CI releasu po Chart.js migraci: timezone-agnosticke parsovani slotu a casovych labelu uz nevychazi z runtime timezone procesu.
- Testy pro `BatteryProjectionCard` a `Cost/Export` builders jsou stabilni i v GitHub Actions prostredi bezícim v UTC.
- Frontend test suite i produkcni build po oprave znovu prosly uspesne.

## 0.1.71
- Frontend grafy migrovany z `recharts` na centralni Chart.js vrstvu s internimi builders, wrappery, tooltipy a anotacemi.
- `Cena`, `Naklady a nakup`, `Prodej a export`, `Baterie a projekce`, `Vyroba vs spotreba` i `Heatmapa historie` ted pouzivaji sjednoceny charting stack.
- Combo grafy pro naklad/export sjednocuji linku a sloupce do jednoho zobrazeni, heatmapa bezi pres matrix chart a interakce typu pin slotu zustaly zachovane.
- Testy byly prepojene na novou charting vrstvu a frontend build i test suite prosly bez chyby.

## 0.1.70
- Planovac spotrebicu po kliknuti na `Zobrazit planovac` rovnou nacte a zobrazi doporucena okna pro 120 minut.
- Desktop layout planneru je srovnany: tlacitko `Vlastni`, stav `Vybrano` i akce `Najit okna` uz nejsou zbytecne rozsypane do dalsich radku.
- Frontend testy overuji automaticke nacteni planneru pro 120 minut pri otevreni panelu.

## 0.1.69
- Planovac spotrebicu ma misto volneho inputu rychle volby delky programu (30-300 min) s okamzitym hledanim oken.
- Tlacitko `Vlastni` zachovava puvodni rucni zadani delky a validaci pro rozsah 1-360 minut.
- Frontend testy nove kontroluji, ze klik na preset rovnou vola planner API se spravnou delkou.

## 0.1.68
- Frontend: sjednocene date navigatory napric aplikaci (den/mesic/rok) s jednotnym modernim popover stylem.
- Nove sdilene komponenty `DateNavigator`, `MonthNavigator`, `YearNavigator` pouzite ve vsech dosavadnich date selector pozicich.
- Detail, naklady, export, mesicni souhrn, heatmapa, billing i historie poplatku ted pouzivaji jednotny UX pattern.
- UI: odstranene rozdilne nativni date/month/number pickery; sjednocene ovladani `Prev/Next/Dnes` a vyber z kalendare.
- Testy: doplnene test setup mocky pro `react-day-picker`, aby test suite zustal stabilni.

## 0.1.67
- Frontend: odstraneny prepinac auto-refresh z hlavicky; automaticke obnovovani je napevno zapnute.
- Detail rezim: horni graf cen je navazan na vybrany den (`selectedDate`), takze je mozne pohodlne prochazet historicka data.
- API validace: opravena period-aware validace `energy-balance` anchoru (week/month/year), aby Mesic/Rok nepadaly na VALIDATION_ERROR.
- Chyby v UI: zlepsene formatovani API detailu, aby se nezobrazovalo `[object Object]`.
- UX detailu: doplneny vysvetlujici texty/anotace pro prechody nakupu a exportu.
- Testy: pridane regresni testy pro month/year anchor a formatovani validation detailu.

## 0.1.66
- Backend: pokracovani refaktoru monolitu (`app_service.py`) do samostatnych service modulu (`prices`, `costs`, `export`, `billing`, `battery`, `insights`, `schedule`).
- API: zavedene konzistentni Pydantic query modely (`date`, `month`, `range`) a centralni request context/dependencies vrstva.
- Cache: sjednocena strategie TTL + validace hranic (dnesek vs historicka data vs budouci datum) pres `should_use_daily_cache`.
- Performance: optimalizovane datove pruchody v `/costs` a `/export` (mene opakovaneho parsovani datetime/mapovani v jednom requestu).
- Stabilita: izolace runtime stavu prefetch/OTE backoff mimo globalni promene + doplnene testy (validation, cache fallback, cache strategy, performance guardrails).
- Parsing: opravena robustnost parsovani zapornych cen v historickem HTML (vcetne unicode variant minus znaku).

## 0.1.65
- UI: pridana mobilni gesta (swipe pro zmenu dne/mesice, pull-to-refresh, long-press pin hodiny v cenovem grafu).
- Frontend: refaktor dashboard dat do mensich hooku (`usePrimaryDashboardData`, `useInsightsData`, `usePlannerData`) a pridany `ErrorBoundary` fallback.
- Backend/Docker: novy `/health` endpoint, Docker `HEALTHCHECK` a `npm ci` ve frontend builder stage.
- Kvalita: aktualizovana browser data (`caniuse-lite`, `baseline-browser-mapping`) a pridane testy pro gesta (swipe/pull/long-press).
- Build tooling: odstranen Node deprecation warning `fs.F_OK` pomoci postinstall patchu `react-dev-utils`.

## 0.1.64
- Dokumentace add-onu aktualizovana podle aktualnich funkci (vice zdroju cen, baterie, bilance, heatmapa).
- Nastaveny single source of truth pro metadata repo dokumentaci.
- Release workflow nove synchronizuje i root `README.md` do metadata repa.

## 0.1.63
- Backend: odstraneni deprecation warningu `datetime.utcnow()` (prechod na timezone-aware UTC timestamp v cache metadata).
- Interni cleanup: sjednocene generovani UTC `fetched_at` hodnot do helperu.

## 0.1.62
- Log noise reduction: fallback hlasky v Influx service zmeneny z INFO na DEBUG, aby nezahlcovaly bezne logy.
- Release tooling: oprava kontroly existujiciho tagu ve `tools/release.ps1` (bez padu na starsim PowerShellu).

## 0.1.61
- Refaktor backendu: rozdeleni monolitu do modulu (`app_service`, `pricing`, `influx`, `billing`, `battery`, `cache`, routery, services).
- Refaktor frontendu: `App.js` rozdelen do hooku + API vrstvy; sjednocene volani API a odstranena repetitivni axios logika.
- Bezpecnost a validace: heslo v configu nahrazeno placeholderem, `/api/config` pres Pydantic modely a strict validaci.
- Spolehlivost: scheduler ma single-run guard + process lock, sjednoceny error response format s `error.code` a request ID.
- CI/CD a release flow: pridane GitHub Actions workflow (`ci`, `release`) + automatizace release skriptem.
- Testy: vyrazne rozsiren backend i frontend test suite.

## 0.1.60
- Baterie (KPI pas): pridano ETA do detailu baterie (cas do plna / do rezervy), pokud je projekce k dispozici.
- UI "Vyroba vs spotreba": upravene barvy serii (Export=modra, Import=cervena, PV=zluta, Spotreba domu=cervena tmava).
- UI "Vyroba vs spotreba": sloupcovy graf ma stabilni citelnou sirku (min-width + horizontalni scroll) a sirsi sloupce, aby nebyly tenke pri ruznych sirkach panelu.
- Ceny (historie Spot): parser HTML nově zachovava zaporne hodnoty a robustneji parsuje cisla s locale formatovanim.

## 0.1.59
- UI: graf "Vyroba vs spotreba" ma prehlednejsi tooltip (fixni poradi polozek podle serii + barevne odliseni) a prepinani mezi linkami/sloupci.

## 0.1.58
- Baterie/Forecast/Energy modules: opraveno nacitani z InfluxDB pri rozdilnych measurementech podle jednotek (`kWh`, `W`, `%`, `state`), aby se spravne nacitaly power/SoC/peak-time entity.

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
