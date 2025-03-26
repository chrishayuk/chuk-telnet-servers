/**
 * SessionManager Module
 * Manages the active WebSocket sessions
 */
const SessionManager = (function() {
    // DOM elements
    let sessionListElement = null;
    let noSessionsMessage = null;
    let watchingStatusElement = null;
    
    // Session state
    let activeSessions = {};
    let activeSessionId = null;
    
    /**
     * Initialize the session manager
     * @param {Object} elements - DOM elements needed by the session manager
     * @param {HTMLElement} elements.sessionList - Session list container
     * @param {HTMLElement} elements.noSessionsMessage - Empty state message
     * @param {HTMLElement} elements.watchingStatus - Watching status display
     */
    function init(elements) {
      sessionListElement = elements.sessionList;
      noSessionsMessage = elements.noSessionsMessage;
      watchingStatusElement = elements.watchingStatus;
    }
    
    /**
     * Update the session list UI
     */
    function updateSessionList() {
      if (!sessionListElement) return;
      
      sessionListElement.innerHTML = '';
      
      const sessionIds = Object.keys(activeSessions);
      if (sessionIds.length === 0) {
        noSessionsMessage.style.display = 'block';
      } else {
        noSessionsMessage.style.display = 'none';
        
        sessionIds.forEach(sessionId => {
          const session = activeSessions[sessionId];
          const isActive = (sessionId === activeSessionId);
          
          const li = document.createElement('li');
          li.className = `session-item ${isActive ? 'active' : ''}`;
          li.dataset.sessionId = sessionId;
          
          const remoteAddr = session.client?.remote_addr || 'Unknown';
          const shortId = sessionId.substring(0, 8);
          
          li.innerHTML = `
            <div>Session ${shortId}...</div>
            <div class="session-details">
              Client: ${remoteAddr}
            </div>
          `;
          
          li.addEventListener('click', () => {
            if (isActive) {
              // If already active, stop watching
              window.App.stopWatchingSession(sessionId);
            } else {
              // Start watching this session
              window.App.watchSession(sessionId);
            }
          });
          
          sessionListElement.appendChild(li);
        });
      }
    }
    
    /**
     * Add or update a session in the active sessions list
     * @param {Object} session - Session object
     */
    function addOrUpdateSession(session) {
      if (session && session.id) {
        activeSessions[session.id] = session;
        updateSessionList();
      }
    }
    
    /**
     * Remove a session from the active sessions list
     * @param {string} sessionId - ID of the session to remove
     */
    function removeSession(sessionId) {
      if (sessionId && activeSessions[sessionId]) {
        delete activeSessions[sessionId];
        
        // If we were watching this session, reset
        if (activeSessionId === sessionId) {
          activeSessionId = null;
          if (watchingStatusElement) {
            watchingStatusElement.textContent = 'Not watching any session';
          }
        }
        
        updateSessionList();
      }
    }
    
    /**
     * Update sessions with a new list
     * @param {Array} sessions - Array of session objects
     */
    function updateSessions(sessions) {
      activeSessions = {};
      if (Array.isArray(sessions)) {
        sessions.forEach(session => {
          if (session && session.id) {
            activeSessions[session.id] = session;
          }
        });
      }
      updateSessionList();
    }
    
    /**
     * Find newest session from the active sessions
     * @returns {string|null} ID of the newest session or null if none found
     */
    function findNewestSession() {
      const sessions = Object.values(activeSessions);
      if (sessions.length === 0) return null;
      
      // Try to find a session marked as newest
      for (const sess of sessions) {
        if (sess.is_newest) {
          return sess.id;
        }
      }
      
      // If no session is marked as newest, return the first one
      return sessions[0].id;
    }
    
    /**
     * Set the active session being watched
     * @param {string|null} sessionId - ID of the session to watch, or null to clear
     */
    function setActiveSession(sessionId) {
      activeSessionId = sessionId;
      
      if (sessionId && watchingStatusElement) {
        watchingStatusElement.textContent = `Watching session: ${sessionId.substring(0, 8)}...`;
      } else if (watchingStatusElement) {
        watchingStatusElement.textContent = 'Not watching any session';
      }
      
      updateSessionList();
    }
    
    /**
     * Get the active session ID
     * @returns {string|null} - Currently active session ID or null if none
     */
    function getActiveSessionId() {
      return activeSessionId;
    }
    
    /**
     * Clear all sessions
     */
    function clearSessions() {
      activeSessions = {};
      activeSessionId = null;
      
      if (watchingStatusElement) {
        watchingStatusElement.textContent = 'Not watching any session';
      }
      
      updateSessionList();
    }
    
    // Public API
    return {
      init,
      updateSessionList,
      addOrUpdateSession,
      removeSession,
      updateSessions,
      findNewestSession,
      setActiveSession,
      getActiveSessionId,
      clearSessions
    };
  })();