import React, { useEffect, useMemo, useState } from "react";
import PriceChartCard from "./components/PriceChartCard";
import CostChartCard from "./components/CostChartCard";
import ExportChartCard from "./components/ExportChartCard";
import MonthlySummaryCard from "./components/MonthlySummaryCard";
import BillingCard from "./components/BillingCard";
import PlannerCard from "./components/PlannerCard";
import ConfigCard from "./components/ConfigCard";
import BatteryProjectionCard from "./components/BatteryProjectionCard";
import EnergyBalanceCard from "./components/EnergyBalanceCard";
import HistoryHeatmapCard from "./components/HistoryHeatmapCard";
import { formatDate, formatBytes, formatSlotToTime, formatCurrency } from "./utils/formatters";
import { useLocalStorageState } from "./hooks/useLocalStorageState";
import { usePageVisibility } from "./hooks/usePageVisibility";
import { useCurrentSlot } from "./hooks/useCurrentSlot";
import {
  normalizeEnergyBalanceAnchor,
  shiftEnergyBalanceAnchor,
  useDashboardData,
} from "./hooks/useDashboardData";

const formatEtaTime = (iso) => {
  if (!iso) return null;
  const dt = new Date(iso);
  if (Number.isNaN(dt.getTime())) return null;
  return dt.toLocaleTimeString("cs-CZ", { hour: "2-digit", minute: "2-digit" });
};

const formatEtaDuration = (minutes) => {
  if (minutes == null || !Number.isFinite(minutes)) return null;
  if (minutes < 60) return `${minutes} min`;
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  if (!m) return `${h} h`;
  return `${h} h ${m} min`;
};

