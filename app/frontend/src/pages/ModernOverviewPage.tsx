import React from "react";
import PriceChartCard from "../components/PriceChartCard";
import MonthlySummaryCard from "../components/MonthlySummaryCard";
import EnergyBalanceCard from "../components/EnergyBalanceCard";
import KpiCard from "../components/modern/KpiCard";
import StatusStrip from "../components/modern/StatusStrip";
import EnergyFlowCard from "../components/modern/EnergyFlowCard";
import DailySummaryCard from "../components/modern/DailySummaryCard";
import SectionCard from "../components/modern/SectionCard";
import ModernSolarForecastCard from "../components/modern/ModernSolarForecastCard";
import ModernBatteryProjectionCard from "../components/modern/ModernBatteryProjectionCard";
import { PageMode } from "../components/modern/AppShell";
import { formatCurrency, formatDate, formatSlotRange } from "../utils/formatters";
import {
  getMaxEnergyBalanceAnchor,
  normalizeEnergyBalanceAnchor,
  shiftEnergyBalanceAnchor,
} from "../hooks/useDashboardData";

const formatKwh = (value?: number | null) => (value == null || Number.isNaN(Number(value)) ? null : `${Number(value).toFixed(2)} kWh`);

const formatPowerW = (value?: number | null) => {
  if (value == null || Number.isNaN(Number(value))) return "-";
  const numeric = Number(value);
  if (Math.abs(numeric) >= 1000) return `${(numeric / 1000).toFixed(2)} kW`;
  return `${Math.round(numeric)} W`;
};

const formatPrice = (value?: number | null) => (value == null || Number.isNaN(Number(value)) ? "-" : `${Number(value).toFixed(2)} Kč/kWh`);
const formatPriceValue = (value?: number | null) => (value == null || Number.isNaN(Number(value)) ? "-" : `${Number(value).toFixed(2)} Kč`);

const buildStatusLabel = (alerts: any) => {
  if (alerts?.is_cheap_now) return "LEVNÉ OKNO";
  if (alerts?.is_expensive_now) return "DRAHÁ ENERGIE";
  return "BĚŽNÝ PROVOZ";
};

const normalizeTime = (value: unknown) => {
  if (!value) return null;
  const text = String(value);
  return text.includes(" ") ? text.split(" ").pop() || text : text;
};

