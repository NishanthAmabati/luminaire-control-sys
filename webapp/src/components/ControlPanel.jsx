import { useCallback, useRef } from "react"
import { Sliders } from "lucide-react"
import { FaPlay, FaStop } from 'react-icons/fa'; 
import { toast } from "react-hot-toast"

const ControlPanel = ({ state, sendCommand, setMode, loadScene, activateScene, stopScheduler }) => {
  const debounceTimeout = useRef(null)

  const adjustLight = useCallback((cct, intensity) => {
    if (debounceTimeout.current) clearTimeout(debounceTimeout.current)
    debounceTimeout.current = setTimeout(() => {
      // Calculate cw and ww from cct and intensity using backend formula
      // Backend uses: min_cct=3500, max_cct=6500, max_intensity=500
      const min_cct = 3500
      const max_cct = 6500
      const max_intensity = 500
      const clampedCct = Math.max(min_cct, Math.min(max_cct, cct))
      const clampedIntensity = Math.max(0, Math.min(max_intensity, intensity))
      const intensityPercent = clampedIntensity / max_intensity
      const cwBase = (clampedCct - min_cct) / ((max_cct - min_cct) / 100.0)
      const wwBase = 100.0 - cwBase
      const cw = Math.max(0, Math.min(99.99, cwBase * intensityPercent))
      const ww = Math.max(0, Math.min(99.99, wwBase * intensityPercent))
      sendCommand({ type: "sendAll", cw, ww, intensity: clampedIntensity })
    }, 100)
  }, [sendCommand])

  const handleCctChange = useCallback((e) => {
    const cct = parseFloat(e.target.value)
    const intensity = state.current_intensity
    adjustLight(cct, intensity)
  }, [state.current_intensity, adjustLight])

  const handleIntensityChange = useCallback((e) => {
    const intensity = parseFloat(e.target.value)
    const cct = state.current_cct
    adjustLight(cct, intensity)
  }, [state.current_cct, adjustLight])

  return (
    <div className="card control-card">
      <div className="card-header">
        <h2 className="card-title">
          <Sliders size={22} className="card-icon" />
          Control Panel
        </h2>
      </div>
      <div className="card-content">
        <div className="mode-toggle">
          <div className="mode-toggle-tabs" role="tablist" aria-label="Mode selection">
            <button
              className={`mode-toggle-tab ${state.auto_mode ? "active" : ""}`}
              onClick={() => setMode(true)}
              role="tab"
              aria-selected={state.auto_mode}
              aria-label="Enable auto mode"
            >
              Auto
            </button>
            <button
              className={`mode-toggle-tab ${!state.auto_mode ? "active" : ""}`}
              onClick={() => setMode(false)}
              role="tab"
              aria-selected={!state.auto_mode}
              aria-label="Enable manual mode"
            >
              Manual
            </button>
          </div>
        </div>
        <div className="scene-control">
          <div className="scene-select-group">
            <label htmlFor="scene-select">Select Scene</label>
            <select
              id="scene-select"
              value={state.current_scene || ""}
              onChange={(e) => loadScene(e.target.value)}
              disabled={!state.isSystemOn}
              className="scene-select"
            >
              <option value="">Select a scene</option>
              {state.available_scenes.map((scene) => (
                <option key={scene} value={scene}>
                  {scene}
                </option>
              ))}
            </select>
          </div>
          <div className="scene-button-group">
            <button
              className="scene-button"
              onClick={() => activateScene()}
              disabled={!state.current_scene || !state.isSystemOn}
              aria-label="Activate scene"
            >
              <FaPlay size={16} />
              Activate
            </button>
            <button
              className="scene-button stop-button"
              onClick={() => stopScheduler()}
              disabled={state.scheduler.status !== "running" || !state.isSystemOn}
              aria-label="Stop scheduler"
            >
              <FaStop size={16} />
              Stop
            </button>
          </div>
        </div>
        {!state.auto_mode && (
          <div className="manual-control">
            <div className="slider-group">
              <label htmlFor="cct-slider">CCT ({state.current_cct.toFixed(0)}K)</label>
              <input
                id="cct-slider"
                type="range"
                min="3500"
                max="6500"
                step="100"
                value={state.current_cct}
                onChange={handleCctChange}
                disabled={!state.isSystemOn}
                className="slider"
                aria-label={`CCT slider, current value ${state.current_cct.toFixed(0)}K`}
              />
            </div>
            <div className="slider-group">
              <label htmlFor="intensity-slider">Intensity ({state.current_intensity.toFixed(0)} lux)</label>
              <input
                id="intensity-slider"
                type="range"
                min="0"
                max="500"
                step="10"
                value={state.current_intensity}
                onChange={handleIntensityChange}
                disabled={!state.isSystemOn}
                className="slider"
                aria-label={`Intensity slider, current value ${state.current_intensity.toFixed(0)} lux`}
              />
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default ControlPanel