# Elektroapp — Plán vývoje, optimalizace a vylepšení

Kompletní analýza backendu i frontendu. Pokrývá kritické refaktory, nové funkce, UX vylepšení a optimalizace výkonu.

---

## Priorita 1: Kritické refaktory (technický dluh)

### 1.1 Rozpad monolitu `app_service.py` (2 102 řádků)

Soubor `app_service.py` je stále **gigantický přesahující 2 100 řádků**. Přestože byl částečně refaktorován do servisních tříd (`CostsService`, `BillingService` atd.), tyto služby jsou pouze **tenké wrappery volající zpět do app_service.py**. Skutečná logika (cache, price fetching, projekce baterie, slot profily, OTE/Spot parsery) zůstává celá v jednom souboru.

**Navrhovaný rozpad:**

| Nový modul | Co přesunout | ~řádků |
|---|---|---|
| `services/price_fetcher.py` | `get_spot_prices`, `fetch_ote_prices_xml`, `parse_ote_prices_xml`, `get_eur_czk_rate_for_date`, `get_ote_entries_for_dates`, `build_entries_from_*`, `get_prices_for_date`, `build_price_map_for_date` | ~400 |
| `services/cache_manager.py` | Všechny `load_*_cache`, `save_*_cache`, `build_*_cache_key`, `cache_status*`, `clear_prices_cache_for_date` | ~250 |
| `services/consumption_service.py` | `get_consumption_points`, `get_export_points` (+ společná logika) | ~250 |
| `services/battery_projection.py` | `build_hybrid_battery_projection`, `build_battery_projection`, `build_battery_history_points`, helper funkce | ~200 |
| `services/energy_balance_service.py` | `build_energy_balance_range`, `build_energy_balance_buckets`, `aggregate_*` funkce | ~120 |
| `services/scheduler.py` | `start_prefetch_scheduler`, `schedule_prefetch_loop`, `acquire/release_prefetch_process_lock` | ~100 |
| `config_loader.py` | `load_config`, `merge_config`, celá fee history logika | ~120 |

> [!IMPORTANT]
> Po tomto refaktoru by `app_service.py` obsahoval jen ~200 řádků koordinační logiky a inicializace služeb. Tento krok je **předpokladem** pro většinu dalších vylepšení.

---

### 1.2 Zmenšení `App.js` (812 řádků)

`App.js` je stále velký — 812 řádků JSX a logiky. KPI compute, price data transforms, planner logika se tam mísí s renderem.

**Navrhovaný rozpad:**

| Nová komponenta/hook | Co přesunout |
|---|---|
| `hooks/usePriceChartData.js` | `todayData`, `tomorrowData`, `selectedDatePriceData`, `dphMultiplier` — celý blok řádků 332–380 |
| `hooks/useKpiItems.js` | `kpiItems` useMemo — řádky 382–469 |
| `components/KpiStrip.js` | Render KPI dlaždic (řádky 544–552) |
| `components/OverviewPage.js` | Celý overview branch (řádky 554–694) |
| `components/DetailPage.js` | Celý detail branch (řádky 696–789) |
| `components/AppHeader.js` | Header + toggle + theme (řádky 486–542) |

---

### 1.3 Eliminace duplicitního kódu v cache systému

Funkce `load_consumption_cache`, `save_consumption_cache`, `load_export_cache`, `save_export_cache` jsou **copy-paste identické** s odlišným prefixem. Totéž platí pro `build_consumption_cache_key` vs `build_export_cache_key`.

**Řešení:** Generická třída `SeriesCache(prefix, cache_dir, ttl)` s metodami `load()`, `save()`, `build_key()`.

---

## Priorita 2: Nové funkce

### 2.1 Notifikace a alerty za cenové prahy

**Backend:**
- Nový endpoint `GET /api/alerts` — vrací aktuální a budoucí hodinové sloty, kde cena překročí nastavený práh (vysoká/nízká).
- Konfigurace v `config.yaml`: `alerts.low_price_threshold: 0.5` a `alerts.high_price_threshold: 5.0` (Kč/kWh).

**Frontend:**
- Nový KPI dlaždice: "Další levná hodina" — zobrazuje nejbližší slot pod prahem.
- Vizuální badge v grafu u slotů překračujících práh.

---

### 2.2 Srovnání s předchozím dnem/týdnem

