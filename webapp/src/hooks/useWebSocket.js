import { useEffect, useRef } from "react"
import { useDevices } from "../contexts/DeviceContext"
import { useSystem } from "../contexts/SystemContext"
import { useLogs } from "../contexts/LogContext"

/**
 * Custom hook for WebSocket management with the refactored backend.
 * Subscribes to device_update, system_update, and log_update channels.
 */
export const useWebSocket = (url, onError) => {
  const ws = useRef(null)
  const { updateDevice, updateDevices } = useDevices()
  const { updateSystemState, updateScheduler } = useSystem()
  const { addBasicLog, addAdvancedLog } = useLogs()
  const lastPingTime = useRef(0)
  const reconnectAttempts = useRef(0)
  const maxReconnectAttempts = 10
  const maxBackoff = 32000

  useEffect(() => {
    let reconnectTimeout = null
    let pingInterval = null

    const connectWebSocket = () => {
      console.log("Connecting to WebSocket:", url)
      ws.current = new WebSocket(url)

      ws.current.onopen = () => {
        console.log("WebSocket Connected")
        addAdvancedLog("[WebSocket] Connected")
        reconnectAttempts.current = 0

        // Start ping interval
        pingInterval = setInterval(() => {
          if (ws.current?.readyState === WebSocket.OPEN) {
            lastPingTime.current = Date.now()
            ws.current.send(JSON.stringify({ type: "ping" }))
          }
        }, 1000)
      }

      ws.current.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          console.log("WebSocket message received:", data)

          if (data.type === "pong") {
            const latency = Date.now() - lastPingTime.current
            updateSystemState({ wsLatency: latency })
          } else if (data.type === "device_update") {
            // Handle individual device update
            const deviceData = data.data
            if (deviceData.ip) {
              updateDevice(deviceData.ip, {
                cw: deviceData.cw,
                ww: deviceData.ww,
                connected: deviceData.connected,
                last_seen: deviceData.last_seen,
              })
            }
            // If full devices list is included, update all
            if (deviceData.devices) {
              updateDevices(deviceData.devices)
            }
          } else if (data.type === "system_update" || data.type === "live_update") {
            // Handle system state update
            const systemData = data.data
            const updates = {}

            if (systemData.current_cct !== undefined) updates.current_cct = systemData.current_cct
            if (systemData.current_intensity !== undefined) updates.current_intensity = systemData.current_intensity
            if (systemData.cw !== undefined) updates.cw = systemData.cw
            if (systemData.ww !== undefined) updates.ww = systemData.ww
            if (systemData.isSystemOn !== undefined) updates.isSystemOn = systemData.isSystemOn
            if (systemData.auto_mode !== undefined) updates.auto_mode = systemData.auto_mode
            if (systemData.current_scene !== undefined) updates.current_scene = systemData.current_scene
            if (systemData.loaded_scene !== undefined) updates.loaded_scene = systemData.loaded_scene
            if (systemData.available_scenes !== undefined) updates.available_scenes = systemData.available_scenes
            if (systemData.system_timers !== undefined) updates.system_timers = systemData.system_timers
            if (systemData.is_manual_override !== undefined) updates.is_manual_override = systemData.is_manual_override
            if (systemData.scene_data !== undefined) updates.scene_data = systemData.scene_data

            if (systemData.scheduler) {
              updateScheduler({
                status: systemData.scheduler.status,
                current_interval: systemData.scheduler.current_interval,
                total_intervals: systemData.scheduler.total_intervals,
                current_cct: systemData.scheduler.current_cct,
              })
            }

            updateSystemState(updates)
          } else if (data.type === "log_update") {
            // Handle log update - logs are arrays of plain strings
            const logData = data.data
            if (Array.isArray(logData.basicLogs)) {
              logData.basicLogs.forEach((log) => addBasicLog(log))
            }
            if (Array.isArray(logData.advancedLogs)) {
              logData.advancedLogs.forEach((log) => addAdvancedLog(log))
            }
          } else if (data.type === "system_stats") {
            // Handle system stats
            updateSystemState({
              cpu_percent: data.data.cpu_percent,
              mem_percent: data.data.mem_percent,
              temperature: data.data.temperature,
            })
          }
        } catch (err) {
          console.error("WebSocket parsing error:", err, "Raw message:", event.data)
          addAdvancedLog(`[WebSocket] Parsing error: ${err.message}`)
          if (onError) {
            onError(`Failed to parse WebSocket message: ${err.message}`)
          }
        }
      }

      ws.current.onclose = () => {
        console.log("WebSocket Disconnected")
        addAdvancedLog("[WebSocket] Disconnected")
        updateSystemState({ wsLatency: null })

        if (pingInterval) {
          clearInterval(pingInterval)
          pingInterval = null
        }

        // Attempt reconnection with exponential backoff
        if (reconnectAttempts.current < maxReconnectAttempts) {
          const backoff = Math.min(1000 * Math.pow(2, reconnectAttempts.current), maxBackoff)
          addAdvancedLog(
            `[WebSocket] Reconnecting in ${backoff / 1000}s (Attempt ${reconnectAttempts.current + 1}/${maxReconnectAttempts})`
          )
          reconnectTimeout = setTimeout(() => {
            reconnectAttempts.current++
            connectWebSocket()
          }, backoff)
        } else {
          addAdvancedLog("[WebSocket] Max reconnection attempts reached")
          if (onError) {
            onError("Failed to reconnect to WebSocket. Please refresh the page.")
          }
        }
      }

      ws.current.onerror = (error) => {
        console.error("WebSocket error:", error)
        addAdvancedLog("[WebSocket] Error occurred")
        if (onError) {
          onError("WebSocket error occurred")
        }
      }
    }

    connectWebSocket()

    // Cleanup function
    return () => {
      if (ws.current) {
        ws.current.close()
        ws.current = null
      }
      if (pingInterval) {
        clearInterval(pingInterval)
      }
      if (reconnectTimeout) {
        clearTimeout(reconnectTimeout)
      }
    }
  }, [url, updateDevice, updateDevices, updateSystemState, updateScheduler, addBasicLog, addAdvancedLog, onError])

  // Return WebSocket reference for sending commands
  return ws
}
