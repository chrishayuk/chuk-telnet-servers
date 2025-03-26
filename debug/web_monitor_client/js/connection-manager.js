/**
 * ConnectionManager Module
 * Manages WebSocket connections
 */
const ConnectionManager = (function() {
  // DOM elements
  let urlInput = null;
  let connectBtn = null;
  let disconnectBtn = null;
  let connectionStatusElement = null;
  
  // Connection state
  let websocket = null;
  let isConnected = false;
  let debugMode = false;
  
  /**
   * Initialize the connection manager
   * @param {Object} elements - DOM elements used by the connection manager
   * @param {HTMLElement} elements.urlInput - URL input field
   * @param {HTMLElement} elements.connectBtn - Connect button
   * @param {HTMLElement} elements.disconnectBtn - Disconnect button
   * @param {HTMLElement} elements.connectionStatus - Connection status display
   */
  function init(elements) {
    urlInput = elements.urlInput;
    connectBtn = elements.connectBtn;
    disconnectBtn = elements.disconnectBtn;
    connectionStatusElement = elements.connectionStatus;
  }
  
  /**
   * Set debug mode state
   * @param {boolean} isDebug - Debug mode on/off
   */
  function setDebugMode(isDebug) {
    debugMode = isDebug;
  }
  
  /**
   * Connect to WebSocket server
   */
  function connect() {
    if (!urlInput) return;
    
    const url = urlInput.value.trim();
    if (!url) {
      alert('Please enter a valid WebSocket URL');
      return;
    }
    
    try {
      websocket = new WebSocket(url);
      
      // Set up connection event handlers
      websocket.onopen = () => {
        isConnected = true;
        
        if (connectionStatusElement) {
          connectionStatusElement.textContent = `Connected to ${url}`;
        }
        
        if (connectBtn) connectBtn.disabled = true;
        if (disconnectBtn) disconnectBtn.disabled = false;
        
        // Clear the terminal on each fresh connect
        TerminalDisplay.clear();
        
        // Log connection success
        if (debugMode) {
          console.log(`Connected to ${url}`);
        }
      };
      
      websocket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          EventHandler.handleMonitorEvent(data);
        } catch (error) {
          console.error('Failed to parse message:', error);
          if (debugMode) {
            console.debug('Raw message:', event.data);
          }
        }
      };
      
      websocket.onerror = (error) => {
        console.error('WebSocket connection error:', error);
        TerminalDisplay.appendError('Connection error. Check console for details.');
      };
      
      websocket.onclose = () => {
        isConnected = false;
        
        if (connectionStatusElement) {
          connectionStatusElement.textContent = 'Disconnected';
        }
        
        if (connectBtn) connectBtn.disabled = false;
        if (disconnectBtn) disconnectBtn.disabled = true;
        
        // Reset local state
        SessionManager.clearSessions();
        
        // Log disconnection
        if (debugMode) {
          console.log('Disconnected from WebSocket server');
        }
      };
    } catch (error) {
      console.error('Failed to create WebSocket connection:', error);
      alert(`Failed to connect: ${error.message}`);
    }
  }
  
  /**
   * Disconnect from WebSocket server
   */
  function disconnect() {
    if (websocket && isConnected) {
      websocket.close();
      websocket = null;
    }
  }
  
  /**
   * Send a command to the WebSocket server
   * @param {Object} command - Command object to send
   * @returns {boolean} Success status
   */
  function sendCommand(command) {
    if (!websocket || !isConnected) {
      console.error('Cannot send command: Not connected');
      return false;
    }
    
    try {
      const commandStr = JSON.stringify(command);
      websocket.send(commandStr);
      
      if (debugMode) {
        console.debug('Sent command:', command);
      }
      
      return true;
    } catch (error) {
      console.error('Failed to send command:', error);
      return false;
    }
  }
  
  /**
   * Check if the application is connected
   * @returns {boolean} Connection status
   */
  function isWebSocketConnected() {
    return isConnected;
  }
  
  // Public API
  return {
    init,
    connect,
    disconnect,
    sendCommand,
    setDebugMode,
    isWebSocketConnected
  };
})();