function App() {
  const [showConfig, setShowConfig] = useState(false);
  const [showMonthlySummary, setShowMonthlySummary] = useState(false);
  const [showPlanner, setShowPlanner] = useState(false);
  const [showBilling, setShowBilling] = useState(false);
  const [showFeesHistory, setShowFeesHistory] = useState(false);
  const [showBatteryPanel, setShowBatteryPanel] = useState(false);
  const [pageMode, setPageMode] = useState("overview");

  const [theme, setTheme] = useLocalStorageState("theme", "light");
  const [plannerDuration, setPlannerDuration] = useLocalStorageState("plannerDuration", "120");

  const [autoRefreshEnabled, setAutoRefreshEnabled] = useState(() => localStorage.getItem("autoRefreshEnabled") !== "false");
  const [plannerValidationError, setPlannerValidationError] = useState(null);

  const [selectedDate, setSelectedDate] = useState(() => {
    const today = new Date();
    const y = today.getFullYear();
    const m = String(today.getMonth() + 1).padStart(2, "0");
    const d = String(today.getDate()).padStart(2, "0");
    return `${y}-${m}-${d}`;
  });
  const [selectedMonth, setSelectedMonth] = useState(() => {
    const today = new Date();
    const y = today.getFullYear();
    const m = String(today.getMonth() + 1).padStart(2, "0");
    return `${y}-${m}`;
  });
  const [billingMode, setBillingMode] = useState("month");
  const [billingMonth, setBillingMonth] = useState(() => {
    const today = new Date();
    const y = today.getFullYear();
    const m = String(today.getMonth() + 1).padStart(2, "0");
    return `${y}-${m}`;
  });
  const [billingYear, setBillingYear] = useState(() => String(new Date().getFullYear()));
  const [energyBalancePeriod, setEnergyBalancePeriod] = useState("week");
  const [energyBalanceAnchor, setEnergyBalanceAnchor] = useState(() => {
    const today = new Date();
    const y = today.getFullYear();
    const m = String(today.getMonth() + 1).padStart(2, "0");
    const d = String(today.getDate()).padStart(2, "0");
    return `${y}-${m}-${d}`;
  });
  const [heatmapMetric, setHeatmapMetric] = useState("buy");
  const [heatmapMonth, setHeatmapMonth] = useState(() => {
    const today = new Date();
    const y = today.getFullYear();
    const m = String(today.getMonth() + 1).padStart(2, "0");
    return `${y}-${m}`;
  });

  const isPageVisible = usePageVisibility();
  const currentSlot = useCurrentSlot();

  useEffect(() => {
    document.body.dataset.theme = theme;
  }, [theme]);

  useEffect(() => {
    localStorage.setItem("autoRefreshEnabled", autoRefreshEnabled ? "true" : "false");
  }, [autoRefreshEnabled]);

  const {
    prices,
    config,
    cacheStatus,
    version,
    costs,
    costsSummary,
    costsError,
    costsFromCache,
    costsCacheFallback,
    exportPoints,
    exportSummary,
    exportError,
    exportFromCache,
    exportCacheFallback,
    monthlySummary,
    monthlyTotals,
    monthlyError,
    billingData,
    billingLoading,
    billingError,
    batteryData,
    batteryLoading,
    batteryError,
    refreshBattery,
    todayCostsKpi,
    todayExportKpi,
    energyBalanceData,
    energyBalanceLoading,
    energyBalanceError,
    heatmapData,
    heatmapLoading,
    heatmapError,
    feesHistory,
    feesHistoryLoading,
    feesHistoryError,
    saveFeesHistory,
    refreshPrices,
    pricesRefreshLoading,
    pricesRefreshMessage,
    pricesRefreshError,
    loadPlanner,
    plannerLoading,
    plannerResults,
    plannerNote,
    plannerError,
  } = useDashboardData({
    selectedDate,
    selectedMonth,
    showConfig,
    showFeesHistory,
    showBilling,
    billingMode,
    billingMonth,
    billingYear,
    pageMode,
    energyBalancePeriod,
    energyBalanceAnchor,
    heatmapMonth,
    heatmapMetric,
    autoRefreshEnabled,
    isPageVisible,
  });

  const activePriceProvider = config?.price_provider === "ote" ? "ote" : "spotovaelektrina";
  const priceProviderLabel = activePriceProvider === "ote" ? "OTE (ote-cr.cz + CNB)" : "spotovaelektrina.cz";
  const priceProviderUrl = activePriceProvider === "ote" ? "https://www.ote-cr.cz/" : "https://spotovaelektrina.cz/";

  const normalizeDuration = (value) => {
    if (value == null || value === "") return null;
    const parsed = Number.parseInt(value, 10);
    if (!Number.isFinite(parsed) || parsed <= 0) return null;
    if (parsed > 360) return "too-long";
    return Math.round(parsed);
  };

  const handleLoadPlanner = async () => {
    const durationValue = normalizeDuration(plannerDuration);
    if (durationValue === "too-long") {
      setPlannerValidationError("Okno je prilis dlouhe. Zadej delku 1-360 minut.");
      return;
    }
    if (!durationValue) {
      setPlannerValidationError("Zadej delku programu 1-360 minut.");
      return;
    }
    setPlannerValidationError(null);
    try {
      await loadPlanner(durationValue);
    } catch {
      // Planner error is exposed by the hook.
    }
  };

  const formatFeeValue = (value) => (value == null ? "-" : value);
  const configRows = useMemo(() => {
    if (!config) return [];
    return [
      { label: "DPH", value: Number(config.dph ?? 0).toFixed(0), unit: "%" },
      { label: "Zdroj cen", value: priceProviderLabel },
      { label: "Sluzba obchodu", value: formatFeeValue(config.poplatky?.komodita_sluzba), unit: "Kc/kWh" },
      { label: "OZE", value: formatFeeValue(config.poplatky?.oze), unit: "Kc/kWh" },
      { label: "Dan", value: formatFeeValue(config.poplatky?.dan), unit: "Kc/kWh" },
      { label: "Systemove sluzby", value: formatFeeValue(config.poplatky?.systemove_sluzby), unit: "Kc/kWh" },
      { label: "Distribuce NT", value: formatFeeValue(config.poplatky?.distribuce?.NT), unit: "Kc/kWh" },
      { label: "Distribuce VT", value: formatFeeValue(config.poplatky?.distribuce?.VT), unit: "Kc/kWh" },
      { label: "Staly plat", value: formatFeeValue(config.fixni?.denni?.staly_plat), unit: "Kc/den" },
      {
        label: "Nesitova infrastruktura",
        value: formatFeeValue(config.fixni?.mesicni?.provoz_nesitove_infrastruktury),
        unit: "Kc/mesic",
      },
      { label: "Jistic", value: formatFeeValue(config.fixni?.mesicni?.jistic), unit: "Kc/mesic" },
      {
        label: "Koeficient snizeni ceny",
        value: formatFeeValue(config.prodej?.koeficient_snizeni_ceny),
        unit: "Kc/MWh",
      },
      { label: "Import entity_id", value: config.influxdb?.entity_id || "-" },
      { label: "Export entity_id", value: config.influxdb?.export_entity_id || "-" },
      { label: "Baterie (SoC entity_id)", value: config.battery?.soc_entity_id || "-" },
      {
        label: "Baterie kapacita (usable)",
        value: config.battery?.usable_capacity_kwh ?? "-",
        unit: config.battery?.usable_capacity_kwh != null ? "kWh" : undefined,
      },
      {
        label: "Baterie rezerva",
        value: config.battery?.reserve_soc_percent ?? "-",
        unit: config.battery?.reserve_soc_percent != null ? "%" : undefined,
      },
    ];
  }, [config, priceProviderLabel]);

  const defaultFeesValues = useMemo(() => {
    if (!config) return null;
    return {
      dph: config.dph ?? "",
      poplatky: {
        komodita_sluzba: config.poplatky?.komodita_sluzba ?? "",
        oze: config.poplatky?.oze ?? "",
        dan: config.poplatky?.dan ?? "",
        systemove_sluzby: config.poplatky?.systemove_sluzby ?? "",
        distribuce: {
          NT: config.poplatky?.distribuce?.NT ?? "",
          VT: config.poplatky?.distribuce?.VT ?? "",
        },
      },
      fixni: {
        denni: {
          staly_plat: config.fixni?.denni?.staly_plat ?? "",
        },
        mesicni: {
          provoz_nesitove_infrastruktury: config.fixni?.mesicni?.provoz_nesitove_infrastruktury ?? "",
          jistic: config.fixni?.mesicni?.jistic ?? "",
        },
      },
      prodej: {
        koeficient_snizeni_ceny: config.prodej?.koeficient_snizeni_ceny ?? "",
      },
    };
  }, [config]);

  const cacheRows = useMemo(() => {
    if (!cacheStatus?.prices) return [];
    const status = cacheStatus.prices;
    return [
      { label: "Cache dny", value: `${status.count} dni` },
      { label: "Cache nejnovejsi", value: status.latest || "-" },
      { label: "Cache velikost", value: formatBytes(status.size_bytes) },
      { label: "Cache cesta", value: status.dir, valueWrap: true },
    ];
  }, [cacheStatus]);

  const consumptionCacheRows = useMemo(() => {
    if (!cacheStatus?.consumption) return [];
    const status = cacheStatus.consumption;
    return [
      { label: "Cache dny", value: `${status.count} dni` },
      { label: "Cache nejnovejsi", value: status.latest || "-" },
      { label: "Cache velikost", value: formatBytes(status.size_bytes) },
      { label: "Cache cesta", value: status.dir, valueWrap: true },
    ];
  }, [cacheStatus]);

  const todayData = useMemo(() => {
    if (!prices.length) return [];
    return prices.slice(0, 96).map((p, i) => ({
      slot: i,
      time: formatSlotToTime(i),
      spot: p.spot,
      extra: p.final - p.spot,
      final: p.final,
    }));
  }, [prices]);

  const tomorrowData = useMemo(() => {
    if (!prices.length) return [];
    return prices.slice(96, 192).map((p, i) => ({
      slot: i,
      time: formatSlotToTime(i),
      spot: p.spot,
      extra: p.final - p.spot,
      final: p.final,
    }));
  }, [prices]);

  const kpiItems = useMemo(() => {
    const currentPriceItem =
      Number.isInteger(currentSlot) && currentSlot >= 0 && currentSlot < todayData.length ? todayData[currentSlot] : null;
    const minFinal = todayData.length ? Math.min(...todayData.map((item) => item.final)) : null;
    const maxFinal = todayData.length ? Math.max(...todayData.map((item) => item.final)) : null;
    const todayCost = todayCostsKpi?.cost_total ?? null;
    const todayExport = todayExportKpi?.sell_total ?? null;
    const netTotal = todayCost != null || todayExport != null ? (todayCost || 0) - (todayExport || 0) : null;
    const batterySoc = batteryData?.status?.soc_percent;
    const batteryState = batteryData?.status?.battery_state;
    const batteryPower = batteryData?.status?.battery_power_w;
    const batteryProjection = batteryData?.projection;

    const batteryText =
      batterySoc == null
        ? "-"
        : `${batterySoc.toFixed(0)} %${batteryState && batteryState !== "unknown" ? ` (${batteryState})` : ""}`;
    const batteryPowerDetail =
      batteryPower == null ? null : `${batteryPower >= 0 ? "+" : ""}${Math.round(batteryPower)} W`;
    let batteryEtaDetail = null;
    if (batteryData?.is_today && batteryProjection?.state === "charging" && batteryProjection?.eta_to_full_at) {
      const etaTime = formatEtaTime(batteryProjection.eta_to_full_at);
      const etaDuration = formatEtaDuration(batteryProjection.eta_to_full_minutes);
      if (etaTime) {
        batteryEtaDetail = `plna v ${etaTime}${etaDuration ? ` (${etaDuration})` : ""}`;
      }
    } else if (batteryData?.is_today && batteryProjection?.state === "discharging" && batteryProjection?.eta_to_reserve_at) {
      const etaTime = formatEtaTime(batteryProjection.eta_to_reserve_at);
      const etaDuration = formatEtaDuration(batteryProjection.eta_to_reserve_minutes);
      if (etaTime) {
        batteryEtaDetail = `do rezervy v ${etaTime}${etaDuration ? ` (${etaDuration})` : ""}`;
      }
    }
    const batteryDetail = [batteryPowerDetail, batteryEtaDetail].filter(Boolean).join(" | ") || null;

    return [
      {
        key: "price-now",
        label: "Cena ted",
        value: currentPriceItem ? formatCurrency(currentPriceItem.final) : "-",
        detail: currentPriceItem ? currentPriceItem.time : null,
        tone: "price",
      },
      {
        key: "price-min",
        label: "Dnes min",
        value: minFinal != null ? formatCurrency(minFinal) : "-",
        tone: "neutral",
      },
      {
        key: "price-max",
        label: "Dnes max",
        value: maxFinal != null ? formatCurrency(maxFinal) : "-",
        tone: "neutral",
      },
      {
        key: "cost-today",
        label: "Naklad dnes",
        value: formatCurrency(todayCost),
        detail: todayCostsKpi?.kwh_total != null ? `${todayCostsKpi.kwh_total.toFixed(2)} kWh` : null,
        tone: "buy",
      },
      {
        key: "export-today",
        label: "Export dnes",
        value: formatCurrency(todayExport),
        detail: todayExportKpi?.export_kwh_total != null ? `${todayExportKpi.export_kwh_total.toFixed(2)} kWh` : null,
        tone: "sell",
      },
      {
        key: "net-today",
        label: "Netto dnes",
        value: formatCurrency(netTotal),
        tone: netTotal != null && netTotal <= 0 ? "sell" : "buy",
      },
      {
        key: "battery",
        label: "Baterie",
        value: batteryText,
        detail: batteryDetail,
        tone: "battery",
      },
    ];
  }, [todayData, currentSlot, todayCostsKpi, todayExportKpi, batteryData]);

  const today = new Date();
  const tomorrow = new Date(today);
  tomorrow.setDate(today.getDate() + 1);
  const showDetailAnnotations = pageMode === "detail";
  const finalPlannerError = plannerValidationError || plannerError;

  return (
    <div className={`app ${pageMode === "detail" ? "app--detail" : ""}`.trim()}>
      <header className="app-header">
        <div>
          <h1>Elektroapp</h1>
          <div className="subhead">Ceny, nakup a prodej energie v realnem case</div>
        </div>
        <div className="header-toggles">
          <div className="view-mode-toggle" role="tablist" aria-label="Rezimu stranky">
            <button
              type="button"
              className={`view-mode-btn ${pageMode === "overview" ? "is-active" : ""}`}
              onClick={() => setPageMode("overview")}
              role="tab"
              aria-selected={pageMode === "overview"}
            >
              Prehled
            </button>
            <button
              type="button"
              className={`view-mode-btn ${pageMode === "detail" ? "is-active" : ""}`}
              onClick={() => setPageMode("detail")}
              role="tab"
              aria-selected={pageMode === "detail"}
            >
              Detail
            </button>
          </div>
          <div className="theme-toggle">
            <input
              type="checkbox"
              id="theme-toggle"
              checked={theme === "dark"}
              onChange={(e) => setTheme(e.target.checked ? "dark" : "light")}
            />
            <label htmlFor="theme-toggle" aria-label="Prepnout rezim" title="Prepnout rezim">
              <span className="theme-toggle-track">
                <span className="theme-toggle-scenery">
                  <svg viewBox="0 0 24 24" className="theme-toggle-moon" aria-hidden="true">
                    <path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z" />
                  </svg>
                  <svg viewBox="0 0 24 24" className="theme-toggle-sun" aria-hidden="true">
                    <circle cx="12" cy="12" r="5" />
                    <line x1="12" y1="1" x2="12" y2="3" />
                    <line x1="12" y1="21" x2="12" y2="23" />
                    <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
                    <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
                    <line x1="1" y1="12" x2="3" y2="12" />
                    <line x1="21" y1="12" x2="23" y2="12" />
                    <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
                    <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
                  </svg>
                </span>
                <span className="theme-toggle-ball" />
              </span>
            </label>
          </div>
          <div className="theme-toggle refresh-toggle">
            <input
              type="checkbox"
              id="refresh-toggle"
              checked={autoRefreshEnabled}
              onChange={(e) => setAutoRefreshEnabled(e.target.checked)}
            />
            <label htmlFor="refresh-toggle" aria-label="Auto refresh" title="Auto refresh">
              <span className="theme-toggle-track">
                <span className="theme-toggle-scenery">
                  <svg viewBox="0 0 24 24" className="toggle-icon toggle-icon-on" aria-hidden="true">
                    <path d="M21 12a9 9 0 00-15.3-6.3" />
                    <path d="M3 4v6h6" />
                    <path d="M3 12a9 9 0 0015.3 6.3" />
                    <path d="M21 20v-6h-6" />
                  </svg>
                  <svg viewBox="0 0 24 24" className="toggle-icon toggle-icon-off" aria-hidden="true">
                    <line x1="6" y1="6" x2="18" y2="18" />
                    <line x1="18" y1="6" x2="6" y2="18" />
                  </svg>
                </span>
                <span className="theme-toggle-ball" />
              </span>
            </label>
          </div>
        </div>
      </header>

      <section className="kpi-strip" aria-label="Dnesni KPI">
        {kpiItems.map((item) => (
          <div key={item.key} className={`kpi-tile ${item.tone ? `kpi-tile--${item.tone}` : ""}`}>
            <div className="kpi-tile-label">{item.label}</div>
            <div className="kpi-tile-value">{item.value}</div>
            {item.detail ? <div className="kpi-tile-detail">{item.detail}</div> : <div className="kpi-tile-detail" />}
          </div>
        ))}
      </section>

      {pageMode === "overview" ? (
        <>
          <section className="section">
            <h2>Cena elektriny (Kc/kWh)</h2>
            <PriceChartCard
              className="card-spaced"
              chartData={todayData}
              title={`Dnes (${formatDate(today)})`}
              vtPeriods={config?.tarif?.vt_periods}
              highlightSlot={currentSlot}
            />
            <PriceChartCard
              className="card-spaced"
              chartData={tomorrowData}
              title={`Zitra (${formatDate(tomorrow)})`}
              fallbackMessage="Data pro nasledujici den zatim nebyla publikovana"
              vtPeriods={config?.tarif?.vt_periods}
            />
          </section>

          <section className="section">
            <CostChartCard
              selectedDate={selectedDate}
              setSelectedDate={setSelectedDate}
              costs={costs}
              costsSummary={costsSummary}
              costsError={costsError}
              costsFromCache={costsFromCache}
              costsCacheFallback={costsCacheFallback}
              showAnnotations={false}
            />
            <ExportChartCard
              selectedDate={selectedDate}
              setSelectedDate={setSelectedDate}
              exportPoints={exportPoints}
              exportSummary={exportSummary}
              exportError={exportError}
              exportFromCache={exportFromCache}
              exportCacheFallback={exportCacheFallback}
              showAnnotations={false}
            />
          </section>

          <button onClick={() => setShowMonthlySummary(!showMonthlySummary)} className="ghost-button">
            {showMonthlySummary ? "Skryt souhrn" : "Zobrazit souhrn"}
          </button>

          {showMonthlySummary && (
            <section className="section">
              <MonthlySummaryCard
                selectedMonth={selectedMonth}
                setSelectedMonth={setSelectedMonth}
                monthlySummary={monthlySummary}
                monthlyTotals={monthlyTotals}
                monthlyError={monthlyError}
              />
            </section>
          )}

          <button onClick={() => setShowBilling(!showBilling)} className="ghost-button">
            {showBilling ? "Skryt vyuctovani" : "Odhad vyuctovani"}
          </button>

          {showBilling && (
            <BillingCard
              billingMode={billingMode}
              setBillingMode={setBillingMode}
              billingMonth={billingMonth}
              setBillingMonth={setBillingMonth}
              billingYear={billingYear}
              setBillingYear={setBillingYear}
              billingData={billingData}
              billingLoading={billingLoading}
              billingError={billingError}
            />
          )}

          <button onClick={() => setShowBatteryPanel(!showBatteryPanel)} className="ghost-button">
            {showBatteryPanel ? "Skryt baterii a projekci" : "Baterie a projekce"}
          </button>

          {showBatteryPanel && (
            <BatteryProjectionCard
              batteryData={batteryData}
              batteryLoading={batteryLoading}
              batteryError={batteryError}
              onRefresh={refreshBattery}
            />
          )}

          <button onClick={() => setShowPlanner(!showPlanner)} className="ghost-button">
            {showPlanner ? "Skryt planovac" : "Zobrazit planovac"}
          </button>

          {showPlanner && (
            <PlannerCard
              plannerDuration={plannerDuration}
              setPlannerDuration={setPlannerDuration}
              loadPlanner={handleLoadPlanner}
              plannerError={finalPlannerError}
              plannerLoading={plannerLoading}
              plannerNote={plannerNote}
              plannerResults={plannerResults}
            />
          )}

          <button onClick={() => setShowConfig(!showConfig)} className="ghost-button">
            {showConfig ? "Skryt konfiguraci" : "Zobrazit konfiguraci"}
          </button>

          {showConfig && (
            <ConfigCard
              configRows={configRows}
              cacheRows={cacheRows}
              consumptionCacheRows={consumptionCacheRows}
              cacheStatus={cacheStatus}
              showFeesHistory={showFeesHistory}
              onToggleFeesHistory={() => setShowFeesHistory((prev) => !prev)}
              feesHistory={feesHistory}
              feesHistoryLoading={feesHistoryLoading}
              feesHistoryError={feesHistoryError}
              onSaveFeesHistory={saveFeesHistory}
              defaultFeesValues={defaultFeesValues}
              priceProviderLabel={priceProviderLabel}
              priceProviderUrl={priceProviderUrl}
              onRefreshPrices={refreshPrices}
              refreshingPrices={pricesRefreshLoading}
              pricesRefreshMessage={pricesRefreshMessage}
              pricesRefreshError={pricesRefreshError}
            />
          )}
        </>
      ) : (
        <>
          <section className="section">
            <h2>Detail grafu cen a toku energie</h2>
            <PriceChartCard
              className="card-spaced"
              chartData={todayData}
              title={`Dnes (${formatDate(today)})`}
              vtPeriods={config?.tarif?.vt_periods}
              highlightSlot={currentSlot}
            />
          </section>

          <section className="section detail-grid">
            <CostChartCard
              selectedDate={selectedDate}
              setSelectedDate={setSelectedDate}
              costs={costs}
              costsSummary={costsSummary}
              costsError={costsError}
              costsFromCache={costsFromCache}
              costsCacheFallback={costsCacheFallback}
              showAnnotations={showDetailAnnotations}
            />
            <ExportChartCard
              selectedDate={selectedDate}
              setSelectedDate={setSelectedDate}
              exportPoints={exportPoints}
              exportSummary={exportSummary}
              exportError={exportError}
              exportFromCache={exportFromCache}
              exportCacheFallback={exportCacheFallback}
              showAnnotations={showDetailAnnotations}
            />
          </section>

          <section className="section detail-grid">
            <EnergyBalanceCard
              period={energyBalancePeriod}
              anchor={normalizeEnergyBalanceAnchor(energyBalancePeriod, energyBalanceAnchor)}
              onPrev={() =>
                setEnergyBalanceAnchor((prev) => shiftEnergyBalanceAnchor(energyBalancePeriod, prev, -1))
              }
              onNext={() =>
                setEnergyBalanceAnchor((prev) => shiftEnergyBalanceAnchor(energyBalancePeriod, prev, 1))
              }
              onPeriodChange={(value) => {
                setEnergyBalancePeriod(value);
                setEnergyBalanceAnchor((prev) => normalizeEnergyBalanceAnchor(value, prev));
              }}
              data={energyBalanceData}
              loading={energyBalanceLoading}
              error={energyBalanceError}
            />
            <HistoryHeatmapCard
              month={heatmapMonth}
              setMonth={setHeatmapMonth}
              metric={heatmapMetric}
              setMetric={setHeatmapMetric}
              heatmapData={heatmapData}
              loading={heatmapLoading}
              error={heatmapError}
              onSelectDate={(dateValue) => setSelectedDate(dateValue)}
            />
          </section>

          <section className="section">
            <BatteryProjectionCard
              batteryData={batteryData}
              batteryLoading={batteryLoading}
              batteryError={batteryError}
              onRefresh={refreshBattery}
            />
          </section>
        </>
      )}

      <footer className="footer">
        <div>
          (c) {new Date().getFullYear()} mondychan{" "}
          <a href="https://github.com/mondychan" target="_blank" rel="noopener noreferrer">
            github
          </a>
        </div>
        <div className="version-tag">Verze doplnku: {version || "-"}</div>
        <div>
          Zdroj dat:{" "}
          <a href={priceProviderUrl} target="_blank" rel="noopener noreferrer">
            {priceProviderLabel}
          </a>
        </div>
      </footer>
    </div>
  );
}

export default App;
