import { Line } from "react-chartjs-2"
import { FaSyncAlt } from "react-icons/fa"
import { useMemo } from "react"
import { currentValueLabelPlugin, plotAreaBackgroundPlugin } from "../utils/plugins"

const Charts = ({ isLoading, theme, state, sceneData, verticalLinePosition }) => {
  const chartData = useMemo(() => {
    const centerPosition = state.auto_mode ? verticalLinePosition : 4320
    const annotationColor = theme === "dark" ? "#E6E6E6" : "#34C759"
    return {
      datasets: [
        {
          label: "scene CCT",
          data: sceneData.cct.map((y, i) => ({ x: i * (8640 / sceneData.cct.length), y })),
          borderColor: theme === "dark" ? "#4dabf7" : "#0071E3",
          backgroundColor: (context) => {
            const ctx = context.chart.ctx
            const gradient = ctx.createLinearGradient(0, 0, 0, 1000)
            if (theme === "dark") {
              gradient.addColorStop(0, "rgba(77, 171, 247, 0.3)")
              gradient.addColorStop(1, "rgba(77, 171, 247, 0.05)")
            } else {
              gradient.addColorStop(0, "rgba(0, 113, 227, 0.25)")
              gradient.addColorStop(1, "rgba(0, 113, 227, 0.05)")
            }
            return gradient
          },
          fill: true,
          tension: 0.4,
          borderWidth: 2.5,
          pointRadius: 0,
          pointHoverRadius: 0,
        },
        ...(state.isSystemOn ? [{
          label: "current CCT",
          data: state.current_cct ? (state.auto_mode ? [{ x: centerPosition, y: state.current_cct }] : [{ x: 0, y: state.current_cct }, { x: 8640, y: state.current_cct }]) : [],
          borderColor: annotationColor,
          backgroundColor: annotationColor,
          pointStyle: state.auto_mode ? "circle" : false,
          pointRadius: state.auto_mode ? 7 : 0,
          pointHoverRadius: state.auto_mode ? 9 : 0,
          showLine: !state.auto_mode,
          borderWidth: state.auto_mode ? 0 : 2,
          tension: 0,
        }] : []),
      ],
    }
  }, [sceneData.cct, state.isSystemOn, state.current_cct, theme, verticalLinePosition, state.auto_mode])

  const intensityChartData = useMemo(() => { /* similar to chartData */ }, [sceneData.intensity, state.isSystemOn, state.current_intensity, theme, verticalLinePosition, state.auto_mode])

  const chartOptions = useMemo(() => ({
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      plotAreaBackground: plotAreaBackgroundPlugin,
      currentValueLabel: { text: `Current CCT: ${state.current_cct.toFixed(1)}K` },
      title: { display: true, text: "CCT PROFILE", color: theme === "dark" ? "#E6E6E6" : "#1A1A1A", font: { family: "SF Pro Display, system-ui, sans-serif", size: 18, weight: "600" }, padding: { bottom: 12, top: 8 } },
      legend: { display: false },
      annotation: { annotations: { verticalLine: { type: "line", xMin: verticalLinePosition, xMax: verticalLinePosition, borderColor: theme === "dark" ? "rgba(255, 69, 58, 0.7)" : "#FF3B30", borderWidth: 2 } } },
      tooltip: { /* unchanged */ },
    },
    scales: { x: { /* unchanged */ }, y: { min: 2000, max: 7000, title: { display: true, text: "CCT (K)", color: theme === "dark" ? "#A3A3A3" : "#666666", font: { family: "SF Pro Display, system-ui, sans-serif", size: 14, weight: "500" }, padding: { bottom: 8 } }, ticks: { stepSize: 500, color: theme === "dark" ? "#A3A3A3" : "#8A8A8A", font: { family: "SF Pro Display, system-ui, sans-serif", size: 12 } }, grid: { color: theme === "dark" ? "rgba(75, 85, 99, 0.2)" : "rgba(226, 232, 240, 0.4)", lineWidth: 0.5 } } },
  }), [theme, verticalLinePosition, state.auto_mode, state.isSystemOn, state.current_cct])

  const intensityChartOptions = useMemo(() => { /* similar to chartOptions */ }, [theme, verticalLinePosition, state.auto_mode, state.isSystemOn, state.current_intensity])

  return (
    <section className="charts-container">
      <div className="chart-card">
        {isLoading && <div className="loading-overlay"><FaSyncAlt className="loading-spinner" /></div>}
        <Line data={chartData} options={chartOptions} />
      </div>
      <div className="chart-card">
        {isLoading && <div className="loading-overlay"><FaSyncAlt className="loading-spinner" /></div>}
        <Line data={intensityChartData} options={intensityChartOptions} />
      </div>
    </section>
  )
}

export default Charts