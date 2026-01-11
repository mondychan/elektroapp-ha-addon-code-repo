import React, { useEffect, useState, useMemo } from "react";
import axios from "axios";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ResponsiveContainer,
  Cell,
  ComposedChart,
  Line
} from "recharts";
import * as d3 from "d3-scale";

function App() {
  const [data, setData] = useState([]);
  const [config, setConfig] = useState(null);
  const [showConfig, setShowConfig] = useState(false);
  const [showMonthlySummary, setShowMonthlySummary] = useState(false);
  const [theme, setTheme] = useState(() => {
    return localStorage.getItem("theme") || "light";
  });
  const [costs, setCosts] = useState([]);
  const [costsSummary, setCostsSummary] = useState(null);
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

  // --- nový state pro čas ---
  const [currentTime, setCurrentTime] = useState(new Date());

  // --- efekt pro aktualizaci času ---
  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    document.body.dataset.theme = theme;
    localStorage.setItem("theme", theme);
  }, [theme]);

  const API_PREFIX = "./api";

  // --- Načtení cen (dnes + zítra) ---
  useEffect(() => {
    axios.get(`${API_PREFIX}/prices`)
      .then(res => setData(res.data.prices))
      .catch(err => console.error("Error fetching prices:", err));
  }, []);

  // --- Načtení konfigurace ---
  useEffect(() => {
    axios.get(`${API_PREFIX}/config`)
      .then(res => setConfig(res.data))
      .catch(err => console.error("Error fetching config:", err));
  }, []);

  // --- Načtení nákladů za spotřebu ---
  useEffect(() => {
    setCosts([]);
    setCostsSummary(null);
    axios.get(`${API_PREFIX}/costs`, { params: { date: selectedDate } })
      .then(res => {
        setCosts(res.data.points || []);
        setCostsSummary(res.data.summary || null);
      })
      .catch(err => console.error("Error fetching costs:", err));
  }, [selectedDate]);

  // --- Načtení měsíčního souhrnu ---
  useEffect(() => {
    setMonthlySummary([]);
    setMonthlyTotals(null);
    axios.get(`${API_PREFIX}/daily-summary`, { params: { month: selectedMonth } })
      .then(res => {
        setMonthlySummary(res.data.days || []);
        setMonthlyTotals(res.data.summary || null);
      })
      .catch(err => console.error("Error fetching monthly summary:", err));
  }, [selectedMonth]);


  // --- funkce pro převod slotu na HH:MM ---
  const formatDate = (date) => date.toLocaleDateString("cs-CZ");
  const toDateInputValue = (date) => {
    const y = date.getFullYear();
    const m = String(date.getMonth() + 1).padStart(2, "0");
    const d = String(date.getDate()).padStart(2, "0");
    return `${y}-${m}-${d}`;
  };
  const selectedDateObj = useMemo(() => new Date(`${selectedDate}T00:00:00`), [selectedDate]);
  const formatMonthLabel = (monthStr) => {
    const [y, m] = monthStr.split("-");
    return new Date(`${y}-${m}-01T00:00:00`).toLocaleDateString("cs-CZ", { year: "numeric", month: "long" });
  };

  const formatSlotToTime = (slot) => {
    const hour = Math.floor(slot / 4);
    const minute = (slot % 4) * 15;
    return `${hour.toString().padStart(2, "0")}:${minute.toString().padStart(2, "0")}`;
  };

  const todayData = useMemo(() => {
    if (!data.length) return [];
    return data.slice(0, 96).map((p, i) => ({
      slot: i,
      time: formatSlotToTime(i),
      spot: p.spot,
      extra: p.final - p.spot,
      final: p.final
    }));
  }, [data]);

  const tomorrowData = useMemo(() => {
    if (!data.length) return [];
    return data.slice(96, 192).map((p, i) => ({
      slot: i,
      time: formatSlotToTime(i),
      spot: p.spot,
      extra: p.final - p.spot,
      final: p.final
    }));
  }, [data]);

  const today = new Date();
  const tomorrow = new Date(today);
  tomorrow.setDate(today.getDate() + 1);
  const formatIsoToTime = (iso) => {
    const dt = new Date(iso);
    const h = dt.getHours().toString().padStart(2, "0");
    const m = dt.getMinutes().toString().padStart(2, "0");
    return `${h}:${m}`;
  };

  const renderChart = (chartData, title, fallbackMessage = null) => {
    if (!chartData.length) {
      return fallbackMessage ? (
        <div style={{ margin: "20px 0", fontStyle: "italic" }}>
          {fallbackMessage}
        </div>
      ) : null;
    }

    const minPrice = Math.min(...chartData.map((d) => d.final));
    const maxPrice = Math.max(...chartData.map((d) => d.final));
    const colorScale = d3.scaleLinear().domain([minPrice, maxPrice]).range(["#00FF00", "#FF0000"]);

    const getVTStatus = (slot) => {
      return config?.tarif?.vt_periods?.some(
        ([start, end]) => slot >= start * 4 && slot < end * 4
      ) ? "VT" : "NT";
    };

    return (
      <div style={{ marginBottom: 40 }}>
        <h3>{title}</h3>
        <ResponsiveContainer width="100%" height={400}>
          <BarChart data={chartData} margin={{ top: 20, right: 20, left: 40, bottom: 20 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
            <XAxis
              dataKey="time"
              tick={({ x, y, payload }) => {
                const time = payload.value;
                const [h, m] = time.split(":").map(Number);
                const slot = h * 4 + m / 15;
                const isVT = getVTStatus(slot) === "VT";
                return (
                  <text
                    x={x}
                    y={y + 10}
                    textAnchor="middle"
                    fill={isVT ? "#FF0000" : "#00AA00"}
                    fontSize={10}
                  >
                    {time} ({isVT ? "VT" : "NT"})
                  </text>
                );
              }}
            />
            <YAxis tick={{ fill: "var(--text-muted)" }} label={{ value: "Cena", angle: -90, position: "insideLeft" }} tickFormatter={(v) => `${v.toFixed(2)},-Kc`} />
            <Tooltip
              contentStyle={{ background: "var(--panel)", borderColor: "var(--border)", color: "var(--text)" }}
              itemStyle={{ color: "var(--text)" }}
              labelStyle={{ color: "var(--text)" }}
              formatter={(value, name, props) => {
                if (props.dataKey === "spot") return [`${value.toFixed(2)},-Kc`, "Spot"];
                if (props.dataKey === "extra") return [`${props.payload.final.toFixed(2)},-Kc`, "Konecna cena"];
                return [`${value.toFixed(2)},-Kc`, name];
              }}
              labelFormatter={(label, payload) => {
                if (!payload || !payload.length) return `Cas: ${label}`;
                const [h, m] = label.split(":").map(Number);
                const slot = h * 4 + m / 15;
                const vtStatus = getVTStatus(slot);
                return `Cas: ${label} (${vtStatus})`;
              }}
            />

            <Bar dataKey="spot" stackId="a">
              {chartData.map((entry, index) => (
                <Cell key={`cell-spot-${index}`} fill="#4D79FF" />
              ))}
            </Bar>
            <Bar dataKey="extra" stackId="a">
              {chartData.map((entry, index) => (
                <Cell key={`cell-extra-${index}`} fill={colorScale(entry.final)} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    );
  };

  const costChartData = useMemo(() => {
    if (!costs.length) return [];
    return costs.map((p) => ({
      time: formatIsoToTime(p.time),
      kwh: p.kwh,
      cost: p.cost
    }));
  }, [costs]);

  const renderCostChart = () => {
    if (!costChartData.length) {
      return (
        <div style={{ marginBottom: 40, fontStyle: "italic" }}>
          Data pro vybrany den nejsou k dispozici.
        </div>
      );
    }

    return (
      <div className="card" style={{ marginBottom: 40 }}>
        <div className="card-header">
          <h3>Naklady a spotreba - {formatDate(selectedDateObj)}</h3>
        </div>
        <div className="toolbar">
          <button
            onClick={() => {
              const prev = new Date(`${selectedDate}T00:00:00`);
              prev.setDate(prev.getDate() - 1);
              setSelectedDate(toDateInputValue(prev));
            }}
          >
            Prev
          </button>
          <div className="toolbar-label">{formatDate(selectedDateObj)}</div>
          <button
            onClick={() => {
              const next = new Date(`${selectedDate}T00:00:00`);
              next.setDate(next.getDate() + 1);
              setSelectedDate(toDateInputValue(next));
            }}
          >
            Next
          </button>
          <input
            type="date"
            value={selectedDate}
            onChange={(e) => setSelectedDate(e.target.value)}
          />
          <button onClick={() => {
            const today = new Date();
            setSelectedDate(toDateInputValue(today));
          }}>
            Dnes
          </button>
        </div>
        {costsSummary && (
          <div className="summary">
            Celkem: {costsSummary.kwh_total?.toFixed(2)} kWh / {costsSummary.cost_total?.toFixed(2)},-Kc
          </div>
        )}
        <ResponsiveContainer width="100%" height={400}>
          <ComposedChart data={costChartData} margin={{ top: 20, right: 40, left: 40, bottom: 20 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="time" tick={{ fill: "var(--text-muted)" }} />
            <YAxis yAxisId="left" tick={{ fill: "var(--text-muted)" }} label={{ value: "Kc", angle: -90, position: "insideLeft" }} />
            <YAxis yAxisId="right" tick={{ fill: "var(--text-muted)" }} orientation="right" label={{ value: "kWh", angle: 90, position: "insideRight" }} />
            <Tooltip
              contentStyle={{ background: "var(--panel)", borderColor: "var(--border)", color: "var(--text)" }}
              itemStyle={{ color: "var(--text)" }}
              labelStyle={{ color: "var(--text)" }}
              formatter={(value, name) => {
                if (name === "cost") return [`${value?.toFixed(2) ?? "-"},-Kc`, "Naklad"];
                if (name === "kwh") return [`${value?.toFixed(3) ?? "-"}`, "Spotreba kWh"];
                return [value, name];
              }}
            />
            <Bar yAxisId="left" dataKey="cost" fill="var(--accent)" />
            <Line yAxisId="right" type="monotone" dataKey="kwh" stroke="var(--accent-2)" dot={false} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    );
  };

  const renderMonthlyTable = () => {
    if (!monthlySummary.length) {
      return (
        <div style={{ fontStyle: "italic" }}>
          Mesicni souhrn neni k dispozici.
        </div>
      );
    }

    return (
      <div className="card" style={{ marginTop: 20 }}>
        <div className="card-header">
          <h3>Souhrn za mesic - {formatMonthLabel(selectedMonth)}</h3>
        </div>
        <div className="toolbar">
          <input
            type="month"
            value={selectedMonth}
            onChange={(e) => setSelectedMonth(e.target.value)}
          />
          <button onClick={() => {
            const today = new Date();
            const y = today.getFullYear();
            const m = String(today.getMonth() + 1).padStart(2, "0");
            setSelectedMonth(`${y}-${m}`);
          }}>
            Tento mesic
          </button>
        </div>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr>
              <th style={{ textAlign: "left", padding: "6px 4px", borderBottom: "1px solid #ddd" }}>Den</th>
              <th style={{ textAlign: "left", padding: "6px 4px", borderBottom: "1px solid #ddd" }}>Datum</th>
              <th style={{ textAlign: "right", padding: "6px 4px", borderBottom: "1px solid #ddd" }}>Spotreba (kWh)</th>
              <th style={{ textAlign: "right", padding: "6px 4px", borderBottom: "1px solid #ddd" }}>Cena (Kc)</th>
            </tr>
          </thead>
          <tbody>
            {monthlySummary.map((day) => {
              const dt = new Date(`${day.date}T00:00:00`);
              const dayName = dt.toLocaleDateString("cs-CZ", { weekday: "short" });
              return (
                <tr key={day.date}>
                  <td style={{ padding: "6px 4px", borderBottom: "1px solid #f0f0f0" }}>{dayName}</td>
                  <td style={{ padding: "6px 4px", borderBottom: "1px solid #f0f0f0" }}>{formatDate(dt)}</td>
                  <td style={{ textAlign: "right", padding: "6px 4px", borderBottom: "1px solid #f0f0f0" }}>
                    {day.kwh_total == null ? "-" : day.kwh_total.toFixed(2)}
                  </td>
                  <td style={{ textAlign: "right", padding: "6px 4px", borderBottom: "1px solid #f0f0f0" }}>
                    {day.cost_total == null ? "-" : day.cost_total.toFixed(2)}
                  </td>
                </tr>
              );
            })}
          </tbody>
          {monthlyTotals && (
            <tfoot>
              <tr>
                <td colSpan={2} style={{ padding: "6px 4px", borderTop: "1px solid #ddd" }}>Soucet</td>
                <td style={{ textAlign: "right", padding: "6px 4px", borderTop: "1px solid #ddd" }}>
                  {monthlyTotals.kwh_total?.toFixed(2)}
                </td>
                <td style={{ textAlign: "right", padding: "6px 4px", borderTop: "1px solid #ddd" }}>
                  {monthlyTotals.cost_total?.toFixed(2)}
                </td>
              </tr>
            </tfoot>
          )}
        </table>
      </div>
    );
  };

  return (
    <div className="app">
      <header className="app-header">
        <div>
          <h1>Elektroapp</h1>
          <div className="subhead">Cena a spotreba energie v realnem case</div>
        </div>
        <button
          className="icon-toggle"
          onClick={() => setTheme(theme === "light" ? "dark" : "light")}
          aria-label="Toggle theme"
          title="Toggle theme"
        >
          {theme === "light" ? "☀" : "☾"}
        </button>
      </header>

      <section className="section">
        <h2>Cena elektriny (Kc/kWh)</h2>
        {renderChart(todayData, `Dnes (${formatDate(today)})`)}
        {renderChart(tomorrowData, `Zitra (${formatDate(tomorrow)})`, "Data pro nasledujici den zatim nebyla publikovana")}
      </section>

      <section className="section">
        {renderCostChart()}
      </section>

      <button
        onClick={() => setShowMonthlySummary(!showMonthlySummary)}
        className="ghost-button"
      >
        {showMonthlySummary ? "Skryt souhrn" : "Zobrazit souhrn"}
      </button>

      {showMonthlySummary && (
        <section className="section">
          {renderMonthlyTable()}
        </section>
      )}

      <button onClick={() => setShowConfig(!showConfig)} className="ghost-button">
        {showConfig ? "Skryt konfiguraci" : "Zobrazit konfiguraci"}
      </button>

      {showConfig && (
        <div className="card" style={{ marginTop: 20 }}>
          <h3>Aktualni konfigurace</h3>
          <ul>
            <li>DPH: {((config.dph - 1) * 100).toFixed(0)}%</li>
            <li>Sluzba obchodu: {config.poplatky?.komodita_sluzba},-Kc bez DPH/kWh</li>
            <li>POZE: {config.poplatky?.poze},-Kc vc DPH/kWh</li>
            <li>Dan: {config.poplatky?.dan},-Kc vc DPH/kWh</li>
            <li>Distribuce NT: {config.poplatky?.distribuce?.NT},-Kc vc DPH/kWh</li>
            <li>Distribuce VT: {config.poplatky?.distribuce?.VT},-Kc vc DPH/kWh</li>
          </ul>

        </div>
      )}

      <footer className="footer">
        <div>(c) {new Date().getFullYear()} mondychan <a href="https://github.com/mondychan" target="_blank" rel="noopener noreferrer">github</a></div>
        <div>Aktualni cas: {currentTime.toLocaleString("cs-CZ")}</div>
        <div>
          Zdroj dat: <a href="https://spotovaelektrina.cz/" target="_blank" rel="noopener noreferrer">spotovaelektrina.cz</a>
        </div>
      </footer>
    </div>
  );

}

export default App;
