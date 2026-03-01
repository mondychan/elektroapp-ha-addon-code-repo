import React from "react";

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = {
      hasError: false,
      message: null,
    };
  }

  static getDerivedStateFromError(error) {
    return {
      hasError: true,
      message: error?.message || "Unexpected UI error.",
    };
  }

  componentDidCatch(error, errorInfo) {
    console.error("Unhandled frontend error:", error, errorInfo);
  }

  render() {
    if (!this.state.hasError) {
      return this.props.children;
    }

    return (
      <div className="error-boundary">
        <h2>Aplikace narazila na chybu</h2>
        <p>{this.state.message}</p>
        <button type="button" onClick={() => window.location.reload()}>
          Obnovit stranku
        </button>
      </div>
    );
  }
}

export default ErrorBoundary;
