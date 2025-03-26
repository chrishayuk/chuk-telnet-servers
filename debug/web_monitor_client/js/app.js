/**
 * Main Application Module
 * Coordinates the WebSocket Session Monitor application
 */
const App = (function() {
    // Debug mode state
    let debugMode = false;
    let debugPanelElement = null;
    let debugRawElement = null;
    
    /**
     * Initialize the application
     */
    function init() {
      // Get DOM elements
      const elements = {
        // Connection related elements
        urlInput: document.getElementById('monitor-url'),
        connectBtn: document.getElementById('connect-btn'),
        disconnectBtn: document.getElementById('disconnect-btn'),
        connectionStatus: document.getElementById('connection-status'),
        
        // Session related elements
        sessionList: document.getElementById('session-list'),
        noSessionsMessage: document.getElementById('no-sessions'),
        watchingStatus: document.getElementById('watching-status'),
        
        // Terminal elements
        terminal: document.getElementById('terminal'),
        
        // Debug elements
        toggleDebug: document.getElementById('toggle-debug'),
        debugPanel: document.getElementById('debug-panel'),
        debugRaw: document.getElementById('debug-raw')
      };
      
      // Store debug elements for later use
      debugPanelElement = elements.debugPanel;
      debugRawElement = elements.debugRaw;
      
      // Initialize modules
      TerminalDisplay.init(elements.terminal);
      SessionManager.init({
        sessionList: elements.sessionList,
        noSessionsMessage: elements.noSessionsMessage,
        watchingStatus: elements.watchingStatus
      });
      ConnectionManager.init({
        urlInput: elements.urlInput,
        connectBtn: elements.connectBtn,
        disconnectBtn: elements.disconnectBtn,
        connectionStatus: elements.connectionStatus
      });
      
      // Set up event listeners
      elements.connectBtn.addEventListener('click', ConnectionManager.connect);
      elements.disconnectBtn.addEventListener('click', ConnectionManager.disconnect);
      elements.toggleDebug.addEventListener('click', toggleDebugMode);
      
      // Log initialization
      console.log('WebSocket Session Monitor initialized');
    }
    
    /**
     * Watch a specific session
     * @param {string} sessionId - ID of the session to watch
     */
    function watchSession(sessionId) {
      if (!ConnectionManager.isWebSocketConnected()) return;
      
      const command = {
        type: 'watch_session',
        session_id: sessionId
      };
      
      ConnectionManager.sendCommand(command);
    }
    
    /**
     * Stop watching a session
     * @param {string} sessionId - ID of the session to stop watching
     */
    function stopWatchingSession(sessionId) {
      if (!ConnectionManager.isWebSocketConnected()) return;
      
      const command = {
        type: 'stop_watching',
        session_id: sessionId
      };
      
      ConnectionManager.sendCommand(command);
    }
    
    /**
     * Toggle debug mode
     */
    function toggleDebugMode() {
      debugMode = !debugMode;
      
      // Update UI
      if (debugPanelElement) {
        debugPanelElement.style.display = debugMode ? 'block' : 'none';
      }
      
      const toggleBtn = document.getElementById('toggle-debug');
      if (toggleBtn) {
        toggleBtn.textContent = debugMode ? 'Hide Debug Panel' : 'Show Debug Panel';
      }
      
      // Update modules
      EventHandler.setDebugMode(debugMode);
      ConnectionManager.setDebugMode(debugMode);
      
      console.log(`Debug mode ${debugMode ? 'enabled' : 'disabled'}`);
    }
    
    /**
     * Set debug information in the debug panel
     * @param {string} info - Debug information to display
     */
    function setDebugInfo(info) {
      if (debugRawElement && debugMode) {
        debugRawElement.textContent = info;
      }
    }

    /**
     * Check if debug mode is enabled
     * @returns {boolean} Current debug mode state
     */
    function isDebugMode() {
      return debugMode;
    }
    
    // Public API
    return {
      init,
      watchSession,
      stopWatchingSession,
      toggleDebugMode,
      setDebugInfo,
      isDebugMode
    };
  })();
  
  // Make the App object available globally
  window.App = App;
  
  // Initialize the application when the document is ready
  document.addEventListener('DOMContentLoaded', function() {
    App.init();
  });