**Backend:**
- Nový endpoint `GET /api/costs/compare?date=YYYY-MM-DD&compare_with=previous_day|previous_week`.
- Vrací `delta_kwh`, `delta_cost`, `delta_percent` pro snadné zobrazení.

**Frontend:**
- KPI dlaždice s delta šipkami (↑ červená / ↓ zelená).
- Tooltip v grafech: "Včera ve stejnou dobu: X Kč/kWh".

---

### 2.3 Export dat (CSV/PDF)

**Backend:**
- Nový endpoint `GET /api/export-csv?month=YYYY-MM` generující CSV z měsíčního souhrnu.
- Volitelný PDF endpoint (pomocí `reportlab` nebo `weasyprint`).

**Frontend:**
- Tlačítko "Exportovat do CSV" v MonthlySummaryCard a BillingCard.
- Tlačítko "Stáhnout PDF" v odhadu vyúčtování.

---

### 2.4 Solární předpověď jako samostatný dashboard panel

Aktuálně se Forecast.Solar data používají pouze v projekci baterie. Mohla by mít vlastní sekci:

- Graf očekávané vs reálné výroby (historický callback po dni).
- KPI: "Zbývající produkce dnes", "Předpověď na zítra".
- Integration accuracy score: jak přesný byl historicky forecast vs realita.

---

### 2.5 Chytré doporučení pro spotřebu

Rozšíření plánovače spotřebičů o chytrou logiku:
- "Nejlevnějších X hodin dnes/zítra" — automatická identifikace.
- Push notifikace (webhook) do HA automation: "Zapněte pračku nyní, cena klesla pod práh".
- Vizualizace oken v cenovém grafu jako barevné zóny.

---

## Priorita 3: UI/UX vylepšení frontendu

### 3.1 Centrální loading/error stav

Aktuálně je loading/error rozptýlený po mnoha komponentách s duplicitní logikou. 

**Řešení:** Generická komponenta `<DataCard loading error emptyMessage>` jako wrapper.

---

### 3.2 Animované přechody mezi stránkami

Přepínání mezi Overview ↔ Detail je tvrdý cut. Přidat `framer-motion` nebo CSS transition group pro plynulý přechod.

---

### 3.3 Dark mode vylepšení

- Aktuální dark mode má hardcoded barvy. Přidat **auto-detekci** `prefers-color-scheme` jako výchozí.
- Přidat třetí volbu "Auto" do toggle.

---

### 3.4 Tabulky — vylepšení zobrazení

- **Řazení sloupců** v MonthlySummaryCard (klik na záhlaví → sort ↑↓).
- **Zvýraznění víkendů** v souhrnu za měsíc (lehce odlišné pozadí řádků).
- **Sticky header** pro tabulky na mobilech (záhlaví se přilepí při scrollu).

---

### 3.5 Lepší mobilní navigace

- Fixovaný spodní panel (bottom nav) s ikonami: Dashboard / Costs / Battery / Settings.
- Přepínání stránek swipem mezi hlavními sekcemi.

---

### 3.6 Přehled vyrobené a spotřebované energie v overview

V overview mode chybí graf Energy Balance. Přidat zjednodušený mini-graf výroby vs spotřeby (donut/pie chart) pod KPI strip.

---

## Priorita 4: Optimalizace výkonu

### 4.1 Backend — paralelizace API volání

`get_prices_for_date` + `get_consumption_points` + `get_export_points` se volají sekvenčně. Pro "dnes" by se daly spustit **paralelně** pomocí `asyncio.gather()` nebo `concurrent.futures.ThreadPoolExecutor`.

**Odhad zrychlení:** 2–3× pro daily summary a billing month (30 sekvenčních volání → paralelizovaných).

---

### 4.2 Frontend — virtualizace dlouhých tabulek

MonthlySummaryCard vykresluje 28–31 řádků najednou, ale BillingCard (roční pohled) může mít 12+ měsíců × desítky řádků. Pro budoucí škálovatelnost zvážit `react-window` nebo native `content-visibility: auto`.

---

### 4.3 Backend — batch endpoint pro dashboard data

Frontend dnes stahuje ~8 API volání při načtení dashboardu. Nový batch endpoint `POST /api/dashboard-snapshot` by vrátil vše v jednom HTTP požadavku:

