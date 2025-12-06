import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import './App.css'
import { DeviceProvider } from './contexts/DeviceContext.jsx'
import { SystemProvider } from './contexts/SystemContext.jsx'
import { LogProvider } from './contexts/LogContext.jsx'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <DeviceProvider>
      <SystemProvider>
        <LogProvider>
          <App />
        </LogProvider>
      </SystemProvider>
    </DeviceProvider>
  </React.StrictMode>
)