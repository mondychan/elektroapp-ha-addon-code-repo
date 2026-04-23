<!-- AUTO-SYNCED FROM mondychan/elektroapp-ha-addon-code-repo:ha-addon/README.md -->
# Elektroapp Home Assistant Add-on Repository

Toto je metadata repo pro Home Assistant Add-on Store.

## Kde najdes dokumentaci

- Add-on dokumentace (instalace, konfigurace, pouziti):
  - `elektroapp/README.md`
- Zdrojovy kod aplikace:
  - https://github.com/mondychan/elektroapp-ha-addon-code-repo

## Aktualni core zmeny

- Frontend build byl migrovan z CRA na Vite a testy na Vitest.
- Dashboard snapshot nyni nacita prvni obrazovku jednim rozsireny API kontraktem bez duplicitnich volani cen.
- Nova karta Doporuceni kombinuje ceny, baterii, solarni forecast, bilanci a planner do akcnich radku bez automatickeho rizeni Home Assistanta.
- API ma prisnejsi mutacni guard, diagnostiku a bezpecnejsi Influx query builder.

## Poznamka k forecastu

- Pro presnejsi profil jsou podporovany i Forecast.Solar entity `power_production_next_hour`, `power_production_next_12hours` a `power_production_next_24hours`.

## Poznamka

Obsah tohoto repozitare je synchronizovan automaticky z code repa behem release
workflow.
