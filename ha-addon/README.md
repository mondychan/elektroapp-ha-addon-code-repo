<!-- AUTO-SYNCED FROM mondychan/elektroapp-ha-addon-code-repo:ha-addon/README.md -->
# Elektroapp Home Assistant Add-on Repository

Toto repo slouzi pro Home Assistant Add-on Store. Vlastni aplikace je add-on, ktery se po instalaci otevira jako panel v Home Assistantu pres Ingress.

## Co doplnek dela

Elektroapp je prehled domaci energetiky. Spojuje spotove ceny elektriny, vlastni tarif a poplatky, data z Home Assistant senzoru, historii z InfluxDB, baterii, fotovoltaiku a volitelne i oficialni data z Portalu namerenych dat CEZ Distribuce.

Doplnek pomaha odpovedet hlavne na tyhle otazky:

- Kolik stoji elektrina dnes a zitra po zapocitani DPH, distribuce, OZE a dalsich poplatku?
- Kolik stoji skutecna spotreba domu podle dat ze stridace nebo jinych HA senzoru?
- Kolik dava export do site po zapocitani koeficientu prodejni ceny?
- Jak vypada import, export, vlastni spotreba a vyroba v dennich, mesicnich a rocnich pohledech?
- Jak sedi lokalni mereni proti oficialnim datum z elektromeru v PND?
- Kdy dava smysl spustit spotrebic, setrit baterii, nabijet nebo exportovat?

## Co je potreba nastavit

- Zdroj cen: `spotovaelektrina.cz` nebo `ote-cr.cz`.
- Tarif a poplatky: DPH, distribuce VT/NT, stale platby, OZE, dan a dalsi slozky ceny.
- InfluxDB: historie importu a exportu, typicky ze stridace nebo energetickych senzoru.
- Home Assistant entity: baterie, FV vykon, spotreba domu, import/export ze site a pripadne dalsi vlastni senzory.
- PND: volitelne prihlaseni k Portalu namerenych dat CEZ Distribuce pro import oficialnich dat z elektromeru.

## Dokumentace a kod

- Add-on dokumentace:
  - `elektroapp/README.md`
- Zdrojovy kod aplikace:
  - https://github.com/mondychan/elektroapp-ha-addon-code-repo

## Poznamka

Obsah tohoto repozitare je synchronizovan automaticky z code repa behem release workflow.

Add-on obsahuje samostatné obrazovky `Distribuční portál` pro profil odběrných a výrobních EAN a `Vyúčtování` pro virtuální fakturu, dodavatelské exporty a audit PDF/XLSX dokumentů. Přihlašovací údaje DIP se konfigurují pouze přes Home Assistant add-on konfiguraci nebo YAML.
