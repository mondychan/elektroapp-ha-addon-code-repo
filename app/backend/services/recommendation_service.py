from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


class RecommendationService:
    def build(
        self,
        *,
        date: str,
        prices: list[dict[str, Any]],
        schedule: dict[str, Any] | None,
        battery: dict[str, Any] | None,
        solar: dict[str, Any] | None,
        costs: dict[str, Any] | None,
        export: dict[str, Any] | None,
    ) -> dict[str, Any]:
        actions: list[dict[str, Any]] = []
        metrics: list[dict[str, Any]] = []
        valid_prices = [p for p in prices if isinstance(p.get("final"), (int, float))]
        valid_prices.sort(key=lambda p: (p.get("final"), p.get("time", "")))

        if valid_prices:
            cheapest = valid_prices[0]
            most_expensive = max(valid_prices, key=lambda p: (p.get("final"), p.get("time", "")))
            avg_price = sum(float(p["final"]) for p in valid_prices) / len(valid_prices)
            metrics.extend(
                [
                    self._metric("avg_price", "Prumerna cena", round(avg_price, 3), "Kc/kWh"),
                    self._metric("min_price", "Nejnizsi cena", round(float(cheapest["final"]), 3), "Kc/kWh"),
                    self._metric("max_price", "Nejvyssi cena", round(float(most_expensive["final"]), 3), "Kc/kWh"),
                ]
            )
            actions.append(
                self._action(
                    "run_load",
                    "Spustit spotrebic",
                    f"Nejlevnejsi slot zacina {self._hhmm(cheapest.get('time'))}.",
                    cheapest.get("time"),
                    confidence=0.9,
                    impact="low_cost",
                )
            )
            if float(most_expensive["final"]) > avg_price * 1.25:
                actions.append(
                    self._action(
                        "save_battery",
                        "Setrit baterii",
                        f"Drahy slot zacina {self._hhmm(most_expensive.get('time'))}; vyplati se omezit odber ze site.",
                        most_expensive.get("time"),
                        confidence=0.78,
                        impact="avoid_peak",
                    )
                )

        for item in (schedule or {}).get("recommendations", [])[:2]:
            actions.append(
                self._action(
                    "planned_window",
                    "Vyhodne okno",
                    f"Okno {self._hhmm(item.get('start'))}-{self._hhmm(item.get('end'))}, prumer {item.get('avg_price')} Kc/kWh.",
                    item.get("start"),
                    item.get("end"),
                    confidence=0.86,
                    impact="planner",
                )
            )

        battery_status = (battery or {}).get("status") or {}
        soc = battery_status.get("soc_percent")
        if isinstance(soc, (int, float)):
            metrics.append(self._metric("battery_soc", "Baterie", round(float(soc), 1), "%"))
            if soc < 35 and valid_prices:
                actions.append(
                    self._action(
                        "charge_battery",
                        "Nabit baterii",
                        "Baterie je nizko; preferuj nabijeni v nejlevnejsim okne.",
                        valid_prices[0].get("time"),
                        confidence=0.72,
                        impact="battery_reserve",
                    )
                )

        solar_comparison = (solar or {}).get("comparison") or {}
        solar_tomorrow = solar_comparison.get("adjusted_projection_tomorrow_kwh")
        if isinstance(solar_tomorrow, (int, float)):
            metrics.append(self._metric("solar_tomorrow", "FV zitra", round(float(solar_tomorrow), 2), "kWh"))
            if solar_tomorrow > 8:
                actions.append(
                    self._action(
                        "defer_load",
                        "Odlozit spotrebu",
                        "Zitra se ceka vyssi FV vyroba; cast spotreby muze byt levnejsi odlozit.",
                        confidence=0.68,
                        impact="solar_use",
                    )
                )

        cost_total = ((costs or {}).get("summary") or {}).get("cost_total")
        export_total = ((export or {}).get("summary") or {}).get("sell_total")
        if isinstance(cost_total, (int, float)) or isinstance(export_total, (int, float)):
            net = float(cost_total or 0) - float(export_total or 0)
            metrics.append(self._metric("net_today", "Netto dnes", round(net, 2), "Kc"))
            if net < 0:
                actions.append(
                    self._action(
                        "export_ok",
                        "Exportovat",
                        "Dnesni bilance je zatim v plusu; export dava smysl pri dostatku baterie.",
                        confidence=0.62,
                        impact="export_revenue",
                    )
                )

        if not actions:
            actions.append(
                self._action(
                    "no_action",
                    "Bez akce",
                    "Neni k dispozici dost dat nebo aktualni stav nevyzaduje zasah.",
                    confidence=0.5,
                    impact="neutral",
                )
            )

        confidence = round(sum(float(a["confidence"]) for a in actions) / len(actions), 2)
        return {
            "date": date,
            "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "confidence": confidence,
            "metrics": metrics,
            "actions": actions[:6],
            "inputs": {
                "prices": bool(prices),
                "schedule": bool((schedule or {}).get("recommendations")),
                "battery": bool(battery_status),
                "solar": bool(solar and solar.get("enabled")),
                "costs": bool(costs),
                "export": bool(export),
            },
        }

    def _metric(self, key: str, label: str, value: Any, unit: str | None = None) -> dict[str, Any]:
        return {"key": key, "label": label, "value": value, "unit": unit}

    def _action(
        self,
        action_type: str,
        title: str,
        reason: str,
        start: str | None = None,
        end: str | None = None,
        *,
        confidence: float,
        impact: str,
    ) -> dict[str, Any]:
        return {
            "type": action_type,
            "title": title,
            "reason": reason,
            "start": start,
            "end": end,
            "confidence": round(confidence, 2),
            "impact": impact,
        }

    def _hhmm(self, value: Any) -> str:
        if not value:
            return "-"
        raw = str(value)
        if " " in raw:
            return raw.split(" ", 1)[1][:5]
        if "T" in raw:
            return raw.split("T", 1)[1][:5]
        return raw[:5]
