import { FileText } from "lucide-react"

const LogsPanel = ({ isLogsPanelOpen, setIsLogsPanelOpen, activeLogTab, setActiveLogTab, basicLogs, advancedLogs }) => {
  return (
    <div className={`logs-panel ${isLogsPanelOpen ? "open" : ""}`}>
      <div className="logs-panel-header">
        <h2 className="logs-panel-title">
          <FileText size={22} className="card-icon" />
          System Logs
        </h2>
        <button
          className="icon-button close-logs"
          onClick={() => setIsLogsPanelOpen(false)}
          aria-label="Close logs panel"
        >
          ✕
        </button>
      </div>
      <div className="logs-panel-content">
        <div className="log-tabs">
          <button
            className={`log-tab ${activeLogTab === "basic" ? "active" : ""}`}
            onClick={() => setActiveLogTab("basic")}
            role="tab"
            aria-selected={activeLogTab === "basic"}
            aria-label="Basic logs"
          >
            Basic
          </button>
          <button
            className={`log-tab ${activeLogTab === "advanced" ? "active" : ""}`}
            onClick={() => setActiveLogTab("advanced")}
            role="tab"
            aria-selected={activeLogTab === "advanced"}
            aria-label="Advanced logs"
          >
            Advanced
          </button>
        </div>
        <div className="log-content">
          {activeLogTab === "basic" ? (
            <div className="log-list">
              {basicLogs.length > 0 ? (
                basicLogs.map((log, index) => (
                  <div key={index} className="log-entry">{log}</div>
                ))
              ) : (
                <div className="no-logs">No basic logs available</div>
              )}
            </div>
          ) : (
            <div className="log-list">
              {advancedLogs.length > 0 ? (
                advancedLogs.map((log, index) => (
                  <div key={index} className="log-entry">{log}</div>
                ))
              ) : (
                <div className="no-logs">No advanced logs available</div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default LogsPanel