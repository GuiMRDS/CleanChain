import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App.jsx';
import './fonts.js';
import './index.css';
import './styles/hud.css';

// Desktop build (Electron): integrated title bar styles in DesktopMenu.css apply to html.is-desktop.
if (window.cleanchain) document.documentElement.classList.add('is-desktop');

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>
);