const ModernOverviewPage = (props: any) => {
  const {
    today,
    tomorrow,
    todayData,
    tomorrowData,
    config,
    pinnedSlot,
    setPinnedSlot,
    effectiveHighlightSlot,
    costsSummary,
    exportSummary,
    batteryData,
    batteryLoading,
    batteryError,
    refreshBattery,
    solarForecast,
    solarForecastLoading,
    monthlySummary,
    monthlyTotals,
    monthlyError,
    monthlyLoading,
    selectedMonth,
    setSelectedMonth,
    maxMonth,
    energyBalancePeriod,
    energyBalanceAnchor,
    setEnergyBalanceAnchor,
    setEnergyBalancePeriod,
    energyBalanceData,
    energyBalanceLoading,
    energyBalanceError,
    alerts,
    recommendations,
    setPageMode,
  } = props;

  const currentEnergyBalanceAnchor = normalizeEnergyBalanceAnchor(energyBalancePeriod, energyBalanceAnchor);
  const maxEnergyBalanceAnchor = getMaxEnergyBalanceAnchor(energyBalancePeriod);
  const currentPriceNumber =
    alerts?.current_price != null
      ? Number(alerts.current_price)
      : Number.isInteger(effectiveHighlightSlot) && todayData?.[effectiveHighlightSlot]
        ? todayData[effectiveHighlightSlot].final
        : null;

  const nextCheapWindow = alerts?.next_cheap_start
    ? `Další levné okno začne v ${normalizeTime(alerts.next_cheap_start)}${
        alerts.next_cheap_price != null ? ` (${Number(alerts.next_cheap_price).toFixed(2)} Kč/kWh)` : ""
      }`
    : null;

  const finals = todayData.map((item: any) => item.final);
  const minPrice = finals.length ? Math.min(...finals) : null;
  const maxPrice = finals.length ? Math.max(...finals) : null;
  const minItem = minPrice != null ? todayData.find((item: any) => item.final === minPrice) : null;
  const maxItem = maxPrice != null ? todayData.find((item: any) => item.final === maxPrice) : null;
  const netTotal =
    costsSummary?.cost_total != null || exportSummary?.sell_total != null
      ? (costsSummary?.cost_total || 0) - (exportSummary?.sell_total || 0)
      : null;
  const pvPower = batteryData?.current_energy?.pv_power_total_w ?? solarForecast?.actual?.power_now_w ?? solarForecast?.status?.power_now_w;

  const kpis = [
    { label: "Aktuální cena", value: formatPriceValue(currentPriceNumber), unit: "/kWh", detail: todayData?.[effectiveHighlightSlot]?.time || null, tone: "price" },
    { label: "Dnešní minimum", value: formatPriceValue(minPrice), detail: minItem ? formatSlotRange(minItem.slot) : null, tone: "green" },
    { label: "Dnešní maximum", value: formatPriceValue(maxPrice), detail: maxItem ? formatSlotRange(maxItem.slot) : null, tone: "red" },
    { label: "Nákup dnes", value: formatCurrency(costsSummary?.cost_total), detail: formatKwh(costsSummary?.kwh_total), tone: "red" },
    { label: "Export dnes", value: formatCurrency(exportSummary?.sell_total), detail: formatKwh(exportSummary?.export_kwh_total), tone: "green" },
    { label: "Netto dnes", value: formatCurrency(netTotal), detail: null, tone: "purple" },
    {
      label: "Baterie",
      value: batteryData?.status?.soc_percent != null ? `${Number(batteryData.status.soc_percent).toFixed(0)} %` : "-",
      detail: batteryData?.status?.stored_kwh != null ? `${Number(batteryData.status.stored_kwh).toFixed(2)} kWh` : null,
      tone: "amber",
    },
    { label: "Výkon FV", value: formatPowerW(pvPower), detail: "aktuálně", tone: "green" },
  ];

  return (
    <div className="modern-dashboard">
      <section className="modern-kpi-grid" aria-label="Dnešní KPI">
        {kpis.map((item) => (
          <KpiCard key={item.label} {...item} />
        ))}
      </section>

      <StatusStrip
        statusLabel={buildStatusLabel(alerts)}
        currentPrice={formatPrice(currentPriceNumber)}
        nextCheapWindow={nextCheapWindow}
        recommendation={alerts?.recommendation || recommendations?.actions?.[0]?.title}
        onOpenRecommendations={() => setPageMode("recommendations" as PageMode)}
      />

      <div className="modern-dashboard-grid modern-dashboard-grid--top">
        <SectionCard title="Energetický tok" hideHeader>
          <EnergyFlowCard batteryData={batteryData} solarForecast={solarForecast} />
        </SectionCard>

        <SectionCard
          title="Cena elektřiny dnes"
          eyebrow="Kč/kWh"
          className="modern-section-card--wide"
          actions={
            Number.isInteger(pinnedSlot) ? (
              <button type="button" className="ghost-button" onClick={() => setPinnedSlot(null)}>
                Zrušit pin
              </button>
            ) : null
          }
        >
          <PriceChartCard
            chartData={todayData}
            fallbackMessage="Načítám data..."
            vtPeriods={config?.tarif?.vt_periods}
            highlightSlot={effectiveHighlightSlot}
            pinnedSlot={pinnedSlot}
            onPinSlot={setPinnedSlot}
            thresholds={alerts}
            className="modern-price-chart"
            height={330}
          />
        </SectionCard>

        {tomorrowData?.length > 0 && (
          <SectionCard
            title="Cena elektřiny zítra"
            eyebrow={`Kč/kWh · ${formatDate(tomorrow)}`}
            className="modern-section-card--full"
          >
            <PriceChartCard
              chartData={tomorrowData}
              fallbackMessage="Data pro zítřek zatím nejsou k dispozici."
              vtPeriods={config?.tarif?.vt_periods}
              highlightSlot={-1}
              pinnedSlot={null}
              onPinSlot={() => {}}
              thresholds={alerts}
              className="modern-price-chart"
              height={300}
            />
          </SectionCard>
        )}
      </div>

      <div className="modern-dashboard-grid modern-dashboard-grid--middle">
        <SectionCard title="Solární předpověď">
          <ModernSolarForecastCard solarForecast={solarForecast} loading={solarForecastLoading} />
        </SectionCard>

        <SectionCard title="Baterie a projekce" className="modern-section-card--wide">
          <ModernBatteryProjectionCard
            batteryData={batteryData}
            batteryLoading={batteryLoading}
            batteryError={batteryError}
            onRefresh={refreshBattery}
          />
        </SectionCard>

        <SectionCard title="Denní souhrn">
          <DailySummaryCard
            costsSummary={costsSummary}
            exportSummary={exportSummary}
            batteryData={batteryData}
            solarForecast={solarForecast}
          />
        </SectionCard>
      </div>

      <div className="modern-dashboard-grid modern-dashboard-grid--bottom">
        <SectionCard title="Měsíční přehled" className="modern-section-card--wide" eyebrow={selectedMonth}>
          {monthlyLoading ? (
            <div className="muted-note">Načítám měsíční přehled...</div>
          ) : (
            <MonthlySummaryCard
              selectedMonth={selectedMonth}
              setSelectedMonth={setSelectedMonth}
              maxMonth={maxMonth}
              monthlySummary={monthlySummary || []}
              monthlyTotals={monthlyTotals}
              monthlyError={monthlyError}
            />
          )}
        </SectionCard>

        <SectionCard title="Energetická bilance" className="modern-section-card--wide">
          <EnergyBalanceCard
            period={energyBalancePeriod}
            anchor={currentEnergyBalanceAnchor}
            onPrev={() => setEnergyBalanceAnchor((prev: string) => shiftEnergyBalanceAnchor(energyBalancePeriod, prev, -1))}
            onNext={() => setEnergyBalanceAnchor((prev: string) => shiftEnergyBalanceAnchor(energyBalancePeriod, prev, 1))}
            disableNext={currentEnergyBalanceAnchor === maxEnergyBalanceAnchor}
            onPeriodChange={(value: any) => {
              setEnergyBalancePeriod(value as any);
              setEnergyBalanceAnchor((prev: string) => normalizeEnergyBalanceAnchor(value, prev));
            }}
            data={energyBalanceData}
            loading={energyBalanceLoading}
            error={energyBalanceError}
          />
        </SectionCard>
      </div>
    </div>
  );
};

export default ModernOverviewPage;
