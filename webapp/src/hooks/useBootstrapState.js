import { useEffect } from "react"
import { useDevices } from "../contexts/DeviceContext"
import { useSystem } from "../contexts/SystemContext"

/**
 * Custom hook to bootstrap initial state from REST APIs on app load.
 * Fetches devices, system state, timers, and optionally logs before switching to live updates.
 * Uses dynamic URL based on window.location for cross-IP and container access.
 */
export const useBootstrapState = () => {
  const { updateDevices } = useDevices()
  const { updateSystemState } = useSystem()

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
            console.log("Bootstrapped devices:", devicesData.devices)
            updateDevices(devicesData.devices)
          }
        } else {
          console.warn("Failed to fetch initial devices:", devicesResponse.status)
        }
      } catch (error) {
        console.error("Error bootstrapping devices:", error)
      }

      try {
        // Fetch available scenes
        const scenesResponse = await fetch(`${apiBaseUrl}/api/available_scenes`)
        if (scenesResponse.ok) {
          const scenesData = await scenesResponse.json()
          if (Array.isArray(scenesData.available_scenes)) {
            console.log("Bootstrapped available scenes:", scenesData.available_scenes)
            updateSystemState({ available_scenes: scenesData.available_scenes })
          }
        } else {
          console.warn("Failed to fetch available scenes:", scenesResponse.status)
        }
      } catch (error) {
        console.error("Error bootstrapping scenes:", error)
      }

      try {
        // Fetch timers from /api/timers endpoint
        const timersResponse = await fetch(`${apiBaseUrl}/api/timers`)
        if (timersResponse.ok) {
          const timersData = await timersResponse.json()
          if (Array.isArray(timersData.timers)) {
            console.log("Bootstrapped timers:", timersData.timers)
            updateSystemState({ 
              system_timers: timersData.timers,
              isTimerEnabled: timersData.isTimerEnabled 
            })
          }
        } else {
          console.warn("Failed to fetch timers:", timersResponse.status)
        }
      } catch (error) {
        console.error("Error bootstrapping timers:", error)
      }

      // Note: System state and logs will be populated via WebSocket live_update and log_update
      console.log("State bootstrap complete - switching to live WebSocket updates")
    }

    bootstrapState()
  }, [updateDevices, updateSystemState])
}
