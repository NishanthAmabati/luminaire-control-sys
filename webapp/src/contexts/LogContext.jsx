import { createContext, useContext, useState, useCallback, useRef } from "react"

const LogContext = createContext()

const MAX_BASIC_LOGS = 500
const MAX_ADVANCED_LOGS = 500

export const useLogs = () => {
  const context = useContext(LogContext)
  if (!context) {
    throw new Error("useLogs must be used within a LogProvider")
  }
  return context
}

export const LogProvider = ({ children }) => {
  const [basicLogs, setBasicLogs] = useState([])
  const [advancedLogs, setAdvancedLogs] = useState([])
  const [autoScroll, setAutoScroll] = useState(true)
  const lastLogRef = useRef({ basic: null, advanced: null })

  const addBasicLog = useCallback((logMessage) => {
    // Deduplicate: avoid adding same log twice in a row
    if (lastLogRef.current.basic === logMessage) {
      return
    }
    lastLogRef.current.basic = logMessage
    setBasicLogs((prev) => {
      const updated = [...prev, logMessage]
      return updated.slice(-MAX_BASIC_LOGS)
    })
  }, [])

  const addAdvancedLog = useCallback((logMessage) => {
    // Deduplicate: avoid adding same log twice in a row
    if (lastLogRef.current.advanced === logMessage) {
      return
    }
    lastLogRef.current.advanced = logMessage
    setAdvancedLogs((prev) => {
      const updated = [...prev, logMessage]
      return updated.slice(-MAX_ADVANCED_LOGS)
    })
  }, [])

  const clearBasicLogs = useCallback(() => {
    setBasicLogs([])
    lastLogRef.current.basic = null
  }, [])

  const clearAdvancedLogs = useCallback(() => {
    setAdvancedLogs([])
    lastLogRef.current.advanced = null
  }, [])

  const clearAllLogs = useCallback(() => {
    setBasicLogs([])
    setAdvancedLogs([])
    lastLogRef.current = { basic: null, advanced: null }
  }, [])

  const toggleAutoScroll = useCallback(() => {
    setAutoScroll((prev) => !prev)
  }, [])

  return (
    <LogContext.Provider
      value={{
        basicLogs,
        advancedLogs,
        autoScroll,
        addBasicLog,
        addAdvancedLog,
        clearBasicLogs,
        clearAdvancedLogs,
        clearAllLogs,
        toggleAutoScroll,
      }}
    >
      {children}
    </LogContext.Provider>
  )
}
