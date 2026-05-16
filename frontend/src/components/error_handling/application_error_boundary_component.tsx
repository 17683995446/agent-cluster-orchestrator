import React, { Component, ErrorInfo, ReactNode } from 'react';

export interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
}

export interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
  showErrorDetails?: boolean;
  maxRetries?: number;
}

export class GlobalApplicationErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  private retryCount: number = 0;
  private maxRetries: number;

  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.maxRetries = props.maxRetries ?? 3;
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
    };
  }

  static getDerivedStateFromError(error: Error): Partial<ErrorBoundaryState> {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    this.setState({ errorInfo });
    this.props.onError?.(error, errorInfo);
    console.error('Application Error Boundary caught an error:', error, errorInfo);
  }

  handleRetry = (): void => {
    if (this.retryCount < this.maxRetries) {
      this.retryCount++;
      this.setState({ hasError: false, error: null, errorInfo: null });
    }
  };

  handleReset = (): void => {
    this.retryCount = 0;
    this.setState({ hasError: false, error: null, errorInfo: null });
  };

  render(): ReactNode {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-900 p-4">
          <div className="max-w-lg w-full bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6">
            <div className="flex items-center justify-center w-16 h-16 mx-auto mb-4 bg-red-100 dark:bg-red-900/30 rounded-full">
              <svg
                className="w-8 h-8 text-red-600 dark:text-red-400"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                />
              </svg>
            </div>
            <h2 className="text-xl font-semibold text-center text-gray-900 dark:text-white mb-2">
              Something went wrong
            </h2>
            <p className="text-gray-600 dark:text-gray-400 text-center mb-6">
              We encountered an unexpected error. Please try again.
            </p>
            {this.state.error && (
              <div className="bg-gray-100 dark:bg-gray-700 rounded-lg p-4 mb-6">
                <p className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Error: {this.state.error.name}
                </p>
                <p className="text-xs text-gray-500 dark:text-gray-400 break-all">
                  {this.state.error.message}
                </p>
              </div>
            )}
            {this.props.showErrorDetails && this.state.errorInfo && (
              <details className="mb-6">
                <summary className="text-sm text-gray-600 dark:text-gray-400 cursor-pointer mb-2">
                  Show error details
                </summary>
                <pre className="bg-gray-100 dark:bg-gray-700 p-4 rounded-lg text-xs text-gray-600 dark:text-gray-400 overflow-auto max-h-32">
                  {this.state.errorInfo.componentStack}
                </pre>
              </details>
            )}
            <div className="flex gap-3">
              {this.retryCount < this.maxRetries && (
                <button
                  onClick={this.handleRetry}
                  className="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg transition-colors"
                >
                  Try Again ({this.maxRetries - this.retryCount} left)
                </button>
              )}
              <button
                onClick={this.handleReset}
                className="flex-1 px-4 py-2 bg-gray-200 hover:bg-gray-300 dark:bg-gray-700 dark:hover:bg-gray-600 text-gray-800 dark:text-white font-medium rounded-lg transition-colors"
              >
                Reset
              </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export interface AsyncOperationBoundaryProps {
  children: ReactNode;
  loadingComponent?: ReactNode;
  errorComponent?: ReactNode;
  onError?: (error: Error) => void;
  loadingDelay?: number;
}

interface AsyncOperationBoundaryState {
  isLoading: boolean;
  error: Error | null;
}

export class AsyncOperationBoundary extends Component<
  AsyncOperationBoundaryProps,
  AsyncOperationBoundaryState
> {
  private loadingTimeout: ReturnType<typeof setTimeout> | null = null;

  constructor(props: AsyncOperationBoundaryProps) {
    super(props);
    this.state = { isLoading: false, error: null };
  }

  static getDerivedStateFromError(error: Error): Partial<AsyncOperationBoundaryState> {
    return { error };
  }

  componentDidCatch(error: Error): void {
    this.props.onError?.(error);
  }

  setLoading = (loading: boolean, delay = 300): void => {
    if (loading) {
      this.loadingTimeout = setTimeout(() => {
        this.setState({ isLoading: true });
      }, delay);
    } else {
      if (this.loadingTimeout) {
        clearTimeout(this.loadingTimeout);
      }
      this.setState({ isLoading: false });
    }
  };

  clearError = (): void => {
    this.setState({ error: null });
  };

  render(): ReactNode {
    if (this.state.error) {
      if (this.props.errorComponent) {
        return (
          <>
            {React.cloneElement(this.props.errorComponent as React.ReactElement<{ error: Error; onRetry: () => void }>, {
              error: this.state.error,
              onRetry: this.clearError,
            })}
          </>
        );
      }
      return (
        <div className="p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
          <p className="text-red-800 dark:text-red-200 font-medium mb-2">
            Operation Failed
          </p>
          <p className="text-red-600 dark:text-red-400 text-sm mb-3">
            {this.state.error.message}
          </p>
          <button
            onClick={this.clearError}
            className="px-3 py-1 bg-red-100 dark:bg-red-800 text-red-700 dark:text-red-200 rounded hover:bg-red-200 dark:hover:bg-red-700 transition-colors"
          >
            Dismiss
          </button>
        </div>
      );
    }

    return (
      <>
        {this.state.isLoading && this.props.loadingComponent}
        {!this.state.isLoading && this.props.children}
      </>
    );
  }
}

export function withErrorBoundary<P extends object>(
  WrappedComponent: React.ComponentType<P>,
  errorBoundaryProps?: Partial<ErrorBoundaryProps>
): React.FC<P> {
  return function WithErrorBoundaryComponent(props: P) {
    return (
      <GlobalApplicationErrorBoundary {...errorBoundaryProps}>
        <WrappedComponent {...props} />
      </GlobalApplicationErrorBoundary>
    );
  };
}

export function withAsyncBoundary<P extends object>(
  WrappedComponent: React.ComponentType<P>,
  asyncBoundaryProps?: Partial<AsyncOperationBoundaryProps>
): React.FC<P> {
  return function WithAsyncBoundaryComponent(props: P) {
    return (
      <AsyncOperationBoundary {...asyncBoundaryProps}>
        <WrappedComponent {...props} />
      </AsyncOperationBoundary>
    );
  };
}
