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

  const intensityChartData = useMemo(() => {
    const centerPosition = state.auto_mode ? verticalLinePosition : 4320
    const annotationColor = theme === "dark" ? "#E6E6E6" : "#34C759"
    return {
      datasets: [
        {
          label: "scene intensity",
          data: sceneData.intensity.map((y, i) => ({ x: i * (8640 / sceneData.intensity.length), y })),
          borderColor: theme === "dark" ? "#ffa94d" : "#FF9500",
          backgroundColor: (context) => {
            const ctx = context.chart.ctx
            const gradient = ctx.createLinearGradient(0, 0, 0, 500)
            if (theme === "dark") {
              gradient.addColorStop(0, "rgba(255, 169, 77, 0.3)")
              gradient.addColorStop(1, "rgba(255, 169, 77, 0.05)")
            } else {
              gradient.addColorStop(0, "rgba(255, 149, 0, 0.25)")
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
          label: "current intensity",
          data: state.current_intensity ? (state.auto_mode ? [{ x: centerPosition, y: state.current_intensity }] : [{ x: 0, y: state.current_intensity }, { x: 8640, y: state.current_intensity }]) : [],
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
  }, [sceneData.intensity, state.isSystemOn, state.current_intensity, theme, verticalLinePosition, state.auto_mode])

  const chartOptions = useMemo(() => ({
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      plotAreaBackground: plotAreaBackgroundPlugin,
      currentValueLabel: { text: `Current CCT: ${state.current_cct.toFixed(1)}K` },
      title: { display: true, text: "CCT PROFILE", color: theme === "dark" ? "#E6E6E6" : "#1A1A1A", font: { family: "SF Pro Display, system-ui, sans-serif", size: 18, weight: "600" }, padding: { bottom: 12, top: 8 } },
      legend: { display: false },
      annotation: { annotations: { verticalLine: { type: "line", xMin: verticalLinePosition, xMax: verticalLinePosition, borderColor: theme === "dark" ? "rgba(255, 69, 58, 0.7)" : "#FF3B30", borderWidth: 2 } } },
      tooltip: {
        backgroundColor: theme === "dark" ? "rgba(35, 47, 62, 0.95)" : "rgba(255, 255, 255, 0.95)",
        titleColor: theme === "dark" ? "#E6E6E6" : "#1A1A1A",
        bodyColor: theme === "dark" ? "#A3A3A3" : "#666666",
        borderColor: theme === "dark" ? "#4B5563" : "#E2E8F0",
        borderWidth: 1,
        cornerRadius: 8,
        padding: 10,
        callbacks: {
          title: (tooltipItems) => {
            const value = tooltipItems[0].parsed.x
            const totalMinutes = Math.floor((value * 10) / 60)
            const hours = Math.floor(totalMinutes / 60) % 24
            const minutes = totalMinutes % 60
            if (value === 8640) {
              return "24:00"
            }
            return `${hours % 24}:${minutes.toString().padStart(2, "0")}`
          },
          label: (context) => {
            const label = context.dataset.label || ""
            const value = context.parsed.y
            if (label.includes("CCT") || label.includes("cct")) {
              return `${label}: ${value.toFixed(1)}K`
            } else if (label.includes("intensity") || label.includes("Intensity")) {
              return `${label}: ${value.toFixed(1)} lux`
            }
            return `${label}: ${value}`
          },
        },
      },
    },
    scales: {
      x: {
        type: "linear",
        min: 0,
        max: 8640,
        title: {
          display: true,
          text: "Time (Hours)",
          color: theme === "dark" ? "#A3A3A3" : "#666666",
          font: { family: "SF Pro Display, system-ui, sans-serif", size: 14, weight: "500" },
          padding: { top: 8 },
        },
        ticks: {
          stepSize: 720,
          autoSkip: false,
          maxRotation: 0,
          font: { family: "SF Pro Display, system-ui, sans-serif", size: 12 },
          color: theme === "dark" ? "#A3A3A3" : "#8A8A8A",
          callback: (value) => {
            const totalMinutes = (value * 10) / 60
            const hours = Math.floor(totalMinutes / 60) % 24
            return `${hours}h`
          },
        },
        grid: {
          color: theme === "dark" ? "rgba(75, 85, 99, 0.2)" : "rgba(226, 232, 240, 0.4)",
          lineWidth: 0.5,
        },
      },
      y: { 
        min: 2000, 
        max: 7000, 
        title: { 
          display: true, 
          text: "CCT (K)", 
          color: theme === "dark" ? "#A3A3A3" : "#666666", 
          font: { family: "SF Pro Display, system-ui, sans-serif", size: 14, weight: "500" }, 
          padding: { bottom: 8 } 
        }, 
        ticks: { 
          stepSize: 500, 
          color: theme === "dark" ? "#A3A3A3" : "#8A8A8A", 
          font: { family: "SF Pro Display, system-ui, sans-serif", size: 12 } 
        }, 
        grid: { 
          color: theme === "dark" ? "rgba(75, 85, 99, 0.2)" : "rgba(226, 232, 240, 0.4)", 
          lineWidth: 0.5 
        } 
      }
    },
  }), [theme, verticalLinePosition, state.auto_mode, state.isSystemOn, state.current_cct])

  const intensityChartOptions = useMemo(() => ({
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      plotAreaBackground: plotAreaBackgroundPlugin,
      currentValueLabel: { text: `Current Intensity: ${state.current_intensity.toFixed(1)} lux` },
      title: { display: true, text: "INTENSITY PROFILE", color: theme === "dark" ? "#E6E6E6" : "#1A1A1A", font: { family: "SF Pro Display, system-ui, sans-serif", size: 18, weight: "600" }, padding: { bottom: 12, top: 8 } },
      legend: { display: false },
      annotation: { annotations: { verticalLine: { type: "line", xMin: verticalLinePosition, xMax: verticalLinePosition, borderColor: theme === "dark" ? "rgba(255, 69, 58, 0.7)" : "#FF3B30", borderWidth: 2 } } },
      tooltip: {
        backgroundColor: theme === "dark" ? "rgba(35, 47, 62, 0.95)" : "rgba(255, 255, 255, 0.95)",
        titleColor: theme === "dark" ? "#E6E6E6" : "#1A1A1A",
        bodyColor: theme === "dark" ? "#A3A3A3" : "#666666",
        borderColor: theme === "dark" ? "#4B5563" : "#E2E8F0",
        borderWidth: 1,
        cornerRadius: 8,
        padding: 10,
        callbacks: {
          title: (tooltipItems) => {
            const value = tooltipItems[0].parsed.x
            const totalMinutes = Math.floor((value * 10) / 60)
            const hours = Math.floor(totalMinutes / 60) % 24
            const minutes = totalMinutes % 60
            if (value === 8640) {
              return "24:00"
            }
            return `${hours % 24}:${minutes.toString().padStart(2, "0")}`
          },
          label: (context) => {
            const label = context.dataset.label || ""
            const value = context.parsed.y
            if (label.includes("CCT") || label.includes("cct")) {
              return `${label}: ${value.toFixed(1)}K`
            } else if (label.includes("intensity") || label.includes("Intensity")) {
              return `${label}: ${value.toFixed(1)} lux`
            }
            return `${label}: ${value}`
          },
        },
      },
    },
    scales: {
      x: {
        type: "linear",
        min: 0,
        max: 8640,
        title: {
          display: true,
          text: "Time (Hours)",
          color: theme === "dark" ? "#A3A3A3" : "#666666",
          font: { family: "SF Pro Display, system-ui, sans-serif", size: 14, weight: "500" },
          padding: { top: 8 },
        },
        ticks: {
          stepSize: 720,
          autoSkip: false,
          maxRotation: 0,
          font: { family: "SF Pro Display, system-ui, sans-serif", size: 12 },
          color: theme === "dark" ? "#A3A3A3" : "#8A8A8A",
          callback: (value) => {
            const totalMinutes = (value * 10) / 60
            const hours = Math.floor(totalMinutes / 60) % 24
            return `${hours}h`
          },
        },
        grid: {
          color: theme === "dark" ? "rgba(75, 85, 99, 0.2)" : "rgba(226, 232, 240, 0.4)",
          lineWidth: 0.5,
        },
      },
      y: { 
        min: 0, 
        max: 1000, 
        title: { 
          display: true, 
          text: "Intensity (lux)", 
          color: theme === "dark" ? "#A3A3A3" : "#666666", 
          font: { family: "SF Pro Display, system-ui, sans-serif", size: 14, weight: "500" }, 
          padding: { bottom: 8 } 
        }, 
        ticks: { 
          stepSize: 100, 
          color: theme === "dark" ? "#A3A3A3" : "#8A8A8A", 
          font: { family: "SF Pro Display, system-ui, sans-serif", size: 12 } 
        }, 
        grid: { 
          color: theme === "dark" ? "rgba(75, 85, 99, 0.2)" : "rgba(226, 232, 240, 0.4)", 
          lineWidth: 0.5 
        } 
      }
    },
  }), [theme, verticalLinePosition, state.auto_mode, state.isSystemOn, state.current_intensity])

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