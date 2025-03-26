/**
 * Enhanced TelnetParser Module
 * Advanced handling of telnet protocol commands and escape sequences
 */
const TelnetParser = (function() {
  // Telnet command constants
  const IAC = 255;  // Interpret As Command (0xFF)
  const WILL = 251;
  const WONT = 252;
  const DO = 253;
  const DONT = 254;
  const SB = 250;   // Subnegotiation Begin
  const SE = 240;   // Subnegotiation End
  
  // Known option codes
  const ECHO = 1;
  const SUPPRESS_GO_AHEAD = 3;
  const TERMINAL_TYPE = 24;
  const NAWS = 31;  // Negotiate About Window Size
  
  // Debug logging helper
  function logHexDump(bytes, label = "Hex Dump") {
    const hexOutput = Array.from(bytes).map(b => 
      b.toString(16).padStart(2, '0')
    ).join(' ');
    
    console.debug(`${label}: [${hexOutput}]`);
    return hexOutput;
  }
  
  /**
   * Clean telnet control characters and ANSI escape sequences from text
   * @param {string} data - Raw text data which may contain telnet commands
   * @returns {string} - Cleaned text data
   */
  function parseRawData(data) {
    // Convert to Uint8Array for binary processing
    const bytes = new Uint8Array(data.length);
    for (let i = 0; i < data.length; i++) {
      bytes[i] = data.charCodeAt(i) & 0xFF;
    }
    
    // Generate debug info
    const hexDump = logHexDump(bytes, "Raw input");
    if (window.App && window.App.setDebugInfo) {
      window.App.setDebugInfo(hexDump);
    }
    
    // Create processed output buffer
    const processed = [];
    let i = 0;
    
    while (i < bytes.length) {
      // Check for telnet IAC sequence (0xFF)
      if (bytes[i] === IAC) {
        // Process the IAC command
        i = processIACSequence(bytes, i, processed);
        continue;
      }
      
      // Check for escape sequences
      if (bytes[i] === 0x1B) { // ESC character
        // Process ANSI escape sequence
        i = processEscapeSequence(bytes, i);
        continue;
      }
      
      // Check for other control characters (0x00-0x1F except common ones)
      if (bytes[i] < 32) {
        switch (bytes[i]) {
          case 9:  // Tab
            processed.push('\t');
            break;
          case 10: // Line Feed
            processed.push('\n');
            break;
          case 13: // Carriage Return - skip, we handle newlines with \n
            break;
          case 8:  // Backspace
            if (processed.length > 0) {
              processed.pop(); // Remove last character
            }
            break;
          default:
            // Skip all other control characters
            if (window.App && window.App.isDebugMode && window.App.isDebugMode()) {
              console.debug(`Skipping control character: 0x${bytes[i].toString(16)}`);
            }
            break;
        }
        i++;
        continue;
      }
      
      // Regular ASCII printable characters
      if ((bytes[i] >= 32 && bytes[i] <= 126) || bytes[i] >= 160) {
        processed.push(String.fromCharCode(bytes[i]));
      }
      
      i++;
    }
    
    // Join the processed characters
    return processed.join('');
  }
  
  /**
   * Process an IAC sequence
   * @param {Uint8Array} bytes - Full byte array
   * @param {number} pos - Current position (at IAC byte)
   * @param {Array} processed - Array of processed characters
   * @returns {number} - New position after skipping the IAC sequence
   */
  function processIACSequence(bytes, pos, processed) {
    const start = pos;
    
    // Skip the IAC byte
    pos++;
    
    // We need at least one more byte
    if (pos >= bytes.length) {
      return pos;
    }
    
    // Handle different IAC commands
    switch (bytes[pos]) {
      case WILL:
      case WONT:
      case DO:
      case DONT:
        // These are 3-byte sequences: IAC + CMD + OPTION
        pos += 2;
        break;
        
      case SB:
        // Subnegotiation: IAC + SB + ... + IAC + SE
        pos++;
        
        // Find the end (IAC + SE)
        while (pos < bytes.length - 1) {
          if (bytes[pos] === IAC && bytes[pos + 1] === SE) {
            pos += 2;
            break;
          }
          pos++;
        }
        break;
        
      default:
        // Other two-byte commands: IAC + CMD
        pos++;
        break;
    }
    
    // Debug log the skipped sequence
    if (window.App && window.App.isDebugMode && window.App.isDebugMode()) {
      const sequence = Array.from(bytes.slice(start, pos)).map(b => 
        b.toString(16).padStart(2, '0')
      ).join(' ');
      console.debug(`Skipped telnet sequence: ${sequence}`);
    }
    
    return pos;
  }
  
  /**
   * Process an escape sequence (ANSI color codes, etc.)
   * @param {Uint8Array} bytes - Full byte array
   * @param {number} pos - Current position (at ESC byte)
   * @returns {number} - New position after skipping the escape sequence
   */
  function processEscapeSequence(bytes, pos) {
    const start = pos;
    
    // Skip the ESC byte
    pos++;
    
    // Check for CSI sequence (ESC + [)
    if (pos < bytes.length && bytes[pos] === 0x5B) {
      pos++;
      
      // Consume until we find a terminating byte (0x40-0x7E)
      while (pos < bytes.length && !(bytes[pos] >= 0x40 && bytes[pos] <= 0x7E)) {
        pos++;
      }
      
      // Skip the terminating byte
      if (pos < bytes.length) {
        pos++;
      }
    }
    // Check for other common sequences
    else if (pos < bytes.length) {
      // Simple 2-byte sequences like ESC + D, ESC + M, etc.
      pos++;
    }
    
    // Debug log the skipped sequence
    if (window.App && window.App.isDebugMode && window.App.isDebugMode()) {
      const sequence = Array.from(bytes.slice(start, pos)).map(b => 
        b.toString(16).padStart(2, '0')
      ).join(' ');
      console.debug(`Skipped escape sequence: ${sequence}`);
    }
    
    return pos;
  }
  
  // Public API
  return {
    parseRawData,
    logHexDump
  };
})();