import { useCallback } from "react"
import { Network, Search } from "lucide-react"

const DevicesCard = ({ state, deviceSearchQuery, setDeviceSearchQuery, isSearchVisible, setIsSearchVisible }) => {
  const handleDeviceSearchChange = useCallback((e) => {
    setDeviceSearchQuery(e.target.value)
  }, [setDeviceSearchQuery])

  const toggleSearchBar = useCallback(() => {
    setIsSearchVisible((prev) => !prev)
    if (isSearchVisible) setDeviceSearchQuery("")
  }, [isSearchVisible, setIsSearchVisible, setDeviceSearchQuery])

  const filteredDevices = Object.entries(state.connected_devices).filter(([id, device]) =>
    id.toLowerCase().includes(deviceSearchQuery.toLowerCase()) ||
    device.name.toLowerCase().includes(deviceSearchQuery.toLowerCase())
  )

  return (
    <div className="card device-card">
      <div className="card-header">
        <h2 className="card-title">
          <Network size={22} className="card-icon" />
          Connected Luminaires
        </h2>
        <button className="icon-button search-toggle" onClick={toggleSearchBar} aria-label="Toggle device search">
          <Search size={20} />
        </button>
      </div>
      <div className="card-content">
        {isSearchVisible && (
          <div className="search-bar">
            <input
              type="text"
              placeholder="Search devices..."
              value={deviceSearchQuery}
              onChange={handleDeviceSearchChange}
              className="search-input"
              aria-label="Search devices"
            />
          </div>
        )}
        <div className="device-list">
          {filteredDevices.length > 0 ? (
            filteredDevices.map(([id, device]) => (
              <div key={id} className="device-item">
                <div className="device-info">
                  <span className="device-name">{device.name}</span>
                  <span className="device-id">{id}</span>
                </div>
                <div className="device-status">
                  {device.status === "connected" ? (
                    <span className="status-indicator connected"></span>
                  ) : (
                    <span className="status-indicator disconnected"></span>
                  )}
                </div>
              </div>
            ))
          ) : (
            <div className="no-devices">No devices found</div>
          )}
        </div>
      </div>
    </div>
  )
}

export default DevicesCard