import { memo } from "react"

// Memoized DeviceItem component to prevent unnecessary re-renders
// Only re-renders when the device's cw or ww values actually change
const DeviceItem = memo(({ ip, data }) => {
  return (
    <li className="device-item">
      <div className={`device-status ${data.cw !== null ? "connected" : "disconnected"}`}></div>
      <div className="device-info">
        <div className="device-ip">{ip}</div>
        <div className="device-details">
          CW: {data.cw !== null ? data.cw.toFixed(1) : "N/A"}%, WW: {data.ww !== null ? data.ww.toFixed(1) : "N/A"}%
        </div>
      </div>
    </li>
  )
}, (prevProps, nextProps) => {
  // Custom comparison function: only re-render if values actually changed
  return (
    prevProps.ip === nextProps.ip &&
    prevProps.data.cw === nextProps.data.cw &&
    prevProps.data.ww === nextProps.data.ww
  )
})

DeviceItem.displayName = "DeviceItem"

export default DeviceItem
