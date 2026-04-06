# Elektroapp Home Assistant Add-on

Elektroapp je pokročilý Home Assistant add-on pro komplexní sledování energetiky, výpočet nákladů podle spotových cen a integraci s distributory. UI je dostupné přes Home Assistant Ingress (panel v postranním menu).

## Hlavní funkce
- **Spotové ceny**: Načítání cen (dnes/zítra) z OTE nebo `spotovaelektrina.cz` s automatickým přepočtem na konečnou cenu (DPH, distribuce, OZE).
- **Náklady a tržby**: Výpočet v reálném čase podle dat z InfluxDB (např. ze Solaxu).
- **PND Integrace**: Automatický import dat z Portálu naměřených dat (ČEZ Distribuce).
- **Srovnání dat**: Unikátní možnost porovnání "oficiálních" dat z elektroměru (PND) s lokálními senzory střídače pro odhalení nepřesností.
- **Solární předpověď**: Hybridní odhad výroby (Forecast.Solar) kalibrovaný podle reálného chování vašeho systému, včetně historického backfillu z InfluxDB pro rychlejší rozjezd kalibrace po nasazení.
- **Baterie**: Detailní monitoring SoC, výkonu a inteligentní projekce času nabití/vybití.
- **Interaktivní Dashboard**: Moderní, modulární UI s toggle-sekcemi (Statistiky, Detailní grafy) a responsivní heatmapou cen.

## Struktura projektu
- `app/backend` - FastAPI backend (API + výpočty + InfluxDB dotazy)
  - `services/pnd_service.py` - Integrace s Portálem naměřených dat
  - `services/insights_service.py` - Agregace pro bilanci a heatmapy
  - `services/solar_service.py` - Logika hybridní solární předpovědi
  - `pricing.py` - Cenové a tarifní výpočty
- `app/frontend` - Moderní React frontend (Highcharts, Vite)
- `ha-addon/elektroapp` - Home Assistant manifest a metadata doplňku

## Instalace do Home Assistant
1. V HA: Settings > Add-ons > Add-on Store > ... > Repositories.
2. Přidat URL: `https://github.com/mondychan/elektroapp-ha-addon`
3. V seznamu vybrat "Elektroapp", kliknout Install a vyplnit Konfiguraci.

## Konfigurace (PND)
Pro automatický import z PND vyplňte v nastavení sekci `pnd`:
```yaml
pnd:
  enabled: true
  username: "vás_email@domena.cz"
  password: "vaše_heslo"
  meter_id: "3000012345"
  nightly_sync_enabled: true
```

## API
Backend poskytuje bohaté rozhraní:
- `GET /api/prices` - Aktuální a budoucí ceny
- `GET /api/pnd/data?from=...&to=...` - Data z distribuce + lokální srovnání
- `GET /api/energy-balance` - Týdenní/měsíční energetická bilance
- `GET /api/solar-forecast` - Kalibrovaná solární předpověď
- `GET /api/daily-summary?month=YYYY-MM` - Měsíční billing souhrn
