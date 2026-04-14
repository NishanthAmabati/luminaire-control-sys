export const getChartData = (state, type) => {
  const labels = Array.from({ length: 10 }, (_, i) => `T-${9 - i}`)
  const data = Array.from({ length: 10 }, () => Math.random() * (type === "cct" ? 5000 : 800) + (type === "cct" ? 2000 : 200))
  return {
    labels,
    datasets: [
      {
        label: type === "cct" ? "CCT (K)" : "Intensity (lux)",
        data,
        borderColor: type === "cct" ? "var(--cct-color)" : "var(--intensity-color)",
        backgroundColor: type === "cct" ? "var(--cct-gradient-start)" : "var(--intensity-gradient-start)",
        fill: true,
        tension: 0.4,
      },
    ],
  }
}

export const getChartOptions = (title, min, max, unit) => ({
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { display: true, position: "top" },
    title: { display: true, text: title, color: "var(--text-primary)" },
    annotation: {
      annotations: {
        line1: {
          type: "line",
          yMin: min,
          yMax: min,
          borderColor: "var(--accent-color)",
          borderWidth: 2,
        },
      },
    },
  },
  scales: {
    x: { grid: { color: "var(--chart-grid)" } },
    y: {
      min,
      max,
      ticks: { callback: (value) => `${value} ${unit}` },
      grid: { color: "var(--chart-grid)" },
    },
  },
})