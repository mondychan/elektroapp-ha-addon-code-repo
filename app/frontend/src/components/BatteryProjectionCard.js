import React, { useMemo } from "react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  BarChart,
  Bar,
  ReferenceLine,
} from "recharts";

const formatIsoToTime = (iso) => {
  if (!iso) return "-";
  const dt = new Date(iso);
  if (Number.isNaN(dt.getTime())) return "-";
  return `${String(dt.getHours()).padStart(2, "0")}:${String(dt.getMinutes()).padStart(2, "0")}`;
};

const formatNumber = (value, digits = 1) => {
  if (value == null || Number.isNaN(value)) return "-";
  return Number(value).toFixed(digits);
};

const formatW = (value) => {
  if (value == null || Number.isNaN(value)) return "-";
  const abs = Math.abs(Number(value));
  if (abs >= 1000) return `${(Number(value) / 1000).toFixed(2)} kW`;
  return `${Math.round(Number(value))} W`;
};

const formatKwh = (value, digits = 2) => {
  if (value == null || Number.isNaN(value)) return "-";
  return `${Number(value).toFixed(digits)} kWh`;
};

const formatEta = (iso) => {
  if (!iso) return null;
  const dt = new Date(iso);
  if (Number.isNaN(dt.getTime())) return null;
  return dt.toLocaleTimeString("cs-CZ", { hour: "2-digit", minute: "2-digit" });
};

const formatDurationMins = (minutes) => {
  if (minutes == null || !Number.isFinite(minutes)) return null;
  if (minutes < 60) return `${minutes} min`;
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  if (!m) return `${h} h`;
  return `${h} h ${m} min`;
};

