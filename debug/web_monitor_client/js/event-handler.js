/**
 * EventHandler Module
 * Processes WebSocket events received from the monitor
 */
const EventHandler = (function() {
  // Debug mode flag
  let debugMode = false;
  
  /**
   * Set debug mode state
   * @param {boolean} isDebug - Debug mode on/off
   */
  function setDebugMode(isDebug) {
    debugMode = isDebug;
  }
  
  /**
   * Process incoming WebSocket monitor events
   * @param {Object} event - Event object received from the WebSocket
   */
  function handleMonitorEvent(event) {
    if (!event || !event.type) {
      console.error('Received invalid event:', event);
      return;
    }
    
    const eventType = event.type;
    
    // Log event in debug mode
    if (debugMode) {
      console.debug('Received event:', eventType, event);
    }
    
    switch (eventType) {
      case 'active_sessions': {
        // Update session list with all active sessions
        const sessions = event.sessions || [];
        SessionManager.updateSessions(sessions);
        
        // Auto-watch "newest" session if not watching anything
        if (!SessionManager.getActiveSessionId() && sessions.length > 0) {
          const newestSessionId = SessionManager.findNewestSession();
          if (newestSessionId) {
            window.App.watchSession(newestSessionId);
          }
        }
        break;
      }
      
      case 'session_started': {
        // Add new session to the list
        const newSession = event.session || {};
        if (newSession.id) {
          SessionManager.addOrUpdateSession(newSession);
          
          // Auto-watch if none is active
          if (!SessionManager.getActiveSessionId()) {
            window.App.watchSession(newSession.id);
          }
        }
        break;
      }
      
      case 'session_ended': {
        // Remove ended session from the list
        const endedSession = event.session || {};
        if (endedSession.id) {
          SessionManager.removeSession(endedSession.id);
        }
        break;
      }
      
      case 'client_input': {
        // Process and display client input
        const clientSessionId = event.session_id;
        const clientData = event.data || {};
        const clientText = clientData.text || '';
        
        if (clientSessionId === SessionManager.getActiveSessionId()) {
          try {
            // Parse the raw data to remove telnet control sequences
            const cleanText = TelnetParser.parseRawData(clientText);
            if (cleanText && cleanText.trim().length > 0) {
              TerminalDisplay.appendClientInput(cleanText);
            }
          } catch (error) {
            console.error('Error parsing client input:', error);
            if (debugMode) {
              TerminalDisplay.appendError(`Error parsing client input: ${error.message}`);
            }
          }
        }
        break;
      }
      
      case 'server_message': {
        // Process and display server output
        const serverSessionId = event.session_id;
        const serverData = event.data || {};
        const serverText = serverData.text || '';
        
        if (serverSessionId === SessionManager.getActiveSessionId()) {
          try {
            // Parse the raw data to remove telnet control sequences
            const cleanText = TelnetParser.parseRawData(serverText);
            if (cleanText && cleanText.trim().length > 0) {
              TerminalDisplay.appendServerOutput(cleanText);
            }
          } catch (error) {
            console.error('Error parsing server message:', error);
            if (debugMode) {
              TerminalDisplay.appendError(`Error parsing server message: ${error.message}`);
            }
          }
        }
        break;
      }
      
      case 'watch_response': {
        // Handle watch success/failure
        const watchSessionId = event.session_id;
        const watchStatus = event.status;
        
        if (watchStatus === 'success') {
          // Successfully watching session
          SessionManager.setActiveSession(watchSessionId);
        } else if (watchStatus === 'stopped') {
          // Stopped watching session
          SessionManager.setActiveSession(null);
        } else if (event.error) {
          // Watch error
          console.error('Watch error:', event.error);
          TerminalDisplay.appendError(`Watch error: ${event.error}`);
        }
        break;
      }
      
      default:
        // Unknown event type
        if (debugMode) {
          console.warn('Unknown event type:', eventType, event);
        }
        break;
    }
  }
  
  // Public API
  return {
    handleMonitorEvent,
    setDebugMode
  };
})();