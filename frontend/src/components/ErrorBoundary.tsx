import React, { Component, ErrorInfo, ReactNode } from 'react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error?: Error;
  errorInfo?: ErrorInfo;
}

class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error): State {
    // Update state so the next render will show the fallback UI
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    // Log error to console and potentially to a logging service
    console.error('ErrorBoundary caught an error:', error, errorInfo);
    
    this.setState({
      error,
      errorInfo
    });

    // You can also log the error to an error reporting service here
    // logErrorToService(error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      // Fallback UI
      return (
        <div className="min-h-screen bg-red-50 flex items-center justify-center">
          <div className="max-w-md mx-auto bg-white rounded-lg shadow-md p-6">
            <div className="text-center">
              <div className="text-red-500 text-6xl mb-4">⚠️</div>
              <h1 className="text-2xl font-bold text-gray-900 mb-2">
                Something went wrong
              </h1>
              <p className="text-gray-600 mb-4">
                An unexpected error occurred. Please refresh the page or contact support if the problem persists.
              </p>
              
              {process.env.NODE_ENV === 'development' && this.state.error && (
                <details className="text-left bg-gray-100 p-4 rounded mt-4">
                  <summary className="cursor-pointer font-semibold">
                    Error Details (Development Mode)
                  </summary>
                  <pre className="mt-2 text-sm text-red-600 whitespace-pre-wrap">
                    {this.state.error.toString()}
                    {this.state.errorInfo?.componentStack}
                  </pre>
                </details>
              )}
              
              <button
                onClick={() => window.location.reload()}
                className="mt-4 bg-blue-500 hover:bg-blue-600 text-white font-bold py-2 px-4 rounded"
              >
                Refresh Page
              </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
