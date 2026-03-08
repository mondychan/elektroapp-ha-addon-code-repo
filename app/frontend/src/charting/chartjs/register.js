import {
  BarController,
  BarElement,
  CategoryScale,
  Chart as ChartJS,
  Filler,
  Legend,
  LineController,
  LineElement,
  LinearScale,
  PointElement,
  Tooltip,
  Title,
} from "chart.js";
import annotationPlugin from "chartjs-plugin-annotation";
import { MatrixController, MatrixElement } from "chartjs-chart-matrix";
import { emptyStateOverlayPlugin } from "../plugins/emptyStateOverlayPlugin";

let isRegistered = false;

export const ensureChartJsRegistered = () => {
  if (isRegistered) {
    return ChartJS;
  }

  ChartJS.register(
    BarController,
    LineController,
    CategoryScale,
    LinearScale,
    BarElement,
    LineElement,
    PointElement,
    MatrixController,
    MatrixElement,
    Tooltip,
    Legend,
    Title,
    Filler,
    annotationPlugin,
    emptyStateOverlayPlugin
  );

  isRegistered = true;
  return ChartJS;
};

