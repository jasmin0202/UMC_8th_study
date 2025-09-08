import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import Clock from './chatper_04/Clock';

const root = ReactDOM.createRoot(document.getElementById('root'));
setInterval(() => {
  root.render(
    <StrictMode>
      <Clock />
    </StrictMode>
  )
}, 1000);
