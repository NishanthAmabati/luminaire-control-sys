"use client"

// Import necessary React hooks and components
import { useState, useEffect, useRef, useMemo, useCallback } from "react"
import { Line } from "react-chartjs-2"
import {
  Chart as ChartJS,
  LineElement,
  PointElement,
  LinearScale,
  Title,
  CategoryScale,
  Filler,
  Tooltip,
  Legend,
  registerables,
} from "chart.js"
import annotationPlugin from "chartjs-plugin-annotation"
import "./App.css"
import { FaSyncAlt, FaPlay, FaStop, FaExclamationTriangle, FaCheckCircle } from "react-icons/fa"
import {
  Thermometer,
  Sun,
  Moon,
  Cpu,
  MemoryStickIcon as Memory,
  BarChart2,
  AlertCircle,
  Zap,
  Radio,
  FileText,
  Search,
  Sliders,
  Network,
  Clock,
} from "lucide-react"
import { toast, Toaster } from "react-hot-toast"
import { debounce } from "lodash"
import logo from "./SSS.png"
import { useDevices } from "./contexts/DeviceContext"
import { useSystem } from "./contexts/SystemContext"
import DeviceItem from "./components/DeviceItem"
// Log UI removed for performance - LogContext kept for potential future use
// import { useLogs } from "./contexts/LogContext"

