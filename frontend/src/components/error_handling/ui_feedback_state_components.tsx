import React, { useCallback, useState } from 'react';

interface RetryButtonProps {
  onRetry: () => void | Promise<void>;
  maxRetries?: number;
  retryDelay?: number;
  children?: React.ReactNode;
  className?: string;
}

export function RetryOperationButton({
  onRetry,
  maxRetries = 3,
  retryDelay = 1000,
  children = 'Retry',
  className = '',
}: RetryButtonProps): JSX.Element {
  const [retryCount, setRetryCount] = useState(0);
  const [isRetrying, setIsRetrying] = useState(false);

  const handleRetry = useCallback(async () => {
    if (retryCount >= maxRetries) return;
    
    setIsRetrying(true);
    try {
      await onRetry();
      setRetryCount(0);
    } catch {
      setRetryCount((prev) => prev + 1);
    } finally {
      setIsRetrying(false);
    }
  }, [onRetry, retryCount, maxRetries]);

  return (
    <button
      onClick={handleRetry}
      disabled={retryCount >= maxRetries || isRetrying}
      className={`px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white font-medium rounded-lg transition-colors ${className}`}
    >
      {isRetrying ? 'Retrying...' : `${children} (${maxRetries - retryCount} left)`}
    </button>
  );
}

interface ErrorDisplayProps {
  error: Error | string;
  onDismiss?: () => void;
  onRetry?: () => void;
  variant?: 'banner' | 'card' | 'inline';
}

export function ErrorDisplayMessage({
  error,
  onDismiss,
  onRetry,
  variant = 'card',
}: ErrorDisplayProps): JSX.Element {
  const errorMessage = typeof error === 'string' ? error : error.message;

  if (variant === 'inline') {
    return (
      <span className="text-red-600 dark:text-red-400 text-sm">
        {errorMessage}
        {onRetry && (
          <button onClick={onRetry} className="ml-2 underline hover:no-underline">
            Retry
          </button>
        )}
      </span>
    );
  }

  if (variant === 'banner') {
    return (
      <div className="bg-red-600 text-white px-4 py-3 rounded-lg flex items-center justify-between">
        <div className="flex items-center gap-3">
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <span>{errorMessage}</span>
        </div>
        <div className="flex gap-2">
          {onRetry && (
            <button
              onClick={onRetry}
              className="px-3 py-1 bg-white/20 hover:bg-white/30 rounded transition-colors"
            >
              Retry
            </button>
          )}
          {onDismiss && (
            <button
              onClick={onDismiss}
              className="p-1 hover:bg-white/20 rounded transition-colors"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4">
      <div className="flex items-start gap-3">
        <div className="flex-shrink-0">
          <svg className="w-5 h-5 text-red-600 dark:text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </div>
        <div className="flex-1">
          <h3 className="text-red-800 dark:text-red-200 font-medium mb-1">Error</h3>
          <p className="text-red-600 dark:text-red-400 text-sm">{errorMessage}</p>
        </div>
        <div className="flex gap-2">
          {onRetry && (
            <button
              onClick={onRetry}
              className="px-3 py-1 bg-red-100 dark:bg-red-800 text-red-700 dark:text-red-200 rounded hover:bg-red-200 dark:hover:bg-red-700 transition-colors"
            >
              Retry
            </button>
          )}
          {onDismiss && (
            <button
              onClick={onDismiss}
              className="p-1 text-red-600 dark:text-red-400 hover:bg-red-100 dark:hover:bg-red-800 rounded transition-colors"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

interface LoadingStateProps {
  message?: string;
  size?: 'sm' | 'md' | 'lg';
}

export function LoadingStateIndicator({
  message = 'Loading...',
  size = 'md',
}: LoadingStateProps): JSX.Element {
  const sizeClasses = {
    sm: 'w-4 h-4',
    md: 'w-8 h-8',
    lg: 'w-12 h-12',
  };

  const textSizes = {
    sm: 'text-sm',
    md: 'text-base',
    lg: 'text-lg',
  };

  return (
    <div className="flex flex-col items-center justify-center gap-4">
      <div className={`${sizeClasses[size]} border-4 border-blue-200 border-t-blue-600 rounded-full animate-spin`} />
      <p className={`${textSizes[size]} text-gray-600 dark:text-gray-400`}>{message}</p>
    </div>
  );
}

interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: {
    label: string;
    onClick: () => void;
  };
}

export function EmptyStateDisplay({
  icon,
  title,
  description,
  action,
}: EmptyStateProps): JSX.Element {
  return (
    <div className="flex flex-col items-center justify-center py-12 px-4">
      {icon && <div className="mb-4 text-gray-400 dark:text-gray-500">{icon}</div>}
      <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">{title}</h3>
      {description && (
        <p className="text-gray-500 dark:text-gray-400 text-center mb-6 max-w-md">
          {description}
        </p>
      )}
      {action && (
        <button
          onClick={action.onClick}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg transition-colors"
        >
          {action.label}
        </button>
      )}
    </div>
  );
}
