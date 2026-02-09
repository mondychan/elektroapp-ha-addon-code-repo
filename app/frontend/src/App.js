import React, { useEffect, useState, useMemo } from "react";
import axios from "axios";
import PriceChartCard from "./components/PriceChartCard";
import CostChartCard from "./components/CostChartCard";
import ExportChartCard from "./components/ExportChartCard";
import MonthlySummaryCard from "./components/MonthlySummaryCard";
import BillingCard from "./components/BillingCard";
import PlannerCard from "./components/PlannerCard";
import ConfigCard from "./components/ConfigCard";
import { formatDate, formatBytes, formatSlotToTime } from "./utils/formatters";

function App() {
  const [data, setData] = useState([]);
  const [config, setConfig] = useState(null);
  const [cacheStatus, setCacheStatus] = useState(null);
  const [version, setVersion] = useState(null);
  const [showConfig, setShowConfig] = useState(false);
  const [showMonthlySummary, setShowMonthlySummary] = useState(false);
  const [theme, setTheme] = useState(() => localStorage.getItem("theme") || "light");
  const [costs, setCosts] = useState([]);
  const [costsSummary, setCostsSummary] = useState(null);
  const [costsError, setCostsError] = useState(null);
  const [costsFromCache, setCostsFromCache] = useState(false);
  const [costsCacheFallback, setCostsCacheFallback] = useState(false);
  const [exportPoints, setExportPoints] = useState([]);
  const [exportSummary, setExportSummary] = useState(null);
  const [exportError, setExportError] = useState(null);
  const [exportFromCache, setExportFromCache] = useState(false);
  const [exportCacheFallback, setExportCacheFallback] = useState(false);
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
  const [monthlySummary, setMonthlySummary] = useState([]);
  const [monthlyTotals, setMonthlyTotals] = useState(null);
  const [showPlanner, setShowPlanner] = useState(false);
  const [plannerResults, setPlannerResults] = useState([]);
  const [plannerLoading, setPlannerLoading] = useState(false);
  const [plannerError, setPlannerError] = useState(null);
  const [plannerNote, setPlannerNote] = useState(null);
  const [monthlyError, setMonthlyError] = useState(null);
  const [showBilling, setShowBilling] = useState(false);
  const [billingMode, setBillingMode] = useState("month");
  const [billingMonth, setBillingMonth] = useState(() => {
    const today = new Date();
    const y = today.getFullYear();
    const m = String(today.getMonth() + 1).padStart(2, "0");
    return `${y}-${m}`;
  });
  const [billingYear, setBillingYear] = useState(() => String(new Date().getFullYear()));
  const [billingData, setBillingData] = useState(null);
  const [billingLoading, setBillingLoading] = useState(false);
  const [billingError, setBillingError] = useState(null);
  const [plannerDuration, setPlannerDuration] = useState(() => localStorage.getItem("plannerDuration") || "120");
  const [currentSlot, setCurrentSlot] = useState(null);
  const [autoRefreshEnabled, setAutoRefreshEnabled] = useState(() => {
    return localStorage.getItem("autoRefreshEnabled") !== "false";
  });
  const [isPageVisible, setIsPageVisible] = useState(() => document.visibilityState === "visible");
  const [showFeesHistory, setShowFeesHistory] = useState(false);
  const [feesHistory, setFeesHistory] = useState([]);
  const [feesHistoryLoading, setFeesHistoryLoading] = useState(false);
  const [feesHistoryError, setFeesHistoryError] = useState(null);
  const [pricesRefreshLoading, setPricesRefreshLoading] = useState(false);
  const [pricesRefreshMessage, setPricesRefreshMessage] = useState(null);
  const [pricesRefreshError, setPricesRefreshError] = useState(null);

  useEffect(() => {
    document.body.dataset.theme = theme;
    localStorage.setItem("theme", theme);
  }, [theme]);

  useEffect(() => {
    localStorage.setItem("autoRefreshEnabled", autoRefreshEnabled ? "true" : "false");
  }, [autoRefreshEnabled]);

  useEffect(() => {
    const handleVisibility = () => {
      setIsPageVisible(document.visibilityState === "visible");
    };
    document.addEventListener("visibilitychange", handleVisibility);
    return () => document.removeEventListener("visibilitychange", handleVisibility);
  }, []);

  useEffect(() => {
    const updateSlot = () => {
      const now = new Date();
      const slot = now.getHours() * 4 + Math.floor(now.getMinutes() / 15);
      setCurrentSlot(slot);
    };
    updateSlot();
    const intervalId = setInterval(updateSlot, 60000);
    return () => clearInterval(intervalId);
  }, []);

  const API_PREFIX = "./api";
  const activePriceProvider = config?.price_provider === "ote" ? "ote" : "spotovaelektrina";
  const priceProviderLabel = activePriceProvider === "ote" ? "OTE (ote-cr.cz + CNB)" : "spotovaelektrina.cz";
  const priceProviderUrl = activePriceProvider === "ote" ? "https://www.ote-cr.cz/" : "https://spotovaelektrina.cz/";
  const buildInfluxError = (err) => {
    const detail = err?.response?.data?.detail;
    if (detail) {
      return String(detail);
    }
    if (err?.response?.status === 401) {
      return "Nepodarilo se overit pristup k InfluxDB (401). Zkontroluj uzivatele a heslo.";
    }
    if (err?.response?.status) {
      return `Chyba pri nacitani z InfluxDB (HTTP ${err.response.status}).`;
    }
    return "Nepodarilo se pripojit k InfluxDB.";
  };

  const fetchPrices = () => {
    axios
      .get(`${API_PREFIX}/prices`)
      .then((res) => setData(res.data.prices))
      .catch((err) => console.error("Error fetching prices:", err));
  };

  const refreshPrices = () => {
    setPricesRefreshLoading(true);
    setPricesRefreshMessage(null);
    setPricesRefreshError(null);
    axios
      .post(`${API_PREFIX}/prices/refresh`, {})
      .then((res) => {
        const refreshed = res.data?.refreshed || [];
        const summary = refreshed.map((item) => `${item.date}: ${item.count} zaznamu`).join(" | ");
        setPricesRefreshMessage(summary || "Ceny byly obnoveny.");
        fetchPrices();
        if (showConfig) {
          axios
            .get(`${API_PREFIX}/cache-status`)
            .then((cacheRes) => setCacheStatus(cacheRes.data))
            .catch((cacheErr) => console.error("Error fetching cache status:", cacheErr));
        }
      })
      .catch((err) => {
        console.error("Error refreshing prices:", err);
        const detail = err?.response?.data?.detail;
        setPricesRefreshError(detail ? String(detail) : "Obnoveni cen selhalo.");
      })
      .finally(() => setPricesRefreshLoading(false));
  };

  useEffect(() => {
    fetchPrices();
  }, []);

  useEffect(() => {
    axios
      .get(`${API_PREFIX}/config`)
      .then((res) => setConfig(res.data))
      .catch((err) => console.error("Error fetching config:", err));
  }, []);

  useEffect(() => {
    axios
      .get(`${API_PREFIX}/version`)
      .then((res) => setVersion(res.data.version))
      .catch((err) => console.error("Error fetching version:", err));
  }, []);

  useEffect(() => {
    if (!showConfig) return;
    axios
      .get(`${API_PREFIX}/cache-status`)
      .then((res) => setCacheStatus(res.data))
      .catch((err) => console.error("Error fetching cache status:", err));
  }, [showConfig]);

  const fetchCosts = (dateValue, options = {}) => {
    const { reset = true } = options;
    if (reset) {
      setCosts([]);
      setCostsSummary(null);
      setCostsError(null);
      setCostsFromCache(false);
      setCostsCacheFallback(false);
    }
    axios
      .get(`${API_PREFIX}/costs`, { params: { date: dateValue } })
      .then((res) => {
        setCosts(res.data.points || []);
        setCostsSummary(res.data.summary || null);
        setCostsFromCache(Boolean(res.data.from_cache));
        setCostsCacheFallback(Boolean(res.data.cache_fallback));
      })
      .catch((err) => {
        console.error("Error fetching costs:", err);
        setCostsError(buildInfluxError(err));
        setCostsFromCache(false);
        setCostsCacheFallback(false);
      });
  };

  const fetchExport = (dateValue, options = {}) => {
    const { reset = true } = options;
    if (reset) {
      setExportPoints([]);
      setExportSummary(null);
      setExportError(null);
      setExportFromCache(false);
      setExportCacheFallback(false);
    }
    axios
      .get(`${API_PREFIX}/export`, { params: { date: dateValue } })
      .then((res) => {
        setExportPoints(res.data.points || []);
        setExportSummary(res.data.summary || null);
        setExportFromCache(Boolean(res.data.from_cache));
        setExportCacheFallback(Boolean(res.data.cache_fallback));
      })
      .catch((err) => {
        console.error("Error fetching export:", err);
        setExportError(buildInfluxError(err));
        setExportFromCache(false);
        setExportCacheFallback(false);
      });
  };

  useEffect(() => {
    fetchCosts(selectedDate, { reset: true });
  }, [selectedDate]);

  useEffect(() => {
    fetchExport(selectedDate, { reset: true });
  }, [selectedDate]);

  useEffect(() => {
    setMonthlySummary([]);
    setMonthlyTotals(null);
    setMonthlyError(null);
    axios
      .get(`${API_PREFIX}/daily-summary`, { params: { month: selectedMonth } })
      .then((res) => {
        setMonthlySummary(res.data.days || []);
        setMonthlyTotals(res.data.summary || null);
      })
      .catch((err) => {
        console.error("Error fetching monthly summary:", err);
        setMonthlyError(buildInfluxError(err));
      });
  }, [selectedMonth]);

  useEffect(() => {
    if (!showBilling) return;
    setBillingLoading(true);
    setBillingError(null);
    setBillingData(null);
    const endpoint = billingMode === "year" ? "/billing-year" : "/billing-month";
    const params = billingMode === "year" ? { year: Number(billingYear) } : { month: billingMonth };
    if (billingMode === "year" && !params.year) {
      setBillingLoading(false);
      return;
    }
    axios
      .get(`${API_PREFIX}${endpoint}`, { params })
      .then((res) => setBillingData(res.data))
      .catch((err) => {
        console.error("Error fetching billing summary:", err);
        setBillingError(buildInfluxError(err));
      })
      .finally(() => setBillingLoading(false));
  }, [showBilling, billingMode, billingMonth, billingYear]);

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
      {
        label: "Import entity_id",
        value: config.influxdb?.entity_id || "-",
      },
      {
        label: "Export entity_id",
        value: config.influxdb?.export_entity_id || "-",
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

  const fetchFeesHistory = () => {
    setFeesHistoryLoading(true);
    setFeesHistoryError(null);
    axios
      .get(`${API_PREFIX}/fees-history`)
      .then((res) => setFeesHistory(res.data.history || []))
      .catch((err) => {
        console.error("Error fetching fees history:", err);
        setFeesHistoryError("Nepodarilo se nacist historii poplatku.");
      })
      .finally(() => setFeesHistoryLoading(false));
  };

  const saveFeesHistory = (historyPayload) => {
    setFeesHistoryLoading(true);
    setFeesHistoryError(null);
    return axios
      .put(`${API_PREFIX}/fees-history`, { history: historyPayload })
      .then((res) => {
        setFeesHistory(res.data.history || []);
        return res.data.history || [];
      })
      .catch((err) => {
        console.error("Error saving fees history:", err);
        const detail = err?.response?.data?.detail;
        setFeesHistoryError(detail ? String(detail) : "Nepodarilo se ulozit historii poplatku.");
        throw err;
      })
      .finally(() => setFeesHistoryLoading(false));
  };

  const isTodayDateStr = (dateStr) => {
    const today = new Date();
    const y = today.getFullYear();
    const m = String(today.getMonth() + 1).padStart(2, "0");
    const d = String(today.getDate()).padStart(2, "0");
    return dateStr === `${y}-${m}-${d}`;
  };

  useEffect(() => {
    if (!showConfig || !showFeesHistory) return;
    fetchFeesHistory();
  }, [showConfig, showFeesHistory]);

  useEffect(() => {
    if (!autoRefreshEnabled || !isPageVisible) return;
    const refresh = () => {
      fetchPrices();
      if (isTodayDateStr(selectedDate)) {
        fetchCosts(selectedDate, { reset: false });
        fetchExport(selectedDate, { reset: false });
      }
    };
    refresh();
    const intervalId = setInterval(refresh, 600000);
    return () => clearInterval(intervalId);
  }, [autoRefreshEnabled, isPageVisible, selectedDate]);

  const normalizeDuration = (value) => {
    if (value == null || value === "") return null;
    const parsed = Number.parseInt(value, 10);
    if (!Number.isFinite(parsed) || parsed <= 0) return null;
    if (parsed > 360) return "too-long";
    return Math.round(parsed);
  };

  const loadPlanner = () => {
    const rawValue = plannerDuration;
    const durationValue = normalizeDuration(rawValue);
    if (durationValue === "too-long") {
      setPlannerError("Okno je prilis dlouhe. Zadej delku 1-360 minut.");
      return;
    }
    if (!durationValue) {
      setPlannerError("Zadej delku programu 1-360 minut.");
      return;
    }
    localStorage.setItem("plannerDuration", String(durationValue));
    setPlannerLoading(true);
    setPlannerError(null);
    setPlannerNote(null);
    axios
      .get(`${API_PREFIX}/schedule`, {
        params: {
          duration: durationValue,
          count: 3,
        },
      })
      .then((res) => {
        setPlannerResults(res.data.recommendations || []);
        setPlannerNote(res.data.note || null);
      })
      .catch((err) => {
        console.error("Error fetching planner:", err);
        if (err?.response?.status === 422) {
          setPlannerError("Okno je prilis dlouhe. Zadej delku 1-360 minut.");
          return;
        }
        setPlannerError("Planovac neni k dispozici.");
      })
      .finally(() => setPlannerLoading(false));
  };

  const todayData = useMemo(() => {
    if (!data.length) return [];
    return data.slice(0, 96).map((p, i) => ({
      slot: i,
      time: formatSlotToTime(i),
      spot: p.spot,
      extra: p.final - p.spot,
      final: p.final,
    }));
  }, [data]);

  const tomorrowData = useMemo(() => {
    if (!data.length) return [];
    return data.slice(96, 192).map((p, i) => ({
      slot: i,
      time: formatSlotToTime(i),
      spot: p.spot,
      extra: p.final - p.spot,
      final: p.final,
    }));
  }, [data]);

  const today = new Date();
  const tomorrow = new Date(today);
  tomorrow.setDate(today.getDate() + 1);

  return (
    <div className="app">
      <header className="app-header">
        <div>
          <h1>Elektroapp</h1>
          <div className="subhead">Ceny, nakup a prodej energie v realnem case</div>
        </div>
        <div className="header-toggles">
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
        />
        <ExportChartCard
          selectedDate={selectedDate}
          setSelectedDate={setSelectedDate}
          exportPoints={exportPoints}
          exportSummary={exportSummary}
          exportError={exportError}
          exportFromCache={exportFromCache}
          exportCacheFallback={exportCacheFallback}
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

      <button onClick={() => setShowPlanner(!showPlanner)} className="ghost-button">
        {showPlanner ? "Skryt planovac" : "Zobrazit planovac"}
      </button>

      {showPlanner && (
        <PlannerCard
          plannerDuration={plannerDuration}
          setPlannerDuration={setPlannerDuration}
          loadPlanner={loadPlanner}
          plannerError={plannerError}
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