// Define custom plugin for chart labels
const currentValueLabelPlugin = {
  id: "currentValueLabel",
  afterDraw: (chart, args, options) => {
    const { ctx, chartArea, width } = chart
    const text = options.text || ""
    const theme = chart.canvas.classList.contains("dark-theme") ? "dark" : "light"
    ctx.save()
    ctx.font = 'bold 14px "SF Pro Display", system-ui, sans-serif'
    const textMetrics = ctx.measureText(text)
    const textWidth = textMetrics.width
    const textHeight = 14
    const paddingX = 12
    const paddingY = 6
    const boxWidth = Math.max(160, textWidth + paddingX * 2)
    const boxHeight = textHeight + paddingY * 2
    const cornerRadius = 6
    const x = chartArea.right - boxWidth - 0
    const y = chartArea.top - boxHeight - 0
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

// Register Chart.js components
ChartJS.register(
  ...registerables,
  LineElement,
  PointElement,
  LinearScale,
  Title,
  CategoryScale,
  Filler,
  Tooltip,
  Legend,
  annotationPlugin,
  currentValueLabelPlugin
)

// Custom plugin for chart background
const plotAreaBackgroundPlugin = {
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

const App = () => {
  // Use context hooks for decoupled state management
  const { devices, updateDevices } = useDevices()
  const { systemState, updateSystemState, updateScheduler } = useSystem()
  // Log UI removed for performance optimization
  // const { basicLogs, advancedLogs, addBasicLog, addAdvancedLog, clearBasicLogs, clearAdvancedLogs} = useLogs()

  // Local UI-only state
  const [theme, setTheme] = useState(() => localStorage.getItem("theme") || "dark")
  const [state, setState] = useState({
    // Keep only UI-related state here; devices/system/logs are in contexts
    wsLatency: null,
    error: null,
  })
  const [sceneData, setSceneData] = useState({ cct: [], intensity: [] })
  const [localCct, setLocalCct] = useState(null)
  const [localIntensity, setLocalIntensity] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const [verticalLinePosition, setVerticalLinePosition] = useState(0)
  const [manualSystemOff, setManualSystemOff] = useState(false)
  // Log panel state removed for performance (logs UI completely removed)
  // const [activeLogTab, setActiveLogTab] = useState("basic")
  // const [isLogsPanelOpen, setIsLogsPanelOpen] = useState(false)
  const [deviceSearchQuery, setDeviceSearchQuery] = useState("")
  const [isSearchVisible, setIsSearchVisible] = useState(false)
  const [isAdjusting, setIsAdjusting] = useState(false)
  const [isTimerEnabled, setIsTimerEnabled] = useState(() => JSON.parse(localStorage.getItem("isTimerEnabled") || "false"))
  const [onTime, setOnTime] = useState(() => localStorage.getItem("onTime") || "")
  const [offTime, setOffTime] = useState(() => localStorage.getItem("offTime") || "")
  const [runningScene, setRunningScene] = useState(null)
  const [lastCompletionLog, setLastCompletionLog] = useState(null)

  const ws = useRef(null)
  const debounceTimeout = useRef(null)
  const lastPingTime = useRef(0)
  const lastPongTime = useRef(0)
  const animationFrameId = useRef(null)
  const lastIntervalUpdateTime = useRef(Date.now())
  const sceneStartTime = useRef(null)
  const lastCommandSent = useRef(null)
  const previewTimeout = useRef(null)

  const debouncedUpdateState = useRef(
    debounce((newState, newSceneData, newOnTime, newOffTime, newLocalCct, newLocalIntensity, newVerticalLinePosition) => {
      setState((prev) => ({ ...prev, ...newState }));
      setSceneData(newSceneData);
      if (!isEditingTimer.onTime) setOnTime(newOnTime);
      if (!isEditingTimer.offTime) setOffTime(newOffTime);
      setLocalCct(newLocalCct);
      setLocalIntensity(newLocalIntensity);
      if (newVerticalLinePosition !== undefined) {
        setVerticalLinePosition(newVerticalLinePosition);
      }
    }, 100)
  ).current

  const getCurrentSecondOfDay = () => {
    const now = new Date()
    return now.getHours() * 3600 + now.getMinutes() * 60 + now.getSeconds()
  }

  // Log functions converted to no-ops since logs UI was removed for performance
  const logBasic = useCallback((message) => {
    // No-op: logs UI removed for performance optimization
  }, []);

  const logAdvanced = useCallback((message) => {
    // No-op: logs UI removed for performance optimization
  }, []);

  const toggleTheme = () => {
    setTheme((prevTheme) => {
      const newTheme = prevTheme === "dark" ? "light" : "dark"
      localStorage.setItem("theme", newTheme)
      document.body.className = newTheme
      return newTheme
    })
  }

  const sendCommand = useCallback(
    (command) => {
      const commandString = JSON.stringify(command)
      if (ws.current?.readyState === WebSocket.OPEN && lastCommandSent.current !== commandString) {
        ws.current.send(commandString)
        logAdvanced(
          `Sent [${command.type}]: ${Object.entries(command)
            .filter(([k]) => k !== "type")
            .map(([k, v]) => `${k}=${v}`)
            .join(", ")}`
        )
        lastCommandSent.current = commandString
      } else if (ws.current?.readyState !== WebSocket.OPEN) {
        setState((prev) => ({ ...prev, error: "WebSocket not connected" }))
      }
    },
    [logAdvanced]
  )

  const activateScene = useCallback(() => {
    if (systemState.loaded_scene) {
      setIsLoading(true)
      sendCommand({ type: "activate_scene", scene: systemState.loaded_scene })
      toast.success(`Scene Activated`)
      logBasic(`Activated scene: ${systemState.loaded_scene}`)
      updateSystemState({
        current_scene: systemState.loaded_scene,
        auto_mode: true,
      })
      updateScheduler({ status: "running" })
      setRunningScene(systemState.loaded_scene)
      const currentSecond = getCurrentSecondOfDay()
      setVerticalLinePosition(Math.floor(currentSecond / 10))
      lastIntervalUpdateTime.current = Date.now()
      sceneStartTime.current = Date.now()
      if (previewTimeout.current) {
        clearTimeout(previewTimeout.current)
        previewTimeout.current = null
      }
      setTimeout(() => setIsLoading(false), 500)
    }
  }, [systemState.loaded_scene, sendCommand, logBasic, updateSystemState, updateScheduler])

  const setMode = useCallback(
    async (auto) => {
      setIsLoading(true)
      sendCommand({ type: "set_mode", auto })
      if (auto) {
        toast.success("Switched to Auto Mode")
        updateSystemState({ auto_mode: true })
        
        // Wait for backend to process mode switch and fetch updated state
        setTimeout(() => {
          (async () => {
            try {
              const apiBaseUrl = `http://${window.location.hostname}:8000`
              const response = await fetch(`${apiBaseUrl}/api/system_state`)
              if (response.ok) {
                const stateData = await response.json()
                
                // Update scene data if available
                if (stateData.scene_data) {
                  setSceneData({
                    cct: Array.isArray(stateData.scene_data.cct) ? stateData.scene_data.cct : [],
                    intensity: Array.isArray(stateData.scene_data.intensity) ? stateData.scene_data.intensity : []
                  })
                }
                
                // Update state
                const systemUpdates = {}
                if (stateData.current_scene !== undefined) systemUpdates.current_scene = stateData.current_scene
                if (stateData.loaded_scene !== undefined) systemUpdates.loaded_scene = stateData.loaded_scene
                if (stateData.current_cct !== undefined) systemUpdates.current_cct = stateData.current_cct
                if (stateData.current_intensity !== undefined) systemUpdates.current_intensity = stateData.current_intensity
                if (stateData.cw !== undefined) systemUpdates.cw = stateData.cw
                if (stateData.ww !== undefined) systemUpdates.ww = stateData.ww
                updateSystemState(systemUpdates)
                
                // Update scheduler status
                if (stateData.scheduler) {
                  updateScheduler(stateData.scheduler)
                }
              }
            } catch (error) {
              console.error("Error fetching state after mode switch:", error)
            } finally {
              setIsLoading(false)
            }
          })()
        }, 300)
      } else {
        toast.success("Switched to Manual Mode")
        // Clear scene data in UI when switching to manual (as requested)
        setSceneData({ cct: [], intensity: [] })
        updateSystemState({ 
          auto_mode: false,
          loaded_scene: null  // Clear loaded scene in UI
        })
        updateScheduler({ status: "paused" })
        setVerticalLinePosition(0)
        
        // Send current manual values to devices immediately when switching to manual mode
        // This ensures the lights are controlled by manual settings right away
        setTimeout(() => {
          const min_cct = 3500
          const max_cct = 6500
          const max_intensity = 500
          const cct = systemState.current_cct
          const intensity = systemState.current_intensity
          const clampedCct = Math.max(min_cct, Math.min(max_cct, cct))
          const clampedIntensity = Math.max(0, Math.min(max_intensity, intensity))
          const intensityPercent = clampedIntensity / max_intensity
          const cwBase = (clampedCct - min_cct) / ((max_cct - min_cct) / 100.0)
          const wwBase = 100.0 - cwBase
          const cw = Math.max(0, Math.min(99.99, cwBase * intensityPercent))
          const ww = Math.max(0, Math.min(99.99, wwBase * intensityPercent))
          sendCommand({ type: "sendAll", cw, ww, intensity: clampedIntensity })
          logBasic(`Manual mode activated: CCT ${clampedCct}K, Intensity ${clampedIntensity} lux`)
          setIsLoading(false)
        }, 300)
      }
    },
    [sendCommand, updateSystemState, updateScheduler, setSceneData]
  )

  const loadScene = useCallback(
    async (scene) => {
      setIsLoading(true)
      if (systemState.scheduler.status === "running" && systemState.current_scene) {
        setRunningScene(systemState.current_scene)
        if (previewTimeout.current) {
          clearTimeout(previewTimeout.current)
        }
        previewTimeout.current = setTimeout(() => {
          if (systemState.scheduler.status === "running" && systemState.current_scene === runningScene) {
            sendCommand({ type: "load_scene", scene: systemState.current_scene })
            toast.success(`Reverted to running scene: ${systemState.current_scene}`)
            updateSystemState({ loaded_scene: systemState.current_scene })
            updateScheduler({ status: "running" })
          }
        }, 5000)
      }
      sendCommand({ type: "load_scene", scene })
      toast.success(`Scene Loaded: ${scene}`)
      updateSystemState({ loaded_scene: scene })
      updateScheduler({ status: "pending" })
      
      // Wait for backend to process load_scene command before fetching
      await new Promise(resolve => setTimeout(resolve, 200))
      
      // Fetch scene data immediately to populate graphs
      try {
        const apiBaseUrl = `http://${window.location.hostname}:8000`
        const response = await fetch(`${apiBaseUrl}/api/system_state`)
        if (response.ok) {
          const stateData = await response.json()
          if (stateData.scene_data) {
            setSceneData({
              cct: Array.isArray(stateData.scene_data.cct) ? stateData.scene_data.cct : [],
              intensity: Array.isArray(stateData.scene_data.intensity) ? stateData.scene_data.intensity : []
            })
            console.log(`Loaded scene data for ${scene}: ${stateData.scene_data.cct?.length || 0} data points`)
          }
        }
      } catch (error) {
        console.error("Error fetching scene data after load:", error)
      }
      
      setTimeout(() => setIsLoading(false), 600)
    },
    [sendCommand, systemState.current_scene, systemState.scheduler.status, runningScene, updateSystemState, updateScheduler, setSceneData]
  )

  const stopScheduler = useCallback(() => {
    sendCommand({ type: "stop_scheduler" })
    toast.success("Scene Stopped")
    logBasic("Scheduler stopped")
    updateScheduler({ status: "idle", total_intervals: 0, current_interval: 0 })
    updateSystemState({
      scene_data: { cct: [], intensity: [] },
      current_scene: null,
      loaded_scene: null,
      current_cct: 3500,
      current_intensity: 250,
      cw: 50.0,
      ww: 50.0,
    })
    setRunningScene(null)
    setSceneData({ cct: [], intensity: [] })
    setVerticalLinePosition(0)
    if (animationFrameId.current) {
      cancelAnimationFrame(animationFrameId.current)
    }
    if (previewTimeout.current) {
      clearTimeout(previewTimeout.current)
      previewTimeout.current = null
    }
  }, [sendCommand, logBasic, updateScheduler, updateSystemState])

  const adjustLight = useCallback(
    (light_type, value) => {
      setIsAdjusting(true)
      let newCw = systemState.cw
      let newWw = systemState.ww
      if (light_type === "cw") {
        newCw = Math.min(100, Math.max(0, value))
        newWw = 100 - newCw
      } else if (light_type === "ww") {
        newWw = Math.min(100, Math.max(0, value))
        newCw = 100 - newWw
      }
      sendCommand({ type: "sendAll", cw: newCw, ww: newWw, intensity: systemState.current_intensity })
      logBasic(`Adjusted ${light_type.toUpperCase()} to ${light_type === "cw" ? newCw : newWw}%`)
      setTimeout(() => setIsAdjusting(false), 500)
      updateSystemState({ cw: newCw, ww: newWw })
    },
    [sendCommand, logBasic, updateSystemState, systemState.cw, systemState.ww, systemState.current_intensity]
  )

  const adjustIntensity = useCallback(
    (value) => {
      const newIntensity = Math.max(0, Math.min(500, value))
      const intensityPercent = newIntensity / 500.0
      const cwBase = (systemState.current_cct - 3500) / ((6500 - 3500) / 100.0)
      const wwBase = 100.0 - cwBase
      const newCw = Math.max(0, Math.min(99.99, cwBase * intensityPercent))
      const newWw = Math.max(0, Math.min(99.99, wwBase * intensityPercent))
      sendCommand({ type: "sendAll", cw: newCw, ww: newWw, intensity: newIntensity })
      updateSystemState({ current_intensity: newIntensity, cw: newCw, ww: newWw })
    },
    [sendCommand, updateSystemState, systemState.current_cct]
  )

  const setCct = useCallback(
    (cct) => {
      if (debounceTimeout.current) clearTimeout(debounceTimeout.current)
      debounceTimeout.current = setTimeout(() => {
        const validatedCct = Math.max(3500, Math.min(6500, Number(cct) || 3500))
        if (validatedCct !== systemState.current_cct) {
          sendCommand({ type: "set_cct", cct: validatedCct })
          logBasic(`Set CCT to ${validatedCct}K`)
          updateSystemState({ current_cct: validatedCct })
        }
      }, 500)
    },
    [sendCommand, systemState.current_cct, logBasic, updateSystemState]
  )

  const setIntensity = useCallback(
    (intensity) => {
      if (debounceTimeout.current) clearTimeout(debounceTimeout.current)
      debounceTimeout.current = setTimeout(() => {
        const validatedIntensity = Math.max(0, Math.min(500, Number(intensity) || 0))
        if (validatedIntensity !== systemState.current_intensity) {
          adjustIntensity(validatedIntensity)
          logBasic(`Set Intensity to ${validatedIntensity} lux`)
          setLocalIntensity(validatedIntensity)
        }
      }, 500)
    },
    [adjustIntensity, systemState.current_intensity, logBasic]
  )

  const handleCctChange = useCallback(
    (e) => {
      setIsAdjusting(true)
      const value = Number.parseInt(e.target.value)
      setLocalCct(value)
      if (e.type === "change") {
        setCct(value)
        setTimeout(() => setIsAdjusting(false), 500)
      }
    },
    [setCct]
  )

  const handleIntensityChange = useCallback(
    (e) => {
      setIsAdjusting(true)
      const value = Number.parseInt(e.target.value)
      setLocalIntensity(value)
      if (e.type === "change") {
        setIntensity(value)
        setTimeout(() => setIsAdjusting(false), 500)
      }
    },
    [setIntensity]
  )

  const toggleSystem = useCallback(() => {
    const newSystemState = !systemState.isSystemOn;
    sendCommand({ type: "toggle_system", isSystemOn: newSystemState });
    if (newSystemState) {
      sendCommand({ type: "set_manual_override", override: true });
    }
    logBasic(`System turned ${newSystemState ? "ON" : "OFF"}`);
    setManualSystemOff(!newSystemState);
    updateSystemState({ isSystemOn: newSystemState, is_manual_override: newSystemState });
    setState((prev) => ({ ...prev, error: null }));
    if (newSystemState && systemState.current_scene) {
      setTimeout(() => {
        activateScene();
      }, 500);
    }
    setVerticalLinePosition(0);
  }, [sendCommand, logBasic, activateScene, systemState.isSystemOn, systemState.current_scene, updateSystemState]);

  const handleTimerToggle = useCallback((enable) => {
    // If enable is not provided, toggle the current state
    const newIsEnabled = enable !== undefined ? enable : !isTimerEnabled;
    
    // Don't do anything if already in the desired state
    if (newIsEnabled === isTimerEnabled) {
      return;
    }
    
    setIsTimerEnabled(newIsEnabled);
    sendCommand({ type: "toggle_timer", enable: newIsEnabled });
    toast.success(`Timer ${newIsEnabled ? "enabled" : "disabled"}`);
    logBasic(`Timer ${newIsEnabled ? "enabled" : "disabled"}`);
    if (newIsEnabled && systemState.system_timers.length > 0) {
      setOnTime(systemState.system_timers[0].on || "");
      setOffTime(systemState.system_timers[0].off || "");
      logBasic(`Timers populated from local copy: On ${systemState.system_timers[0].on}, Off ${systemState.system_timers[0].off}`);
    } else if (!newIsEnabled) {
      // Clear timer fields and timer state when disabling
      setOnTime("");
      setOffTime("");
      updateSystemState({ 
        is_manual_override: false,
        system_timers: [],
        isTimerEnabled: false
      });
    }
  }, [isTimerEnabled, sendCommand, logBasic, systemState.system_timers, updateSystemState]);

  const handleTimeChange = useCallback(
    (e, type) => {
      const value = e.target.value;
      if (type === "on") {
        setOnTime(value);
      } else {
        setOffTime(value);
      }
    },
    [setOnTime, setOffTime]
  );

  const handleSetTimer = useCallback(() => {
    if (!onTime || !offTime) {
      toast.error("Please set both On and Off times.");
      return;
    }
    if (onTime === offTime) {
      toast.error("On and Off times cannot be the same.");
      return;
    }
    sendCommand({ type: "set_timer", timers: [{ on: onTime, off: offTime }] });
    toast.success("Timer set on backend.");
    logBasic(`Timer set: On ${onTime}, Off ${offTime}`);
  }, [onTime, offTime, sendCommand, logBasic]);

  const handleDeviceSearchChange = useCallback((e) => {
    setDeviceSearchQuery(e.target.value)
  }, [])

  const toggleSearchBar = useCallback(() => {
    setIsSearchVisible((prev) => !prev)
  }, [])

  const animateVerticalLine = useCallback(() => {
    if (systemState.isSystemOn) {
      const now = Date.now()
      if (now - lastIntervalUpdateTime.current >= 1000) {
        const currentSecond = getCurrentSecondOfDay()
        const newPosition = Math.floor(currentSecond / 10) % 8640
        setVerticalLinePosition((prev) => {
          if (Math.abs(prev - newPosition) >= 1) {
            lastIntervalUpdateTime.current = now
            return newPosition
          }
          return prev
        })
      }
      animationFrameId.current = requestAnimationFrame(animateVerticalLine)
    }
  }, [systemState.isSystemOn])

  useEffect(() => {
    localStorage.setItem("isTimerEnabled", JSON.stringify(isTimerEnabled))
    localStorage.setItem("onTime", onTime)
    localStorage.setItem("offTime", offTime)
  }, [isTimerEnabled, onTime, offTime])

  useEffect(() => {
    localStorage.setItem("theme", theme)
    document.body.className = theme
  }, [theme])

  // Bootstrap initial state from REST APIs on app load
  useEffect(() => {
    const bootstrapState = async () => {
      // Use dynamic API base URL from window.location for cross-IP/container access
      const apiBaseUrl = `http://${window.location.hostname}:8000`
      
      try {
        // Fetch initial device list
        const devicesResponse = await fetch(`${apiBaseUrl}/api/devices`)
        if (devicesResponse.ok) {
          const devicesData = await devicesResponse.json()
          if (devicesData.devices) {
            updateDevices(devicesData.devices)
          }
        } else {
          console.warn("Failed to fetch initial devices:", devicesResponse.status)
        }
      } catch (error) {
        console.error("Error bootstrapping devices:", error)
      }

      try {
        // Fetch full system state to restore CCT, intensity, mode, etc.
        const stateResponse = await fetch(`${apiBaseUrl}/api/system_state`)
        if (stateResponse.ok) {
          const stateData = await stateResponse.json()
          // Update all relevant system state fields
          const systemUpdates = {}
          if (stateData.current_cct !== undefined) systemUpdates.current_cct = stateData.current_cct
          if (stateData.current_intensity !== undefined) systemUpdates.current_intensity = stateData.current_intensity
          if (stateData.auto_mode !== undefined) systemUpdates.auto_mode = stateData.auto_mode
          if (stateData.isSystemOn !== undefined) systemUpdates.isSystemOn = stateData.isSystemOn
          if (stateData.cw !== undefined) systemUpdates.cw = stateData.cw
          if (stateData.ww !== undefined) systemUpdates.ww = stateData.ww
          if (stateData.current_scene !== undefined) systemUpdates.current_scene = stateData.current_scene
          if (stateData.loaded_scene !== undefined) systemUpdates.loaded_scene = stateData.loaded_scene
          if (Array.isArray(stateData.available_scenes)) systemUpdates.available_scenes = stateData.available_scenes
          
          updateSystemState(systemUpdates)
          
          // Update scene data for graphs
          if (stateData.scene_data) {
            setSceneData({
              cct: Array.isArray(stateData.scene_data.cct) ? stateData.scene_data.cct : [],
              intensity: Array.isArray(stateData.scene_data.intensity) ? stateData.scene_data.intensity : []
            })
          }
          
          // Update local CCT and intensity values for sliders
          if (stateData.current_cct !== undefined) setLocalCct(stateData.current_cct)
          if (stateData.current_intensity !== undefined) setLocalIntensity(stateData.current_intensity)
          
          // Update scheduler state if available
          if (stateData.scheduler) {
            updateScheduler(stateData.scheduler)
          }
        } else {
          console.warn("Failed to fetch system state:", stateResponse.status)
        }
      } catch (error) {
        console.error("Error bootstrapping system state:", error)
      }

      try {
        // Fetch timers from backend
        const timersResponse = await fetch(`${apiBaseUrl}/api/timers`)
        if (timersResponse.ok) {
          const timersData = await timersResponse.json()
          if (Array.isArray(timersData.timers)) {
            updateSystemState({ 
              system_timers: timersData.timers,
              isTimerEnabled: timersData.isTimerEnabled 
            })
            // Update local timer state if timers exist
            if (timersData.timers.length > 0) {
              setOnTime(timersData.timers[0].on || "")
              setOffTime(timersData.timers[0].off || "")
            }
            setIsTimerEnabled(timersData.isTimerEnabled || false)
          }
        } else {
          console.warn("Failed to fetch timers:", timersResponse.status)
        }
      } catch (error) {
        console.error("Error bootstrapping timers:", error)
      }

    }

    bootstrapState()
  }, [])

  useEffect(() => {
    let reconnectAttempts = 0;
    const maxReconnectAttempts = 10;
    const maxBackoff = 32000;
    let reconnectTimeout = null;

    const connectWebSocket = () => {
      setIsLoading(true);
      ws.current = new WebSocket(`ws://${window.location.hostname}:5001`);
      ws.current.onopen = () => {
        logAdvanced("WebSocket connected");
        setState((prev) => ({ ...prev, error: null }));
        reconnectAttempts = 0;
        setIsLoading(false);
        const pingInterval = setInterval(() => {
          if (ws.current?.readyState === WebSocket.OPEN) {
            lastPingTime.current = Date.now();
            ws.current.send(JSON.stringify({ type: "ping" }));
          }
        }, 1000);
        ws.current.pingInterval = pingInterval;
      };
      ws.current.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
        if (data.type === "live_update") {
            updateSystemState(prev => ({
                ...prev,
                ...data.data,
                scheduler: {
                    ...prev.scheduler,
                    ...data.data.scheduler
                }
            }));
        }
          console.log(
            "%c[WS → FRONTEND] RAW PAYLOAD:",
            "background: #222; color: #bada55; font-size:14px",
            data
          );
          if (data.type === "system_state") {
            console.log(
              "%c[WS → SYSTEM_STATE] Received:",
              "background: #003366; color: #fff; font-size:13px",
              JSON.stringify(data.data, null, 2)
            );
          }
          if (data.type === "pong") {
            lastPongTime.current = Date.now();
            const latency = lastPongTime.current - lastPingTime.current;
            if (data.isSystemOn && manualSystemOff) {
              setManualSystemOff(false);
            }
            setState((prev) => ({ ...prev, wsLatency: latency, error: null }));
          } else if (data.type === "system_stats" || data.type === "system_stats_update") {
            // Handle system stats (CPU, memory, temperature) from monitoring service
            updateSystemState({
              cpu_percent: data.data.cpu_percent !== undefined ? data.data.cpu_percent : (data.data.cpu !== undefined ? data.data.cpu : systemState.cpu_percent),
              mem_percent: data.data.mem_percent !== undefined ? data.data.mem_percent : (data.data.memory !== undefined ? data.data.memory : systemState.mem_percent),
              temperature: (data.data.temperature !== undefined && data.data.temperature !== null) ? data.data.temperature : systemState.temperature,
            });
          } else if (data.type === "device_update") {
            // Handle granular device updates from the refactored backend
            if (data.data.devices) {
              // Full devices list provided
              updateDevices(data.data.devices);
            } else if (data.data.ip) {
              // Individual device update
              updateDevices({
                ...devices,
                [data.data.ip]: {
                  cw: data.data.cw,
                  ww: data.data.ww,
                  connected: data.data.connected,
                  last_seen: data.data.last_seen,
                },
              });
            }
          } else if (data.type === "live_update") {
              const isTimerEnabledValid = typeof data.data.isTimerEnabled === "boolean";
                if (!isTimerEnabledValid) {
                  logAdvanced("Invalid live_update: isTimerEnabled is not a boolean");
                  return;
                }
                setIsTimerEnabled(data.data.isTimerEnabled !== undefined ? data.data.isTimerEnabled : isTimerEnabled);
              // Always update scene data when provided by backend
              // Clear scene data when system is turned off
              if (data.data.isSystemOn === false) {
                setSceneData({ cct: [], intensity: [] });
              } else if (data.data.scene_data) {
                setSceneData({
                  cct: Array.isArray(data.data.scene_data.cct) ? data.data.scene_data.cct : sceneData.cct,
                  intensity: Array.isArray(data.data.scene_data.intensity) ? data.data.scene_data.intensity : sceneData.intensity,
                });
              }
              
              // Update system state via context
              const systemUpdates = {};
              if (data.data.current_cct !== undefined) systemUpdates.current_cct = data.data.current_cct;
              if (data.data.current_intensity !== undefined) systemUpdates.current_intensity = data.data.current_intensity;
              if (data.data.cw !== undefined) systemUpdates.cw = data.data.cw;
              if (data.data.ww !== undefined) systemUpdates.ww = data.data.ww;
              if (data.data.isSystemOn !== undefined && !systemState.is_manual_override) {
                systemUpdates.isSystemOn = data.data.isSystemOn;
                // When system is turned OFF, clear scene-related UI elements
                if (data.data.isSystemOn === false) {
                  systemUpdates.loaded_scene = null;
                  systemUpdates.current_scene = null;
                }
              }
              if (data.data.auto_mode !== undefined) systemUpdates.auto_mode = data.data.auto_mode;
              if (data.data.current_scene !== undefined) systemUpdates.current_scene = data.data.current_scene;
              if (data.data.loaded_scene !== undefined) systemUpdates.loaded_scene = data.data.loaded_scene;
              if (Array.isArray(data.data.available_scenes)) systemUpdates.available_scenes = data.data.available_scenes;
              if (Array.isArray(data.data.system_timers)) systemUpdates.system_timers = data.data.system_timers;
              
              updateSystemState(systemUpdates);
              
              // Update scheduler via context
              if (data.data.scheduler) {
                const schedulerUpdates = {};
                if (data.data.scheduler.status !== undefined) schedulerUpdates.status = data.data.scheduler.status;
                if (data.data.scheduler.current_interval !== undefined) schedulerUpdates.current_interval = data.data.scheduler.current_interval;
                if (data.data.scheduler.total_intervals !== undefined) schedulerUpdates.total_intervals = data.data.scheduler.total_intervals;
                // NOTE: current_cct is sent at root level (data.data.current_cct), NOT in scheduler object
                // The scheduler object's current_cct is stale and should not be used
                if (data.data.scheduler.interval_progress !== undefined) {
                  schedulerUpdates.interval_progress = data.data.scheduler.interval_progress;
                }
                updateScheduler(schedulerUpdates);
                
                // Update vertical line position for real-time graph animation when in auto mode
                // Check both incoming message data and current state to handle all cases:
                // - When backend sends explicit "running" status
                // - When scene is loaded (even if status not explicitly sent in this message)
                const shouldUpdateVerticalLine = systemState.auto_mode && (
                  data.data.scheduler?.status === "running" || 
                  systemState.scheduler.status === "running" || 
                  data.data.loaded_scene || 
                  systemState.loaded_scene
                );
                
                if (shouldUpdateVerticalLine) {
                  const currentSecond = getCurrentSecondOfDay();
                  setVerticalLinePosition(Math.floor(currentSecond / 10));
                  // Only update these timestamps on actual interval changes, not every update
                  if (data.data.scheduler.current_interval !== undefined && data.data.scheduler.current_interval !== systemState.scheduler.current_interval) {
                    lastIntervalUpdateTime.current = Date.now();
                  }
                }
                
                // Check for scene completion
                if (
                  data.data.scheduler.current_interval === data.data.scheduler.total_intervals - 1 &&
                  lastCompletionLog !== data.data.scheduler.current_interval
                ) {
                  logBasic("Scene completed");
                  setLastCompletionLog(data.data.scheduler.current_interval);
                  if (data.data.scheduler.status === "completed") {
                    updateScheduler({ status: "idle" });
                  }
                }
              }
              
              // Update devices if provided
              if (data.data.connected_devices) {
                updateDevices(data.data.connected_devices);
              }
              
              // Clear is_manual_override if the timer triggers a system state change
              if (data.data.isSystemOn !== undefined && data.data.isSystemOn !== systemState.isSystemOn && isTimerEnabled) {
                updateSystemState({ is_manual_override: false });
              }
              
              // Update local CCT and intensity for UI display (explicit undefined checks for falsy values)
              if (data.data.current_cct !== undefined) setLocalCct(data.data.current_cct);
              if (data.data.current_intensity !== undefined) setLocalIntensity(data.data.current_intensity);
              //logBasic(`Processed live_update: isTimerEnabled=${data.data.isTimerEnabled}`);
          }
        } catch (err) {
          console.error("WebSocket parsing error:", err, "Raw message:", event.data);
          logAdvanced(`WebSocket parsing error: ${err}`);
          setState((prev) => ({ ...prev, error: `Failed to parse WebSocket message: ${err}` }));
        } finally {
          setIsLoading(false);
        }
      };
      ws.current.onclose = () => {
        logAdvanced("WebSocket disconnected");
        setState((prev) => ({ ...prev, wsLatency: null, error: "WebSocket connection lost" }));
        setIsLoading(false);
        if (reconnectAttempts < maxReconnectAttempts) {
          const backoff = Math.min(1000 * Math.pow(2, reconnectAttempts), maxBackoff);
          logAdvanced(`Attempting to reconnect in ${backoff / 1000} seconds (Attempt ${reconnectAttempts + 1}/${maxReconnectAttempts})`);
          reconnectTimeout = setTimeout(() => {
            reconnectAttempts++;
            connectWebSocket();
          }, backoff);
        } else {
          logAdvanced("Max reconnection attempts reached. Please refresh the page.");
          setState((prev) => ({ ...prev, error: "Failed to reconnect to WebSocket. Please refresh the page." }));
        }
      };
      ws.current.onerror = () => {
        console.error("WebSocket error occurred");
        logAdvanced("WebSocket error occurred");
        setState((prev) => ({ ...prev, error: "WebSocket error occurred" }));
        setIsLoading(false);
      };
    };
    connectWebSocket();
    return () => {
      if (ws.current) {
        if (ws.current.pingInterval) {
          clearInterval(ws.current.pingInterval);
        }
        ws.current.close();
        ws.current = null;
      }
      if (reconnectTimeout) {
        clearTimeout(reconnectTimeout);
      }
      if (animationFrameId.current) {
        cancelAnimationFrame(animationFrameId.current);
      }
      if (previewTimeout.current) {
        clearTimeout(previewTimeout.current);
      }
    };
  }, [logAdvanced, logBasic]);

  useEffect(() => {
    if (systemState.isSystemOn) {
      const currentSecond = getCurrentSecondOfDay()
      setVerticalLinePosition(Math.floor(currentSecond / 10) % 8640)
      animationFrameId.current = requestAnimationFrame(animateVerticalLine)
    } else {
      if (animationFrameId.current) {
        cancelAnimationFrame(animationFrameId.current)
      }
      setVerticalLinePosition(0)
    }
    return () => {
      if (animationFrameId.current) {
        cancelAnimationFrame(animationFrameId.current)
      }
    }
  }, [systemState.isSystemOn, systemState.auto_mode, animateVerticalLine])

  const filteredDevices = useMemo(() => {
    if (!deviceSearchQuery) return Object.entries(devices)
    return Object.entries(devices).filter(([ip]) => {
      const searchLower = deviceSearchQuery.toLowerCase()
      return ip.toLowerCase().includes(searchLower)
    })
  }, [devices, deviceSearchQuery])

  const chartData = useMemo(() => {
    const centerPosition = systemState.auto_mode ? verticalLinePosition : 4320
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
        ...(systemState.isSystemOn
          ? [
              {
                label: "current CCT",
                data: (localCct ?? systemState.current_cct)
                  ? systemState.auto_mode
                    ? [{ x: centerPosition, y: localCct ?? systemState.current_cct }]
                    : [
                        { x: 0, y: localCct ?? systemState.current_cct },
                        { x: 8640, y: localCct ?? systemState.current_cct },
                      ]
                  : [],
                borderColor: annotationColor,
                backgroundColor: annotationColor,
                pointStyle: systemState.auto_mode ? "circle" : false,
                pointRadius: systemState.auto_mode ? 7 : 0,
                pointHoverRadius: systemState.auto_mode ? 9 : 0,
                showLine: !systemState.auto_mode,
                borderWidth: systemState.auto_mode ? 0 : 2,
                tension: 0,
              },
            ]
          : []),
      ],
    }
  }, [sceneData.cct, systemState.isSystemOn, systemState.current_cct, localCct, theme, verticalLinePosition, systemState.auto_mode])

  const intensityChartData = useMemo(() => {
    const centerPosition = systemState.auto_mode ? verticalLinePosition : 4320
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
        ...(systemState.isSystemOn
          ? [
              {
                label: "current intensity",
                data: (localIntensity ?? systemState.current_intensity)
                  ? systemState.auto_mode
                    ? [{ x: centerPosition, y: localIntensity ?? systemState.current_intensity }]
                    : [
                        { x: 0, y: localIntensity ?? systemState.current_intensity },
                        { x: 8640, y: localIntensity ?? systemState.current_intensity },
                      ]
                  : [],
                borderColor: annotationColor,
                backgroundColor: annotationColor,
                pointStyle: systemState.auto_mode ? "circle" : false,
                pointRadius: systemState.auto_mode ? 7 : 0,
                pointHoverRadius: systemState.auto_mode ? 9 : 0,
                showLine: !systemState.auto_mode,
                borderWidth: systemState.auto_mode ? 0 : 2,
                tension: 0,
              },
            ]
          : []),
      ],
    }
  }, [sceneData.intensity, systemState.isSystemOn, systemState.current_intensity, localIntensity, theme, verticalLinePosition, systemState.auto_mode])

  const chartOptions = useMemo(
    () => ({
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        plotAreaBackground: plotAreaBackgroundPlugin,
        currentValueLabel: {
          text: `Current CCT: ${(localCct ?? systemState.current_cct).toFixed(1)}K`,
        },
        title: {
          display: true,
          text: "CCT PROFILE",
          color: theme === "dark" ? "#E6E6E6" : "#1A1A1A",
          font: { family: "SF Pro Display, system-ui, sans-serif", size: 18, weight: "600" },
          padding: { bottom: 12, top: 8 },
        },
        legend: {
          display: false,
        },
        annotation: {
          annotations: {
            verticalLine: {
              type: "line",
              xMin: verticalLinePosition,
              xMax: verticalLinePosition,
              borderColor: theme === "dark" ? "rgba(255, 69, 58, 0.7)" : "#FF3B30",
              borderWidth: 2,
            },
          },
        },
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
              if (label.includes("CCT")) {
                return `${label}: ${value.toFixed(1)}K`
              } else if (label.includes("Intensity")) {
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
              const totalMinutes = Math.floor((value * 10) / 60)
              const hours = Math.floor(totalMinutes / 60)
              if (value === 8640) {
                return "24:00"
              }
              return `${hours % 24}:00`
            },
          },
          grid: {
            color: theme === "dark" ? "rgba(75, 85, 99, 0.2)" : "rgba(226, 232, 240, 0.4)",
            lineWidth: 0.5,
            display: true,
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
            padding: { bottom: 8 },
          },
          ticks: {
            stepSize: 500,
            color: theme === "dark" ? "#A3A3A3" : "#8A8A8A",
            font: { family: "SF Pro Display, system-ui, sans-serif", size: 12 },
          },
          grid: {
            color: theme === "dark" ? "rgba(75, 85, 99, 0.2)" : "rgba(226, 232, 240, 0.4)",
            lineWidth: 0.5,
          },
        },
      },
    }),
    [theme, verticalLinePosition, systemState.auto_mode, systemState.isSystemOn, systemState.current_cct, localCct]
  )

  const intensityChartOptions = useMemo(
    () => ({
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        plotAreaBackground: plotAreaBackgroundPlugin,
        currentValueLabel: {
          text: `Current Intensity: ${(localIntensity ?? systemState.current_intensity).toFixed(1)} lux`,
        },
        title: {
          display: true,
          text: "INTENSITY PROFILE",
          color: theme === "dark" ? "#E6E6E6" : "#1A1A1A",
          font: { family: "SF Pro Display, system-ui, sans-serif", size: 18, weight: "600" },
          padding: { bottom: 12, top: 8 },
        },
        legend: {
          display: false,
        },
        annotation: {
          annotations: {
            verticalLine: {
              type: "line",
              xMin: verticalLinePosition,
              xMax: verticalLinePosition,
              borderColor: theme === "dark" ? "rgba(255, 69, 58, 0.7)" : "#FF3B30",
              borderWidth: 2,
            },
          },
        },
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
              if (label.includes("CCT")) {
                return `${label}: ${value.toFixed(1)}K`
              } else if (label.includes("Intensity")) {
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
              const totalMinutes = Math.floor((value * 10) / 60)
              const hours = Math.floor(totalMinutes / 60)
              if (value === 8640) {
                return "24:00"
              }
              return `${hours % 24}:00`
            },
          },
          grid: {
            color: theme === "dark" ? "rgba(75, 85, 99, 0.2)" : "rgba(226, 232, 240, 0.4)",
            lineWidth: 0.5,
            display: true,
          },
        },
        y: {
          min: 0,
          max: 700,
          title: {
            display: true,
            text: "Intensity (lux)",
            color: theme === "dark" ? "#A3A3A3" : "#666666",
            font: { family: "SF Pro Display, system-ui, sans-serif", size: 14, weight: "500" },
            padding: { bottom: 8 },
          },
          ticks: {
            stepSize: 100,
            color: theme === "dark" ? "#A3A3A3" : "#8A8A8A",
            font: { family: "SF Pro Display, system-ui, sans-serif", size: 12 },
          },
          grid: {
            color: theme === "dark" ? "rgba(75, 85, 99, 0.2)" : "rgba(226, 232, 240, 0.4)",
            lineWidth: 0.5,
          },
        },
      },
    }),
    [theme, verticalLinePosition, systemState.auto_mode, systemState.isSystemOn, systemState.current_intensity, localIntensity]
  )

  const monitoringDisplay = useMemo(() => {
    const timestamp = new Date().toLocaleTimeString()
    return `CCT: ${systemState.current_cct.toFixed(0)}K, Intensity: ${systemState.current_intensity.toFixed(0)}lux, ${timestamp}`
  }, [systemState.current_cct, systemState.current_intensity])

  const intervalProgressPercent = useMemo(() => {
    console.log('[Progress Bar] useMemo recalculating, systemState.scheduler:', systemState.scheduler);
    // When system is off, always show 0%
    if (!systemState.isSystemOn) {
      console.log('[Progress Bar] System is OFF, returning 0.0');
      return "0.0"
    }
    // Use backend-provided interval_progress (percentage 0-100) directly instead of calculating locally
    if (systemState.scheduler.interval_progress !== undefined) {
      const value = systemState.scheduler.interval_progress.toFixed(1);
      console.log('[Progress Bar] Using backend interval_progress:', value);
      return value;
    }
    // Fallback to local calculation if backend doesn't provide it
    if (systemState.scheduler.total_intervals === 0) {
      console.log('[Progress Bar] Fallback: total_intervals is 0, returning 0.0');
      return "0.0";
    }
    const calculated = (((systemState.scheduler.current_interval + 1) / systemState.scheduler.total_intervals) * 100).toFixed(1);
    console.log('[Progress Bar] Fallback: calculated locally:', calculated);
    return calculated;
  }, [systemState.isSystemOn, systemState.scheduler.interval_progress, systemState.scheduler.current_interval, systemState.scheduler.total_intervals])

  const scenecurrent = (systemState.isSystemOn && systemState.current_scene) ? systemState.current_scene.slice(0, -4) : "None"
  const sceneload = (systemState.isSystemOn && systemState.loaded_scene) ? systemState.loaded_scene.slice(0, -4) : "None"

  return (
    <div className={`luminaire-dashboard ${theme}-theme`}>
      <Toaster
        position="top-right"
        toastOptions={{
          duration: 3000,
          style: {
            background: theme === "dark" ? "#232F3E" : "#FFFFFF",
            color: theme === "dark" ? "#E6E6E6" : "#1A1A1A",
            border: `1px solid ${theme === "dark" ? "#4B5563" : "#E0E0E0"}`,
            borderRadius: "8px",
            boxShadow: "0 4px 12px rgba(0, 0, 0, 0.15)",
          },
          success: {
            iconTheme: {
              primary: theme === "dark" ? "#34D399" : "#10B981",
              secondary: theme === "dark" ? "#E6E6E6" : "#FFFFFF",
            },
          },
          error: {
            iconTheme: {
              primary: theme === "dark" ? "#EF4444" : "#DC2626",
              secondary: theme === "dark" ? "#E6E6E6" : "#FFFFFF",
            },
          },
        }}
      />
      {state.error && (
        <div className="error-banner" role="alert">
          <AlertCircle size={20} />
          <span>{state.error}</span>
        </div>
      )}
      <header className="dashboard-header">
        <div className="header-left">
          <img src={logo} alt="Company Logo" className="company-logo" style={{ height: "60px", marginRight: "0px" }} />
          <h1 className="dashboard-title">Luminaire Control System</h1>
        </div>
        <div className="header-right">
          <div className="system-toggle">
            <span className="toggle-label">System</span>
            <label className="switch">
              <input type="checkbox" checked={systemState.isSystemOn} onChange={toggleSystem} aria-label="Toggle System" />
              <span className="slider round"></span>
            </label>
          </div>
          <button className="icon-button theme-toggle" onClick={toggleTheme} aria-label="Toggle Theme">
            {theme === "dark" ? <Sun size={20} /> : <Moon size={20} />}
          </button>
        </div>
      </header>
      <main className="dashboard-content">
        <section className="charts-container">
          <div className="chart-card">
            {isLoading && (
              <div className="loading-overlay">
                <FaSyncAlt className="loading-spinner" />
              </div>
            )}
            <Line 
              data={chartData}
              options={chartOptions}
            />
          </div>
          <div className="chart-card">
            {isLoading && (
              <div className="loading-overlay">
                <FaSyncAlt className="loading-spinner" />
              </div>
            )}
            <Line 
              data={intensityChartData}
              options={intensityChartOptions}
            />
          </div>
        </section>
        <section className="dashboard-grid">
          <div className="card control-card">
            <div className="card-header">
              <h2 className="card-title">
                <Sliders size={22} className="card-icon" />
                Control Panel
              </h2>
            </div>
            <div className="card-content">
              <div className="control-row">
                <div className={`mode-toggle-container ${!systemState.isSystemOn ? "disabled" : ""}`}>
                  <label
                    className={`mode-label ${!systemState.auto_mode ? "active-mode" : ""}`}
                    onClick={() => systemState.isSystemOn && setMode(false)}
                  >
                    Manual
                  </label>
                  <label className="switch">
                    <input
                      type="checkbox"
                      checked={systemState.auto_mode}
                      onChange={(e) => setMode(e.target.checked)}
                      disabled={!systemState.isSystemOn}
                    />
                  </label>
                  <label
                    className={`mode-label ${systemState.auto_mode ? "active-mode" : ""}`}
                    onClick={() => systemState.isSystemOn && setMode(true)}
                  >
                    Auto
                  </label>
                </div>
              </div>
              {systemState.auto_mode && (
                <div className="control-row">
                  <div className="control-group">
                    <div className="control-label">Scene Selection</div>
                    <select
                      value={systemState.loaded_scene || ""}
                      onChange={(e) => loadScene(e.target.value)}
                      disabled={!systemState.isSystemOn || !systemState.auto_mode}
                      className="select-input"
                    >
                      <option value="">Select Scene</option>
                      {systemState.available_scenes.map((scene) => (
                        <option key={scene} value={scene}>
                          {scene}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="scene-status-container">
                    <div className="status-label">Loaded {sceneload}, Running {scenecurrent}</div>
                    <div className="status-badges">
                      {systemState.scheduler.status === "idle" && (
                        <div className="status-badge idle">
                          <FaExclamationTriangle size={25} />
                          <span>Idle</span>
                        </div>
                      )}
                      {systemState.scheduler.status === "pending" && (
                        <div className="status-badge pending">
                          <FaExclamationTriangle size={25} />
                          <span>Pending</span>
                        </div>
                      )}
                      {systemState.scheduler.status === "running" && (
                        <div className="status-badge running">
                          <FaCheckCircle size={28} />
                          <span>Running {scenecurrent} - {intervalProgressPercent}%</span>
                        </div>
                      )}
                      {systemState.scheduler.status === "completed" && (
                        <div className="status-badge completed">
                          <FaExclamationTriangle size={25} />
                          <span>Completed</span>
                        </div>
                      )}
                      {systemState.scheduler.status === "stopped" && (
                        <div className="status-badge stopped">
                          <FaStop size={25} />
                          <span>Stopped</span>
                        </div>
                      )}
                    </div>
                    {systemState.scheduler.status === "running" && systemState.scheduler.total_intervals > 0 && (
                      <div className="progress-container">
                        <div
                          className="progress-bar"
                          style={{ width: `${intervalProgressPercent}%` }}
                          role="progressbar"
                          aria-valuenow={intervalProgressPercent}
                          aria-valuemin="0"
                          aria-valuemax="100"
                        />
                      </div>
                    )}
                  </div>
                  <div className="scene-actions">
                    <button
                      onClick={activateScene}
                      disabled={!systemState.isSystemOn || !systemState.auto_mode || !systemState.loaded_scene}
                      className="control-button primary"
                    >
                      <FaPlay size={30} />
                      <span>Activate</span>
                    </button>
                    <button
                      onClick={stopScheduler}
                      disabled={
                        !systemState.isSystemOn ||
                        !systemState.auto_mode ||
                        !systemState.current_scene ||
                        systemState.scheduler.status === "idle"
                      }
                      className="control-button secondary"
                    >
                      <FaStop size={30} />
                      <span>Deactivate</span>
                    </button>
                  </div>
                </div>
              )}
              {!systemState.auto_mode && (
                <>
                  <div className="control-row">
                    <div className="control-group">
                      <div className="control-label">
                        <Thermometer size={24} />
                        <span>Color Temperature</span>
                      </div>
                      <div className="slider-container">
                        <input
                          type="range"
                          min="3500"
                          max="6500"
                          step="50"
                          value={localCct !== null ? localCct : systemState.current_cct}
                          onInput={handleCctChange}
                          onChange={handleCctChange}
                          disabled={systemState.auto_mode || !systemState.isSystemOn}
                          className="range-slider"
                        />
                        <div className="slider-value">
                          {localCct !== null ? localCct.toFixed(0) : systemState.current_cct.toFixed(0)} K
                        </div>
                      </div>
                    </div>
                  </div>
                  <div className="control-row">
                    <div className="control-group">
                      <div className="control-label">
                        <Sun size={24} />
                        <span>Intensity</span>
                      </div>
                      <div className="slider-container">
                        <input
                          type="range"
                          min="0"
                          max="500"
                          step="10"
                          value={localIntensity !== null ? localIntensity : systemState.current_intensity}
                          onInput={handleIntensityChange}
                          onChange={handleIntensityChange}
                          disabled={systemState.auto_mode || !systemState.isSystemOn}
                          className="range-slider intensity-slider"
                        />
                        <div className="slider-value">
                          {localIntensity !== null ? localIntensity.toFixed(0) : systemState.current_intensity.toFixed(0)} lux
                        </div>
                      </div>
                    </div>
                  </div>
                  <div className="control-row">
                    <div className="balance-container">
                      <div className="balance-item">
                        <span className="balance-label">Cool White</span>
                        <div className="balance-value">{systemState.cw.toFixed(1)}%</div>
                        <div className="balance-buttons">
                          <button
                            onClick={() => adjustLight("cw", systemState.cw - 1)}
                            disabled={systemState.auto_mode || !systemState.isSystemOn}
                            className="control-button medium"
                          >
                            -
                          </button>
                          <button
                            onClick={() => adjustLight("cw", systemState.cw + 1)}
                            disabled={systemState.auto_mode || !systemState.isSystemOn}
                            className="control-button medium"
                          >
                            +
                          </button>
                        </div>
                      </div>
                      <div className="balance-item">
                        <span className="balance-label">Warm White</span>
                        <div className="balance-value">{systemState.ww.toFixed(1)}%</div>
                        <div className="balance-buttons">
                          <button
                            onClick={() => adjustLight("ww", systemState.ww - 1)}
                            disabled={systemState.auto_mode || !systemState.isSystemOn}
                            className="control-button medium"
                          >
                            -
                          </button>
                          <button
                            onClick={() => adjustLight("ww", systemState.ww + 1)}
                            disabled={systemState.auto_mode || !systemState.isSystemOn}
                            className="control-button medium"
                          >
                            +
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                </>
              )}
            </div>
          </div>
          <div className="card status-card">
            <div className="card-header">
              <h2 className="card-title">
                <BarChart2 size={22} className="card-icon" />
                Status, Timer & Logs
              </h2>
            </div>
            <div className="card-content">
              <div className="performance-metrics-container">
                <div className="performance-metric">
                  <Radio size={32} />
                  <div className="metric-details">
                    <div className="metric-label">Latency</div>
                    <div className="metric-value">{state.wsLatency !== null ? `${state.wsLatency}ms` : "N/A"}</div>
                  </div>
                </div>
                <div className="performance-metric">
                  <Cpu size={32} />
                  <div className="metric-details">
                    <div className="metric-label">CPU</div>
                    <div className="metric-value">{systemState.cpu_percent.toFixed(1)}%</div>
                  </div>
                </div>
                <div className="performance-metric">
                  <Memory size={32} />
                  <div className="metric-details">
                    <div className="metric-label">Memory</div>
                    <div className="metric-value">{systemState.mem_percent.toFixed(1)}%</div>
                  </div>
                </div>
                <div className="performance-metric">
                  <Thermometer size={32} />
                  <div className="metric-details">
                    <div className="metric-label">Temperature</div>
                    <div className="metric-value">{systemState.temperature !== null ? `${systemState.temperature.toFixed(1)}°C` : "N/A"}</div>
                  </div>
                </div>
              </div>
              <div className="status-display">
                <div className="status-icon">
                  {systemState.isSystemOn ? (
                    <div className="status-icon-active">
                      <Zap size={30} />
                    </div>
                  ) : (
                    <div className="status-icon-inactive">
                      <AlertCircle size={24} />
                    </div>
                  )}
                </div>
                <div className="status-info">
                  <div className="status-primary">{systemState.isSystemOn ? "System Active" : "System Inactive"}</div>
                  <div className="status-secondary">{monitoringDisplay}</div>
                </div>
              </div>
              <div className="timer-control">
                <div className="timer-header">
                  <div className="timer-title">
                    <Clock size={20} />
                    <span>System Timer</span>
                  </div>
                  <div className="timer-toggle-wrapper">
                    <div className="timer-toggle-tabs" role="tablist" aria-label="Timer toggle">
                      <button
                        className={`timer-toggle-tab ${isTimerEnabled ? "active" : ""}`}
                        onClick={() => handleTimerToggle(true)}
                        role="tab"
                        aria-selected={isTimerEnabled}
                        aria-label="Enable timer"
                      >
                        Enabled
                      </button>
                      <button
                        className={`timer-toggle-tab ${!isTimerEnabled ? "active" : ""}`}
                        onClick={() => handleTimerToggle(false)}
                        role="tab"
                        aria-selected={!isTimerEnabled}
                        aria-label="Disable timer"
                      >
                        Disabled
                      </button>
                    </div>
                  </div>
                </div>
                  <div className="timer-inputs">
                    <div className="time-input-group">
                      <label htmlFor="onTime">On Time</label>
                      <input
                        id="onTime"
                        type="time"
                        value={onTime}
                        onChange={(e) => handleTimeChange(e, "on")}
                        disabled={!isTimerEnabled}
                        className={`time-input ${onTime && offTime && onTime === offTime ? "invalid" : ""}`}
                        aria-disabled={!isTimerEnabled}
                      />
                    </div>
                    <div className="time-input-group">
                      <label htmlFor="offTime">Off Time</label>
                      <input
                        id="offTime"
                        type="time"
                        value={offTime}
                        onChange={(e) => handleTimeChange(e, "off")}
                        disabled={!isTimerEnabled}
                        className={`time-input ${onTime && offTime && onTime === offTime ? "invalid" : ""}`}
                        aria-disabled={!isTimerEnabled}
                      />
                    </div>
                    <div className="set-button-group">
                      <label>&nbsp;</label>
                      <button
                        className="set-timer-button"
                        onClick={handleSetTimer}
                        disabled={!isTimerEnabled}
                        aria-label="Set timer"
                      >
                        Set
                      </button>
                    </div>
                  </div>
                </div>
                  {(onTime || offTime) && (
                    <div className="current-timers">
                      <strong>Current Timers:</strong>
                      <ul>
                        <li>On: {onTime || "Not set"}, Off: {offTime || "Not set"}</li>
                      </ul>
                    </div>
                  )}
            </div>
              {/* Logs button removed for performance - UI completely eliminated */}
            </div>
          <div className="card devices-card">
            <div className="card-header">
              <h2 className="card-title">
                <Network size={22} className="card-icon" />
                Connected Luminaires
              </h2>
              <button className="icon-button search-toggle" onClick={toggleSearchBar} aria-label="Toggle Search">
                <Search size={16} />
              </button>
            </div>
            <div className="card-content">
              {isSearchVisible && (
                <div className="control-row">
                  <div className="search-input-wrapper">
                    <Search size={16} className="search-icon" />
                    <input
                      type="text"
                      placeholder="Search luminaires..."
                      value={deviceSearchQuery}
                      onChange={handleDeviceSearchChange}
                      className="device-search-input"
                      autoFocus
                    />
                  </div>
                </div>
              )}
              <ul className="device-list">
                {filteredDevices.length > 0 ? (
                  filteredDevices.map(([ip, data]) => (
                    <DeviceItem key={ip} ip={ip} data={data} />
                  ))
                ) : (
                  <li className="no-devices">No luminaires found</li>
                )}
              </ul>
              <div className="device-summary">
                {deviceSearchQuery
                  ? `Showing ${filteredDevices.length} of ${Object.keys(devices).length} luminaires`
                  : `Total Luminaires: ${Object.keys(devices).length}`}
              </div>
            </div>
          </div>
        </section>
      </main>
      {/* Logs panel completely removed for performance optimization */}
      {/* Log functionality can be re-enabled by uncommenting LogContext and restoring logs UI */}
    </div>
  )
}

export default App