const BatteryProjectionCard = ({ batteryData, batteryLoading, batteryError, onRefresh }) => {
  const chartData = useMemo(() => {
    const map = new Map();
    const historyPoints = batteryData?.history?.points || [];
    const projectionPoints = batteryData?.projection?.points || [];

    historyPoints.forEach((p) => {
      const key = p.time;
      const row = map.get(key) || { time: p.time, timeLabel: formatIsoToTime(p.time) };
      row.soc = p.soc_percent ?? null;
      row.batteryPower = p.battery_power_w ?? null;
      map.set(key, row);
    });

    projectionPoints.forEach((p, idx) => {
      const key = p.time;
      const row = map.get(key) || { time: p.time, timeLabel: formatIsoToTime(p.time) };
      row.socProjected = p.soc_percent ?? null;
      if (idx === 0 && row.soc == null) {
        row.soc = p.soc_percent ?? null;
      }
      map.set(key, row);
    });

    return [...map.values()].sort((a, b) => new Date(a.time) - new Date(b.time));
  }, [batteryData]);

  const status = batteryData?.status || null;
  const currentEnergy = batteryData?.current_energy || {};
  const forecast = batteryData?.forecast_solar || {};
  const projection = batteryData?.projection;

  const etaMessage = useMemo(() => {
    if (!batteryData?.is_today || !status) return null;
    if (projection?.state === "charging" && projection?.eta_to_full_at) {
      const etaTime = formatEta(projection.eta_to_full_at);
      const duration = formatDurationMins(projection.eta_to_full_minutes);
      return etaTime ? `Baterie bude nabita cca v ${etaTime}${duration ? ` (${duration})` : ""}.` : null;
    }
    if (projection?.state === "discharging" && projection?.eta_to_reserve_at) {
      const etaTime = formatEta(projection.eta_to_reserve_at);
      const duration = formatDurationMins(projection.eta_to_reserve_minutes);
      return etaTime ? `Baterie vydrzi cca do ${etaTime}${duration ? ` (${duration})` : ""}.` : null;
    }
    if (status?.battery_state === "idle") {
      return "Baterie je zhruba ve stabilnim stavu (vykon pod prahem pro ETA).";
    }
    return "ETA neni k dispozici (chybi trend nebo data).";
  }, [batteryData, projection, status]);

  if (batteryError) {
    return (
      <div className="card card-spaced-lg">
        <div className="card-header">
          <h3>Baterie a projekce</h3>
          <button onClick={onRefresh} disabled={batteryLoading}>
            {batteryLoading ? "Obnovuji..." : "Obnovit"}
          </button>
        </div>
        <div className="alert error">{batteryError}</div>
      </div>
    );
  }

  if (!batteryData) {
    return (
      <div className="card card-spaced-lg">
        <div className="card-header">
          <h3>Baterie a projekce</h3>
          <button onClick={onRefresh} disabled={batteryLoading}>
            {batteryLoading ? "Obnovuji..." : "Nacist"}
          </button>
        </div>
        <div className="muted-note">{batteryLoading ? "Nacitam data..." : "Data zatim nejsou nactena."}</div>
      </div>
    );
  }

  if (!batteryData.enabled || !batteryData.configured) {
    return (
      <div className="card card-spaced-lg">
        <div className="card-header">
          <h3>Baterie a projekce</h3>
          <button onClick={onRefresh} disabled={batteryLoading}>
            {batteryLoading ? "Obnovuji..." : "Obnovit"}
          </button>
        </div>
        <div className="muted-note">{batteryData.detail || "Funkce baterie neni nakonfigurovana."}</div>
      </div>
    );
  }

  return (
    <div className="card card-spaced-lg">
      <div className="card-header">
        <h3>Baterie a projekce {batteryData.is_today ? "(dnes)" : `(${batteryData.date})`}</h3>
        <button onClick={onRefresh} disabled={batteryLoading}>
          {batteryLoading ? "Obnovuji..." : "Obnovit"}
        </button>
      </div>

      <div className="battery-kpi-grid">
        <div className="battery-kpi">
          <div className="battery-kpi-label">SoC</div>
          <div className="battery-kpi-value">{formatNumber(status?.soc_percent, 1)} %</div>
        </div>
        <div className="battery-kpi">
          <div className="battery-kpi-label">Energie v baterii</div>
          <div className="battery-kpi-value">{formatKwh(status?.stored_kwh)}</div>
        </div>
        <div className="battery-kpi">
          <div className="battery-kpi-label">Tok baterie</div>
          <div className="battery-kpi-value">{formatW(status?.battery_power_w)}</div>
        </div>
        <div className="battery-kpi">
          <div className="battery-kpi-label">Stav</div>
          <div className="battery-kpi-value battery-kpi-state">{status?.battery_state || "-"}</div>
        </div>
        <div className="battery-kpi">
          <div className="battery-kpi-label">Do rezervy ({formatNumber(status?.reserve_soc_percent, 0)} %)</div>
          <div className="battery-kpi-value">{formatKwh(status?.available_to_reserve_kwh)}</div>
        </div>
        <div className="battery-kpi">
          <div className="battery-kpi-label">Do plna</div>
          <div className="battery-kpi-value">{formatKwh(status?.remaining_to_full_kwh)}</div>
        </div>
      </div>

      <div className="summary">{etaMessage}</div>
      <div className="muted-note">
        Model: {projection?.method || "-"} / confidence: {projection?.confidence || "-"}.
        {" "}
        {projection?.method === "hybrid_forecast_load_profile"
          ? "Projekce kombinuje Forecast.Solar a historicky profil spotreby/PV."
          : `Odhad podle trendu baterioveho vykonu za poslednich ${status?.eta_smoothing_minutes ?? "-"} minut.`}
      </div>

      {!chartData.length ? (
        <div className="muted-note">Historie baterie neni k dispozici.</div>
      ) : (
        <div className="cost-stack">
          <ResponsiveContainer width="100%" height={230}>
            <LineChart data={chartData} margin={{ top: 10, right: 20, left: 30, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="timeLabel" tick={false} />
              <YAxis
                domain={[0, 100]}
                tick={{ fill: "var(--text-muted)" }}
                label={{ value: "SoC %", angle: -90, position: "insideLeft" }}
              />
              <Tooltip
                contentStyle={{ background: "var(--panel)", borderColor: "var(--border)", color: "var(--text)" }}
                itemStyle={{ color: "var(--text)" }}
                labelStyle={{ color: "var(--text)" }}
                labelFormatter={(_, payload) => (payload?.[0]?.payload?.timeLabel ? `Cas: ${payload[0].payload.timeLabel}` : "Cas: -")}
                formatter={(value, name) => {
                  if (name === "SoC") return [`${Number(value).toFixed(1)} %`, "SoC"];
                  if (name === "Projekce SoC") return [`${Number(value).toFixed(1)} %`, "Projekce SoC"];
                  return [value, name];
                }}
              />
              <Line type="monotone" dataKey="soc" name="SoC" stroke="var(--accent-2)" strokeWidth={2} dot={false} />
              <Line
                type="monotone"
                dataKey="socProjected"
                name="Projekce SoC"
                stroke="var(--accent)"
                strokeWidth={2}
                strokeDasharray="5 4"
                dot={false}
                connectNulls={false}
              />
            </LineChart>
          </ResponsiveContainer>

          <ResponsiveContainer width="100%" height={170}>
            <BarChart data={chartData} margin={{ top: 0, right: 20, left: 30, bottom: 10 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="timeLabel" tick={{ fill: "var(--text-muted)" }} />
              <YAxis
                tick={{ fill: "var(--text-muted)" }}
                label={{ value: "W", angle: -90, position: "insideLeft" }}
              />
              <Tooltip
                contentStyle={{ background: "var(--panel)", borderColor: "var(--border)", color: "var(--text)" }}
                itemStyle={{ color: "var(--text)" }}
                labelStyle={{ color: "var(--text)" }}
                labelFormatter={(_, payload) => (payload?.[0]?.payload?.timeLabel ? `Cas: ${payload[0].payload.timeLabel}` : "Cas: -")}
                formatter={(value) => [formatW(value), "Vykon baterie"]}
              />
              <ReferenceLine y={0} stroke="var(--border)" />
              <Bar dataKey="batteryPower" fill="var(--accent-2)" barSize={5} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      <div className="battery-meta-grid">
        <div className="battery-meta-block">
          <h4>Aktualni energie</h4>
          <div className="battery-meta-list">
            <div>PV: {formatW(currentEnergy.pv_power_total_w)}</div>
            <div>House load: {formatW(currentEnergy.house_load_w)}</div>
            <div>Grid import: {formatW(currentEnergy.grid_import_w)}</div>
            <div>Grid export: {formatW(currentEnergy.grid_export_w)}</div>
            <div>Nabito dnes: {formatKwh(currentEnergy.battery_input_today_kwh, 2)}</div>
            <div>Vybito dnes: {formatKwh(currentEnergy.battery_output_today_kwh, 2)}</div>
          </div>
        </div>

        <div className="battery-meta-block">
          <h4>Forecast Solar</h4>
          {!forecast?.enabled ? (
            <div className="config-muted">Forecast Solar je vypnuty v konfiguraci.</div>
          ) : !forecast?.available ? (
            <div className="config-muted">Forecast data nejsou k dispozici.</div>
          ) : (
            <div className="battery-meta-list">
              <div>Vyroba ted: {formatW(forecast.power_now_w)}</div>
              <div>Tato hodina: {formatKwh(forecast.energy_current_hour_kwh, 2)}</div>
              <div>Pristi hodina: {formatKwh(forecast.energy_next_hour_kwh, 2)}</div>
              <div>Zbyva dnes: {formatKwh(forecast.energy_production_today_remaining_kwh, 2)}</div>
              <div>Dnes celkem: {formatKwh(forecast.energy_production_today_kwh, 2)}</div>
              <div>Zitra celkem: {formatKwh(forecast.energy_production_tomorrow_kwh, 2)}</div>
              <div>Peak dnes: {forecast.peak_time_today_hhmm || "-"}</div>
              <div>Peak zitra: {forecast.peak_time_tomorrow_hhmm || "-"}</div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default BatteryProjectionCard;
