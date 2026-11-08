import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import '@fontsource-variable/geist';
import '@fontsource-variable/space-grotesk';
import './index.css';

// The orb draws at the screen's pixel density. Asking for 2x keeps it sharp when the landing orb is scaled up.
if (window.devicePixelRatio < 2) Object.defineProperty(window, 'devicePixelRatio', { get: () => 2 });

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
