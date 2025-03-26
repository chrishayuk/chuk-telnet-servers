/**
 * TerminalDisplay Module
 * Handles rendering and updating the terminal display
 */
const TerminalDisplay = (function() {
    // DOM element for the terminal display
    let terminalElement = null;
    
    /**
     * Initialize the terminal display
     * @param {HTMLElement} element - The DOM element for the terminal
     */
    function init(element) {
      terminalElement = element;
    }
    
    /**
     * Append text to the terminal display
     * @param {string} text - Text to append to the terminal
     * @param {string} [className] - Optional CSS class to apply to the text
     */
    function appendToTerminal(text, className) {
      if (!terminalElement || !text) return;
      
      // Split by newlines to handle each line
      const lines = text.split('\n');
      
      // Process and append each line
      lines.forEach(line => {
        // Ignore empty lines if they're at the end
        if (line === '' && lines.length > 1) return;
        
        // Create a new line element
        const div = document.createElement('div');
        div.textContent = line;
        
        // Apply class if provided
        if (className) {
          div.className = className;
        }
        
        // Add to terminal
        terminalElement.appendChild(div);
      });
      
      // Auto-scroll to bottom
      scrollToBottom();
    }
    
    /**
     * Append client input to the terminal
     * @param {string} text - Client input text
     */
    function appendClientInput(text) {
      appendToTerminal(text, 'terminal-input');
    }
    
    /**
     * Append server output to the terminal
     * @param {string} text - Server output text
     */
    function appendServerOutput(text) {
      appendToTerminal(text);
    }
    
    /**
     * Append an error message to the terminal
     * @param {string} text - Error message text
     */
    function appendError(text) {
      appendToTerminal(text, 'terminal-error');
    }
    
    /**
     * Clear the terminal display
     */
    function clear() {
      if (terminalElement) {
        terminalElement.innerHTML = '';
      }
    }
    
    /**
     * Scroll the terminal to the bottom
     */
    function scrollToBottom() {
      if (terminalElement) {
        terminalElement.scrollTop = terminalElement.scrollHeight;
      }
    }
    
    // Public API
    return {
      init,
      appendToTerminal,
      appendClientInput,
      appendServerOutput,
      appendError,
      clear,
      scrollToBottom
    };
  })();