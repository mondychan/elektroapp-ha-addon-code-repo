<!-- AUTO-SYNCED FROM mondychan/elektroapp-ha-addon-code-repo:ha-addon/elektroapp/README.md -->
# Elektroapp Home Assistant Add-on

Elektroapp je pokročilý Home Assistant add-on pro sledování spotových cen elektřiny, automatizovaný import dat z distribuce (PND) a komplexní energetický management.

## Hlavní funkce

- **Spotové ceny (OTE / spotovaelektrina.cz)**: Přepočet na finální cenu včetně všech poplatků, DPH a distribučních složek (VT/NT).
- **Integrace PND (ČEZ Distribuce)**: Automatický import oficiálních dat z elektroměru. Už žádné ruční opisování.
- **Srovnání dat**: Porovnání dat z PND s lokálními senzory střídače. Zjistěte, jak přesně vaše senzory měří ve srovnání s fakturačním měřidlem.
- **Hybridní Solární Předpověď**: Kombinuje Forecast.Solar s reálnou historickou křivkou vašeho systému pro nejpřesnější odhad výroby.
- **Energetická Bilance**: Přehledné grafy a tabulky nákupu, prodeje a vlastní spotřeby (týden/měsíc/rok).
- **Bateriace**: Pokročilý monitoring SoC, predikce času nabití/vybití a slotový profil.
- **Doporučení**: Read-only karta s akčními doporučeními pro spotřebu, baterii, FV výrobu a export.
- **Billing**: Odhad aktuálního měsíčního a ročního vyúčtování včetně fixních poplatků.

## Instalace

1. V Home Assistant: `Settings > Add-ons > Add-on Store > ... > Repositories`.
2. Přidej URL: `https://github.com/mondychan/elektroapp-ha-addon`
3. V seznamu vyber `Elektroapp` a klikni `Install`.
4. Vyplň konfiguraci a spusť add-on.

## Konfigurace

Nastavení se provádí přímo v panelu "Configuration" doplňku v HA.

### PND (Portál naměřených dat)
Aktivujte import dat z distribuce:
- `pnd.enabled`: Zapnout integraci
- `pnd.username` / `pnd.password`: Vaše přihlašovací údaje do portálu PND
- `pnd.meter_id`: Číslo elektroměru (EAN bez prefixu nebo Meter ID)

### Ostatní sekce
- `poplatky`: Nastavení distribučních cen, daní a OZE.
- `influxdb`: Připojení k databázi s lokálními daty (Solax, Victron apod.).
- `battery` / `energy`: Mapování HA entit pro bilanci a dashboard.

## Použití

- Dashboard je dostupný v postranním panelu HA přes **Ingress**.
- **Přehled**: Rychlý pohled na ceny, bilanci a stav baterie.
- **Doporučení**: Akční řádky jako `Spustit spotřebič`, `Šetřit baterii`, `Nabít baterii`, `Exportovat` nebo `Bez akce`.
- **Statistiky**: Modulární sekce pro podrobné srovnání výkonu.
- **PND Portál**: Správa importovaných dat a srovnání s lokálními senzory.

## Poznámky

- Historie cen a PND dat je ukládána lokálně pro maximální stabilitu i při výpadku internetu.
- Prodejní cena (export) podporuje koeficienty snížení ceny denního trhu.
