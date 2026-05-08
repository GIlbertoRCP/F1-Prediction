import React from 'react';

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true };
  }

  componentDidCatch(error, errorInfo) {
    console.error("ErrorBoundary caught an error:", error, errorInfo);
    this.setState({ error, errorInfo });
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="bg-red-950/20 border border-red-900 p-8 rounded-lg text-red-500 font-mono shadow-2xl mt-8">
          <h2 className="text-2xl font-bold mb-4">COMPONENT CRASH DETECTED</h2>
          <p className="mb-4">The telemetry visualizer experienced a fatal runtime exception.</p>
          <div className="bg-zinc-950 p-4 rounded text-xs overflow-auto max-h-[300px]">
            <p className="font-bold">{this.state.error && this.state.error.toString()}</p>
            <pre className="text-zinc-500 mt-2">{this.state.errorInfo && this.state.errorInfo.componentStack}</pre>
          </div>
          <button 
            onClick={() => this.setState({ hasError: false, error: null, errorInfo: null })}
            className="mt-4 bg-red-900 hover:bg-red-800 text-white px-4 py-2 rounded"
          >
            Attempt Reset
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

export default ErrorBoundary;
