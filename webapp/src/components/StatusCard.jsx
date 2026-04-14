import { useState, useCallback } from "react"
import { Radio, Cpu, MemoryStick, Thermometer, Clock, Zap, AlertCircle, Sun } from "lucide-react"
import { toast } from "react-hot-toast"

const StatusCard = ({ state, sendCommand, logBasic, setIsLogsPanelOpen, wsLatency, cpu_percent, mem_percent, temperature, system_timers }) => {
  const [onTime, setOnTime] = useState(localStorage.getItem("onTime") || "07:00")
  const [offTime, setOffTime] = useState(localStorage.getItem("offTime") || "22:00")

  const handleSetTimer = useCallback(() => {
    if (!onTime || !offTime) { toast.error("Please set both On and Off times."); return }
    if (onTime === offTime) { toast.error("On and Off times cannot be the same."); return }
    const timeRegex = /^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$/
    if (!timeRegex.test(onTime) || !timeRegex.test(offTime)) { toast.error("Invalid time format. Use HH:MM."); return }
    sendCommand({ type: "set_timer", timers: [{ on: onTime, off: offTime }] })
    toast.success("Timer set on backend.")
    logBasic(`Timer set: On ${onTime}, Off ${offTime}`)
  }, [onTime, offTime, sendCommand, logBasic])

  const handleTimerToggle = useCallback(() => {
    const newTimers = system_timers.length > 0 ? [] : [{ on: onTime, off: offTime }]
    sendCommand({ type: "set_timer", timers: newTimers })
    if (newTimers.length === 0) {
      setOnTime("07:00"); setOffTime("22:00")
      toast.info("Timer disabled and cleared.")
      logBasic("Timer disabled.")
    } else {
      toast.success("Timer enabled.")
      logBasic("Timer enabled.")
    }
  }, [system_timers, onTime, offTime, sendCommand, logBasic])

  const handleTimeChange = useCallback((e, type) => {
    const value = e.target.value
    if (type === 'on') setOnTime(value)
    else setOffTime(value)
    localStorage.setItem(type === 'on' ? "onTime" : "offTime", value)
  }, [])

  return (
    <div className="card status-card">
      <div className="card-header">
        <h2 className="card-title"><BarChart2 size={22} className="card-icon" />Status, Timer & Logs</h2>
      </div>
      <div className="card-content">
        <div className="performance-metrics-container">
          <div className="performance-metric"><Radio size={32} /><div className="metric-details"><div className="metric-label">Latency</div><div className="metric-value">{wsLatency !== null ? `${wsLatency}ms` : "N/A"}</div></div></div>
          <div className="performance-metric"><Cpu size={32} /><div className="metric-details"><div className="metric-label">CPU</div><div className="metric-value">{cpu_percent.toFixed(1)}%</div></div></div>
          <div className="performance-metric"><Memory size={32} /><div className="metric-details"><div className="metric-label">Memory</div><div className="metric-value">{mem_percent.toFixed(1)}%</div></div></div>
          <div className="performance-metric"><Thermometer size={32} /><div className="metric-details"><div className="metric-label">Temperature</div><div className="metric-value">{temperature !== null ? `${temperature.toFixed(1)}°C` : "N/A"}</div></div></div>
        </div>
        <div className="status-display">
          <div className="status-icon">{state.isSystemOn ? <div className="status-icon-active"><Zap size={30} /></div> : <div className="status-icon-inactive"><AlertCircle size={24} /></div>}</div>
          <div className="status-info">
            <div className="status-primary">{state.isSystemOn ? "System Active" : "System Inactive"}</div>
            <div className="status-secondary">{`CCT: ${state.current_cct.toFixed(0)}K, Intensity: ${state.current_intensity.toFixed(0)}lux, ${new Date().toLocaleTimeString()}`}</div>
          </div>
        </div>
        <div className="timer-control">
          <div className="timer-header">
            <div className="timer-title"><Clock size={20} /><span>System Timer</span></div>
            <div className="timer-toggle-wrapper">
              <div className="timer-toggle-tabs">
                <button className={`timer-toggle-tab ${system_timers.length > 0 ? 'active' : ''}`} onClick={handleTimerToggle} disabled={!state.isSystemOn}>Enabled ({system_timers.length})</button>
                <button className={`timer-toggle-tab ${system_timers.length === 0 ? 'active' : ''}`} onClick={handleTimerToggle} disabled={!state.isSystemOn}>Disabled</button>
              </div>
            </div>
          </div>
          <div className="timer-inputs">
            {system_timers.length > 0 ? (
              <>
                <div className="time-input-group"><label>On Time</label><input type="time" value={onTime} onChange={(e) => handleTimeChange(e, 'on')} disabled={!state.isSystemOn} /></div>
                <div className="time-input-group"><label>Off Time</label><input type="time" value={offTime} onChange={(e) => handleTimeChange(e, 'off')} disabled={!state.isSystemOn} /></div>
                <div className="current-timers"><strong>Active:</strong><ul>{system_timers.map((t, i) => <li key={i}>{t.on} → {t.off}</li>)}</ul></div>
              </>
            ) : (
              <p>No timers set.</p>
            )}
            <button className="set-timer-button" onClick={handleSetTimer} disabled={!state.isSystemOn}>Set</button>
          </div>
        </div>
        <div className="logs-button-container">
          <button className="logs-button" onClick={() => setIsLogsPanelOpen(!isLogsPanelOpen)}><FileText size={22} /><span>View System Logs</span></button>
        </div>
      </div>
    </div>
  )
}

export default StatusCard