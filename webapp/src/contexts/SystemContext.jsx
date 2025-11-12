import { createContext, useContext, useState, useCallback } from "react"

const SystemContext = createContext()

export const useSystem = () => {
  const context = useContext(SystemContext)
  if (!context) {
    throw new Error("useSystem must be used within a SystemProvider")
  }
  return context
}

export const SystemProvider = ({ children }) => {
  const [systemState, setSystemState] = useState({
    auto_mode: false,
    available_scenes: [],
    current_scene: null,
    loaded_scene: null,
    cw: 50.0,
    ww: 50.0,
    scheduler: {
      current_cct: 3500,
      current_interval: 0,
      total_intervals: 8640,
      interval_seconds: 1.0,
      status: "idle",
    },
    scene_data: { cct: [], intensity: [] },
    isSystemOn: true,
    is_manual_override: false,
    current_cct: 3500,
    current_intensity: 250,
    cpu_percent: 0.0,
    mem_percent: 0.0,
    temperature: null,
    wsLatency: null,
    system_timers: [],
  })

  const updateSystemState = useCallback((updates) => {
    setSystemState((prev) => ({
      ...prev,
      ...updates,
    }))
  }, [])

  const updateScheduler = useCallback((schedulerUpdates) => {
    setSystemState((prev) => ({
      ...prev,
      scheduler: {
        ...prev.scheduler,
        ...schedulerUpdates,
      },
    }))
  }, [])

  const resetSystemState = useCallback(() => {
    setSystemState({
      auto_mode: false,
      available_scenes: [],
      current_scene: null,
      loaded_scene: null,
      cw: 50.0,
      ww: 50.0,
      scheduler: {
        current_cct: 3500,
        current_interval: 0,
        total_intervals: 8640,
        interval_seconds: 1.0,
        status: "idle",
      },
      scene_data: { cct: [], intensity: [] },
      isSystemOn: true,
      is_manual_override: false,
      current_cct: 3500,
      current_intensity: 250,
      cpu_percent: 0.0,
      mem_percent: 0.0,
      temperature: null,
      wsLatency: null,
      system_timers: [],
    })
  }, [])

  return (
    <SystemContext.Provider
      value={{
        systemState,
        updateSystemState,
        updateScheduler,
        resetSystemState,
      }}
    >
      {children}
    </SystemContext.Provider>
  )
}
