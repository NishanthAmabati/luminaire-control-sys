import { createContext, useContext, useState, useCallback } from "react"

const DeviceContext = createContext()

export const useDevices = () => {
  const context = useContext(DeviceContext)
  if (!context) {
    throw new Error("useDevices must be used within a DeviceProvider")
  }
  return context
}

export const DeviceProvider = ({ children }) => {
  const [devices, setDevices] = useState({})

  const updateDevice = useCallback((ip, deviceData) => {
    setDevices((prev) => ({
      ...prev,
      [ip]: {
        ...prev[ip],
        ...deviceData,
        connected: deviceData.connected !== undefined ? deviceData.connected : (prev[ip]?.connected ?? false),
      },
    }))
  }, [])

  const updateDevices = useCallback((devicesData) => {
    setDevices((prev) => {
      if (Array.isArray(devicesData)) {
        const obj = {}
        devicesData.forEach(d => { if(d.ip) obj[d.ip] = d })
        return { ...prev, ...obj }
      }
      return { ...prev, ...devicesData }
    })
  }, [])

  const clearDevices = useCallback(() => setDevices({}), [])

  return (
    <DeviceContext.Provider value={{ devices, updateDevice, updateDevices, clearDevices }}>
      {children}
    </DeviceContext.Provider>
  )
}