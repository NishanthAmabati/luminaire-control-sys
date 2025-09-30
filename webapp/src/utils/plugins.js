export const currentValueLabelPlugin = {
  id: "currentValueLabel",
  afterDraw: (chart, args, options) => {
    const { ctx, chartArea } = chart
    const text = options.text || ""
    const theme = chart.canvas.classList.contains("dark-theme") ? "dark" : "light"
    ctx.save()
    ctx.font = 'bold 14px "SF Pro Display", system-ui, sans-serif'
    const textMetrics = ctx.measureText(text)
    const textWidth = textMetrics.width
    const textHeight = 14
    const paddingX = 12, paddingY = 6
    const boxWidth = Math.max(160, textWidth + paddingX * 2)
    const boxHeight = textHeight + paddingY * 2
    const cornerRadius = 6
    const x = chartArea.right - boxWidth, y = chartArea.top - boxHeight
    ctx.beginPath()
    ctx.moveTo(x + cornerRadius, y)
    ctx.lineTo(x + boxWidth - cornerRadius, y)
    ctx.arcTo(x + boxWidth, y, x + boxWidth, y + cornerRadius, cornerRadius)
    ctx.lineTo(x + boxWidth, y + boxHeight - cornerRadius)
    ctx.arcTo(x + boxWidth, y + boxHeight, x + boxWidth - cornerRadius, y + boxHeight, cornerRadius)
    ctx.lineTo(x + cornerRadius, y + boxHeight)
    ctx.arcTo(x, y + boxHeight, x, y + boxHeight - cornerRadius, cornerRadius)
    ctx.lineTo(x, y + cornerRadius)
    ctx.arcTo(x, y, x + cornerRadius, y, cornerRadius)
    ctx.closePath()
    ctx.fillStyle = theme === "dark" ? "rgba(30, 30, 30, 0.85)" : "rgba(255, 255, 255, 0.85)"
    ctx.shadowColor = "rgba(0, 0, 0, 0.2)"
    ctx.shadowBlur = 8
    ctx.shadowOffsetY = 2
    ctx.fill()
    ctx.shadowColor = "transparent"
    ctx.shadowBlur = 0
    ctx.shadowOffsetY = 0
    ctx.fillStyle = theme === "dark" ? "#E6E6E6" : "#1A1A1A"
    ctx.textAlign = "center"
    ctx.textBaseline = "middle"
    ctx.fillText(text, x + boxWidth / 2, y + boxHeight / 2)
    ctx.restore()
  },
}

export const plotAreaBackgroundPlugin = {
  id: "plotAreaBackground",
  beforeDraw: (chart) => {
    const ctx = chart.ctx
    const { top, left, width, height } = chart.chartArea
    ctx.save()
    if (chart.canvas.classList.contains("dark-theme")) {
      ctx.fillStyle = "rgba(255, 223, 136, 0.05)"
    } else {
      const gradient = ctx.createLinearGradient(left, top, left, top + height)
      gradient.addColorStop(0, "rgba(245, 247, 250, 0.3)")
      gradient.addColorStop(1, "rgba(245, 247, 250, 0.1)")
      ctx.fillStyle = gradient
    }
    ctx.fillRect(left, top, width, height)
    ctx.restore()
  },
}