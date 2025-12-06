import { useEffect, useRef, useCallback } from "react"
import { useDevices } from "../contexts/DeviceContext"
import { useSystem } from "../contexts/SystemContext"

/**
 * Custom hook for WebSocket management with the refactored backend.
 * Subscribes to device_update, system_update, and log_update channels.
 * 
 * @param {string} url - WebSocket URL to connect to
 * @param {object} options - Configuration options
 * @param {function} options.onError - Error callback
 * @param {function} options.onConnect - Connection established callback
 * @param {function} options.onDisconnect - Disconnection callback
 * @param {function} options.onSceneData - Scene data update callback
 * @param {function} options.onTimerUpdate - Timer update callback
 * @returns {object} - { ws, sendCommand, isConnected }
 */
export const useWebSocket = (url, options = {}) => {
  const ws = useRef(null)
  const { updateDevice, updateDevices } = useDevices()
  const { systemState, updateSystemState, updateScheduler } = useSystem()
  
  const lastPingTime = useRef(0)
  const reconnectAttempts = useRef(0)
  const pingIntervalRef = useRef(null)
  const reconnectTimeoutRef = useRef(null)
  const isConnectedRef = useRef(false)
  
  const maxReconnectAttempts = 10
  const maxBackoff = 32000
  const pingInterval = 1000

  const {
    onError,
    onConnect,
    onDisconnect,
    onSceneData,
    onTimerUpdate,
    onLatencyUpdate,
    isAdjusting = false,
  } = options

  // Cleanup function
  const cleanup = useCallback(() => {
    if (pingIntervalRef.current) {
      clearInterval(pingIntervalRef.current)
      pingIntervalRef.current = null
    }
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }
  }, [])

  // Send command function
  const sendCommand = useCallback((command) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify(command))
      return true
    }
    return false
  }, [])

  useEffect(() => {
    const connectWebSocket = () => {
      console.log("Connecting to WebSocket:", url)
      
      try {
        ws.current = new WebSocket(url)
      } catch (error) {
        console.error("Failed to create WebSocket:", error)
        if (onError) {
          onError("Failed to create WebSocket connection")
        }
        return
      }

      ws.current.onopen = () => {
        console.log("WebSocket Connected")
        isConnectedRef.current = true
        reconnectAttempts.current = 0

        if (onConnect) {
          onConnect()
        }

        // Start ping interval
        pingIntervalRef.current = setInterval(() => {
          if (ws.current?.readyState === WebSocket.OPEN) {
            lastPingTime.current = Date.now()
            ws.current.send(JSON.stringify({ type: "ping" }))
          }
        }, pingInterval)
      }

      ws.current.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)

          if (data.type === "pong") {
            const latency = Date.now() - lastPingTime.current
            updateSystemState({ wsLatency: latency })
            if (onLatencyUpdate) {
              onLatencyUpdate(latency)
            }
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
            // Only update cw/ww if not currently adjusting sliders
            if (!isAdjusting && systemData.cw !== undefined) updates.cw = systemData.cw
            if (!isAdjusting && systemData.ww !== undefined) updates.ww = systemData.ww
            if (systemData.isSystemOn !== undefined) updates.isSystemOn = systemData.isSystemOn
            if (systemData.auto_mode !== undefined) updates.auto_mode = systemData.auto_mode
            if (systemData.current_scene !== undefined) updates.current_scene = systemData.current_scene
            if (systemData.loaded_scene !== undefined) updates.loaded_scene = systemData.loaded_scene
            if (systemData.available_scenes !== undefined) updates.available_scenes = systemData.available_scenes
            if (systemData.system_timers !== undefined) updates.system_timers = systemData.system_timers
            if (systemData.isTimerEnabled !== undefined) updates.isTimerEnabled = systemData.isTimerEnabled
            if (systemData.is_manual_override !== undefined) updates.is_manual_override = systemData.is_manual_override

            // Handle scene data separately if callback provided
            if (systemData.scene_data && onSceneData) {
              onSceneData(systemData.scene_data)
            }

            // Handle scheduler updates
            if (systemData.scheduler) {
              updateScheduler({
                status: systemData.scheduler.status,
                current_interval: systemData.scheduler.current_interval,
                total_intervals: systemData.scheduler.total_intervals,
                current_cct: systemData.scheduler.current_cct,
              })
            }

            updateSystemState(updates)
            
            // Handle timer update callback
            if (systemData.isTimerEnabled !== undefined && onTimerUpdate) {
              onTimerUpdate(systemData.isTimerEnabled, systemData.system_timers)
            }
          } else if (data.type === "system_stats" || data.type === "system_stats_update") {
            // Handle system stats (CPU, memory, temperature)
            updateSystemState({
              cpu_percent: data.data.cpu_percent ?? data.data.cpu,
              mem_percent: data.data.mem_percent ?? data.data.memory,
              temperature: data.data.temperature,
            })
          } else if (data.type === "command_ack") {
            console.log("Command acknowledged:", data.command)
          } else if (data.type === "command_error") {
            console.error("Command error:", data.error)
            if (onError) {
              onError(`Command failed: ${data.error}`)
            }
          }
        } catch (err) {
          console.error("WebSocket parsing error:", err, "Raw message:", event.data)
          if (onError) {
            onError(`Failed to parse WebSocket message: ${err.message}`)
          }
        }
      }

      ws.current.onclose = (event) => {
        console.log("WebSocket Disconnected", event.code, event.reason)
        isConnectedRef.current = false
        updateSystemState({ wsLatency: null })

        cleanup()

        if (onDisconnect) {
          onDisconnect()
        }

        // Attempt reconnection with exponential backoff
        if (reconnectAttempts.current < maxReconnectAttempts) {
          const backoff = Math.min(1000 * Math.pow(2, reconnectAttempts.current), maxBackoff)
          console.log(`Reconnecting in ${backoff / 1000}s (Attempt ${reconnectAttempts.current + 1}/${maxReconnectAttempts})`)
          reconnectTimeoutRef.current = setTimeout(() => {
            reconnectAttempts.current++
            connectWebSocket()
          }, backoff)
        } else {
          console.error("Max reconnection attempts reached")
          if (onError) {
            onError("Failed to reconnect to WebSocket. Please refresh the page.")
          }
        }
      }

      ws.current.onerror = (error) => {
        console.error("WebSocket error:", error)
        if (onError) {
          onError("WebSocket error occurred")
        }
      }
    }

    connectWebSocket()

    // Cleanup function on unmount
    return () => {
      cleanup()
      if (ws.current) {
        ws.current.close()
        ws.current = null
      }
    }
  }, [url]) // Intentionally minimal dependencies to avoid reconnection loops

  return { 
    ws, 
    sendCommand, 
    isConnected: isConnectedRef.current 
  }
}