```json
{
  "prices": {...},
  "costs": {...},
  "export": {...},
  "battery": {...},
  "kpi": {...}
}
```

**Výhody:** Snížení latence (1 roundtrip místo 8), atomický stav, jednodušší error handling na frontendu.

---

### 4.4 Frontend — memoizace Chart.js konfigurací

Chart.js konfigurace se přebudovávají při každém renderování. Přidat deep equality check v ReactChartWrapper, aby se chart destruoval a znovu vytvářel jen skutečně při změně dat.

---

### 4.5 InfluxDB — connection pooling

`InfluxService` vytváří nový HTTP request pro každý query. Pro burst operace (billing month = 30× query) by pomohl connection pool / HTTP session reuse přes `requests.Session()`.

---

## Priorita 5: Kvalita kódu a testování

### 5.1 Pokrytí testy

| Oblast | Aktuální stav | Cíl |
|---|---|---|
| Backend services | Základní testy | Pokrýt edge cases: záporné ceny, chybějící data, timezone přechody |
| Frontend components | Minimální | Snapshot testy pro každou Card komponentu |
| Integration testy | Žádné | E2E test: load → click → verify data zobrazení |
| Price parsing | Dobré | Přidat fuzz testy pro HTML parser (OTE + Spot) |

---

### 5.2 TypeScript migrace (frontend)

`App.js` je čistý JavaScript bez typové kontroly. Postupná migrace:
1. Přidat `tsconfig.json` s `allowJs: true`.
2. Začít s `utils/formatters.ts` a `api/elektroappApi.ts`.
3. Postupně převádět hooks a komponenty.

---

### 5.3 Linting a formátování

- Backend: přidat `ruff` s pravidly pro konzistentní formátování.
- Frontend: přidat `eslint-plugin-react-hooks` rules pro exausativní deps.

---

## Priorita 6: Infrastruktura a provoz

### 6.1 Monitoring a metriky

- Přidat Prometheus endpoint `/metrics` s:
  - Počet cache hitů/missů
  - Latence API volání (percentily)
  - Stav OTE backoff
  - Velikost cache na disku

---

### 6.2 Automatická čistka cache

Aktuálně cache roste neomezeně. Přidat:
- Konfigurovatelný limit: `cache.max_age_days: 90`.
- Automatická čistka v prefetch scheduleru.

---

### 6.3 Graceful degradace

Když InfluxDB není dostupná, aplikace by měla:
- Zobrazit cenový graf (ten DB nepotřebuje).
- Jasně označit, které panely nemají data.
- Nabídnout tlačítko "Zkusit znovu" místo generické chyby.

---

## Doporučené pořadí implementace

| Fáze | Úkoly | Priorita |
|---|---|---|
| **Fáze 1** | 1.1 Rozpad `app_service.py`, 1.2 Rozpad `App.js`, 1.3 Cache refaktor | Kritická |
| **Fáze 2** | 3.1 DataCard wrapper, 3.3 Dark mode auto, 3.4 Tabulky sort + sticky | Vysoká |
| **Fáze 3** | 2.1 Cenové alerty, 2.2 Srovnání dní, 4.1 Paralelizace backendu | Střední |
| **Fáze 4** | 2.3 CSV/PDF export, 2.5 Chytré doporučení, 4.3 Batch endpoint | Střední |
| **Fáze 5** | 5.1 Testy, 5.2 TypeScript migrace, 6.1 Monitoring | Dlouhodobá |
| **Fáze 6** | 2.4 Solární dashboard, 3.2 Animace, 3.5 Bottom nav | Nice-to-have |

---

## Otevřené otázky

> [!IMPORTANT]
> 1. **Které funkce tě nejvíc zajímají?** Plán je rozsáhlý — chceš začít refaktorem (stabilita) nebo novými funkcemi (viditelná hodnota)?
> 2. **TypeScript migrace:** Stojí ti za to? Je to investice do budoucna, ale krátký pain.
> 3. **CSV/PDF export:** Potřebuješ to pro účetnictví / daňové účely, nebo je to spíš nice-to-have?
> 4. **Bottom navigation:** Je mobilní UX priorita, nebo aplikaci používáš hlavně na desktopu přes HA panel?
> 5. **Monitoring (Prometheus):** Máš v HA infrastruktuře Grafana/Prometheus stack, nebo by to bylo zbytečné?
