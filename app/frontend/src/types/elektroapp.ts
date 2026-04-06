export interface Config {
  dph: number;
  price_provider: "ote" | "spotovaelektrina.cz";
  poplatky?: {
    komodita_sluzba?: number;
    oze?: number;
    dan?: number;
    systemove_sluzby?: number;
    distribuce?: {
      NT?: number;
      VT?: number;
    };
  };
  fixni?: {
    denni?: {
      staly_plat?: number;
    };
    mesicni?: {
      provoz_nesitove_infrastruktury?: number;
      jistic?: number;
    };
  };
  tarif?: {
    vt_periods?: any;
  };
  prodej?: {
    koeficient_snizeni_ceny?: number;
  };
  influxdb?: {
    entity_id?: string;
    export_entity_id?: string;
  };
  battery?: {
    enabled?: boolean;
    usable_capacity_kwh?: number;
    reserve_soc_percent?: number;
    soc_entity_id?: string;
  };
  energy?: {
    house_load_power_entity_id?: string;
    grid_import_power_entity_id?: string;
    grid_export_power_entity_id?: string;
    pv_power_total_entity_id?: string;
  };
  forecast_solar?: {
    enabled?: boolean;
    power_now_entity_id?: string;
    power_next_hour_entity_id?: string;
    power_next_12hours_entity_id?: string;
    power_next_24hours_entity_id?: string;
  };
  pnd?: {
    enabled?: boolean;
    username?: string;
    password?: string;
    meter_id?: string;
    verify_on_startup?: boolean;
    nightly_sync_enabled?: boolean;
    nightly_sync_window_start_hour?: number;
    nightly_sync_window_end_hour?: number;
  };
}

export interface PriceItem {
  slot: number;
  time: string;
  spot: number;
  extra: number;
  final: number;
  rawSpot: number;
}

export interface BatteryData {
  status?: {
    soc_percent?: number;
    battery_power_w?: number;
  };
  projection?: {
    state: "charging" | "discharging" | "idle" | "unknown";
    end_state?: "charging" | "discharging" | "idle" | "unknown";
    eta_to_full_at?: string;
    eta_to_full_minutes?: number;
    eta_to_reserve_at?: string;
    eta_to_reserve_minutes?: number;
    eta_to_reserve_after_full_at?: string;
    eta_to_reserve_after_full_minutes?: number;
    peak_soc_percent?: number;
    peak_soc_at?: string;
    min_soc_percent?: number;
    min_soc_at?: string;
    projected_end_soc_percent?: number;
    first_transition_at?: string;
    first_transition_state?: "charging" | "discharging" | "idle";
  };
  is_today?: boolean;
}

export interface CostsKpi {
  cost_total?: number;
  kwh_total?: number;
}

export interface ExportKpi {
  sell_total?: number;
  export_kwh_total?: number;
}

export interface SolarForecast {
  enabled?: boolean;
  date?: string;
  status?: {
    power_now?: number | null;
    power_now_w?: number | null;
    power_next_hour?: number | null;
    power_next_12hours?: number | null;
    power_next_24hours?: number | null;
    power_production_next_hour_w?: number | null;
    power_production_next_12hours_w?: number | null;
    power_production_next_24hours_w?: number | null;
    power_production_next_12hours_w_by_hour?: Array<number | null>;
    power_production_next_24hours_w_by_hour?: Array<number | null>;
    energy_current_hour?: number | null;
    energy_current_hour_kwh?: number | null;
    energy_next_hour?: number | null;
    energy_next_hour_kwh?: number | null;
    production_today?: number | null;
    energy_production_today_kwh?: number | null;
    production_today_remaining?: number | null;
    energy_production_today_remaining_kwh?: number | null;
    production_tomorrow?: number | null;
    energy_production_tomorrow_kwh?: number | null;
    peak_today?: string | null;
    peak_time_today_hhmm?: string | null;
    peak_tomorrow?: string | null;
    peak_time_tomorrow_hhmm?: string | null;
  };
  actual?: {
    pv_power_entity_id?: string | null;
    power_now_w?: number | null;
    production_today_kwh?: number | null;
    samples_today?: number | null;
  };
  comparison?: {
    model_version?: string | null;
    forecast_so_far_kwh?: number | null;
    delta_so_far_kwh?: number | null;
    power_delta_w?: number | null;
    live_ratio?: number | null;
    historical_bias_ratio?: number | null;
    remaining_hourly_bias_ratio?: number | null;
    effective_bias_ratio?: number | null;
    adjusted_projection_today_kwh?: number | null;
    projection_delta_to_forecast_kwh?: number | null;
    adjusted_projection_tomorrow_kwh?: number | null;
    projection_delta_to_forecast_tomorrow_kwh?: number | null;
    adjusted_current_hour_kwh?: number | null;
    adjusted_next_hour_kwh?: number | null;
    adjusted_today_hourly_profile_kwh_by_hour?: Array<number | null>;
    adjusted_tomorrow_hourly_profile_kwh_by_hour?: Array<number | null>;
    future_profile_source?: string | null;
  };
  history?: {
    days_tracked?: number;
    cache_days?: number;
    hourly_slots_tracked?: number;
    median_ratio?: number | null;
    avg_ratio?: number | null;
    last_completed_date?: string | null;
    profile_sources_available?: {
      historical_hourly?: boolean;
      live_next_hour?: boolean;
      live_next_12hours?: boolean;
      live_next_24hours?: boolean;
    };
    recent_days?: Array<{
      date: string;
      actual_total_kwh: number;
      forecast_total_kwh: number;
      ratio: number;
    }>;
  };
}

export interface MonthlyDayData {
  date: string;
  kwh_total: number | null;
  cost_total: number | null;
  export_kwh_total: number | null;
  sell_total: number | null;
  netKwh?: number | null;
  netCost?: number | null;
}

export interface MonthlyTotals {
  kwh_total?: number;
  cost_total?: number;
  export_kwh_total?: number;
  sell_total?: number;
}

export interface DashboardSnapshot {
  config: Config;
  prices: any[];
  selectedDatePrices: any[];
  batteryData: BatteryData;
  todayCostsKpi: CostsKpi;
  todayExportKpi: ExportKpi;
  solarForecast: SolarForecast;
  version: string;
  alerts: any;
  comparison: any;
  solar: any;
}

export interface PndStatus {
  enabled: boolean;
  configured: boolean;
  healthy: boolean;
  state?: string | null;
  state_message?: string | null;
  last_verify_at?: string | null;
  last_sync_at?: string | null;
  last_error?: {
    at?: string;
    code?: string;
    message?: string;
    stage?: string;
    details?: any;
  } | null;
  portal_version?: string | null;
  cached_from?: string | null;
  cached_to?: string | null;
  days_count?: number;
  last_job?: any;
}
