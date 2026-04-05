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
  battery?: {
    enabled?: boolean;
    usable_capacity_kwh?: number;
    reserve_soc_percent?: number;
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
    state: "charging" | "discharging" | "idle";
    eta_to_full_at?: string;
    eta_to_full_minutes?: number;
    eta_to_reserve_at?: string;
    eta_to_reserve_minutes?: number;
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
  power_now?: number;
  energy_production_today_remaining?: number;
  energy_production_tomorrow?: number;
  power_highest_peak_time_today?: string;
  power_highest_peak_time_tomorrow?: string;
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
}
