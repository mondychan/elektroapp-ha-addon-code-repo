import { formatSlotToTime } from "../../utils/formatters";
import { buildCurrentSlotAnnotations } from "../plugins/currentSlotPlugin";
import { buildTimeBandAnnotations } from "../plugins/timeBandPlugin";
import { buildThresholdAnnotations } from "../plugins/thresholdPlugin";
import { buildCategoryTimeAxis, buildLinearAxis, buildStaticTimeLabels, buildTooltip, colorScale } from "./common";

const getVTStatus = (slot, vtPeriods) =>
  (vtPeriods || []).some(([start, end]) => slot >= start * 4 && slot < end * 4) ? "VT" : "NT";

const buildVtBands = (vtPeriods = []) =>
  vtPeriods.map(([start, end]) => ({
    startSlot: start * 4 - 0.5,
    endSlot: end * 4 - 0.5,
    tone: "vt",
  }));

export const buildPriceChartConfig = ({
  chartData,
  title,
  vtPeriods,
  highlightSlot,
  pinnedSlot,
  fallbackMessage,
  thresholds = null,
}) => {
  if (!chartData?.length) {
    return {
      emptyMessage: fallbackMessage,
      pointPayloads: [],
    };
  }

  const minFinal = Math.min(...chartData.map((item) => item.final));
  const maxFinal = Math.max(...chartData.map((item) => item.final));
  const activeSlot = Number.isInteger(pinnedSlot) ? pinnedSlot : highlightSlot;

  const dataFixni = [];
  const dataOdecteno = [];
  const dataVariabilni = [];
  const bgColorsVariabilni = [];

  chartData.forEach((item) => {
    let fixni = null;
    let odecteno = null;
    let variabilni = null;

    if (item.spot < 0) {
      const finalPrice = item.extra + item.spot;
      if (finalPrice >= 0) {
        // Záporná cena jen snižuje fixní složku
        fixni = finalPrice > 0 ? Number(finalPrice.toFixed(4)) : null;
        odecteno = Math.abs(item.spot) > 0 ? Number(Math.abs(item.spot).toFixed(4)) : null;
      } else {
        // Záporná cena pokryla celou fixní složku a zbytek jde pod nulu
        odecteno = item.extra > 0 ? Number(item.extra.toFixed(4)) : null;
        variabilni = finalPrice < 0 ? Number(finalPrice.toFixed(4)) : null;
      }
    } else {
      // Normální stav
      fixni = item.extra > 0 ? Number(item.extra.toFixed(4)) : null;
      variabilni = item.spot > 0 ? Number(item.spot.toFixed(4)) : null;
      
      if (item.extra === 0 && item.spot === 0) {
        fixni = 0;
      }
    }

    dataFixni.push(fixni);
    dataOdecteno.push(odecteno);
    dataVariabilni.push(variabilni);
    bgColorsVariabilni.push(colorScale(item.final, minFinal, maxFinal));
  });

  const datasets = [
    {
      type: "bar",
      label: "Fixní složka",
      data: dataFixni,
      backgroundColor: "rgba(45, 127, 249, 0.88)",
      borderRadius: 7,
      borderSkipped: false,
      stack: "price",
      barPercentage: 0.92,
      categoryPercentage: 1,
    },
    {
      type: "bar",
      label: "Pokryto zápornou cenou",
      data: dataOdecteno,
      backgroundColor: "rgba(45, 127, 249, 0.12)",
      borderColor: "rgba(45, 127, 249, 0.6)",
      borderWidth: 1.5,
      borderDash: [4, 4],
      borderRadius: 7,
      borderSkipped: false,
      stack: "price",
      barPercentage: 0.92,
      categoryPercentage: 1,
    },
    {
      type: "bar",
      label: "Variabilní složka",
      data: dataVariabilni,
      backgroundColor: bgColorsVariabilni,
      borderRadius: 7,
      borderSkipped: false,
      stack: "price",
      barPercentage: 0.92,
      categoryPercentage: 1,
    },
  ];

  return {
    title,
    pointPayloads: chartData,
    data: {
      labels: buildStaticTimeLabels(chartData),
      datasets,
    },
    options: {
      interaction: {
        mode: "index",
        intersect: false,
      },
      scales: {
        x: {
          ...buildCategoryTimeAxis({
            tickColor: (ctx) => (getVTStatus(ctx.tick.value, vtPeriods) === "VT" ? "#c7392f" : "#2f8f49"),
          }),
          stacked: true,
        },
        y: {
          ...buildLinearAxis({ title: "Cena" }),
          stacked: true,
          ticks: {
            callback: (value) => `${Number(value).toFixed(2)},-Kč`,
          },
        },
      },
      plugins: {
        legend: {
          labels: {
            filter: (item) => {
              // Hide empty legend items optionally, but we want all 3 to show.
              return true;
            }
          },
        },
        tooltip: buildTooltip(({ points }) => {
          const point = chartData[points?.[0]?.dataIndex] || null;
          if (!point) {
            return null;
          }
          
          const sections = [
            { label: "Fixní složka", value: `${point.extra.toFixed(2)},-Kč`, color: "rgba(45, 127, 249, 0.88)" }
          ];

          if (point.spot < 0) {
            sections.push({ label: "Záporná var. složka", value: `${point.spot.toFixed(2)},-Kč`, color: "rgba(45, 127, 249, 0.6)" });
          } else {
            sections.push({ label: "Variabilní složka", value: `${point.spot.toFixed(2)},-Kč`, color: "rgba(255, 122, 89, 0.84)" });
          }

          sections.push({ label: "Konečná cena", value: `${point.final.toFixed(2)},-Kč`, color: "rgba(255, 255, 255, 0.92)" });

          return {
            title: `${formatSlotToTime(point.slot)} (${getVTStatus(point.slot, vtPeriods)})`,
            sections,
          };
        }),
        annotation: {
          annotations: {
            ...buildTimeBandAnnotations(buildVtBands(vtPeriods)),
            ...buildCurrentSlotAnnotations({ slot: activeSlot }),
            ...(thresholds ? buildThresholdAnnotations({ 
              minThreshold: thresholds.min_price_today, 
              maxThreshold: thresholds.max_price_today 
            }) : {}),
          },
        },
      },
    },
  };
};
