type LogLevel = 'debug' | 'info' | 'warn' | 'error';

interface LogEntry {
  timestamp: string;
  level: LogLevel;
  message: string;
  data?: any;
  error?: Error;
}

class Logger {
  private isDevelopment = import.meta.env.DEV;

  private formatMessage(level: LogLevel, message: string, data?: any, error?: Error): LogEntry {
    return {
      timestamp: new Date().toISOString(),
      level,
      message,
      data,
      error,
    };
  }

  private log(level: LogLevel, message: string, data?: any, error?: Error) {
    const logEntry = this.formatMessage(level, message, data, error);

    if (this.isDevelopment) {
      // In development, use console methods with styling
      const style = this.getConsoleStyle(level);
      console.group(`%c[${level.toUpperCase()}] ${message}`, style);
      
      if (data) {
        console.log('Data:', data);
      }
      
      if (error) {
        console.error('Error:', error);
        if (error.stack) {
          console.trace(error.stack);
        }
      }
      
      console.groupEnd();
    } else {
      // In production, log as JSON for structured logging
      console.log(JSON.stringify(logEntry));
    }

    // In a real application, you might also send logs to a logging service
    // this.sendToLoggingService(logEntry);
  }

  private getConsoleStyle(level: LogLevel): string {
    const styles = {
      debug: 'color: #6B7280; font-weight: normal;',
      info: 'color: #3B82F6; font-weight: bold;',
      warn: 'color: #F59E0B; font-weight: bold;',
      error: 'color: #EF4444; font-weight: bold;',
    };
    return styles[level];
  }

  debug(message: string, data?: any) {
    this.log('debug', message, data);
  }

  info(message: string, data?: any) {
    this.log('info', message, data);
  }

  warn(message: string, data?: any) {
    this.log('warn', message, data);
  }

  error(message: string, error?: Error, data?: any) {
    this.log('error', message, data, error);
  }

  // Convenience method for API errors
  apiError(endpoint: string, error: any, requestData?: any) {
    this.error(
      `API request failed: ${endpoint}`,
      error,
      {
        endpoint,
        requestData,
        response: error.response?.data,
        status: error.response?.status,
      }
    );
  }

  // Convenience method for component errors
  componentError(componentName: string, error: Error, props?: any) {
    this.error(
      `Component error in ${componentName}`,
      error,
      {
        componentName,
        props,
      }
    );
  }
}

// Export a singleton instance
export const logger = new Logger();

// Export the class for testing or custom instances
export default Logger;
