import React, { useState, useCallback, useRef, useEffect, useMemo } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { GlobalApplicationErrorBoundary } from './components/error_handling';
import { LazyClusterDashboardView, LazyAgentManagementPanel, LazyTaskExecutionConsole } from './utils/component_lazy_loading_utilities';
import { useWebSocketService } from './services/websocket_real_time_communication_service';
import { httpClient } from './api/http_client_configuration';
import './index.css';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5,
      gcTime: 1000 * 60 * 10,
      retry: 3,
      refetchOnWindowFocus: false,
    },
  },
});

function ApplicationRoutes() {
  const wsService = useWebSocketService({
    url: `ws://${window.location.host}/api/v1/ws`,
    autoReconnect: true,
    reconnectInterval: 5000,
    heartbeatInterval: 30000,
  });

  useEffect(() => {
    if (wsService.isConnected) {
      wsService.subscribe('agents');
      wsService.subscribe('tasks');
      wsService.subscribe('notifications');
    }
    return () => {
      if (wsService.isConnected) {
        wsService.unsubscribe('agents');
        wsService.unsubscribe('tasks');
        wsService.unsubscribe('notifications');
      }
    };
  }, [wsService.isConnected]);

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <header className="bg-white dark:bg-gray-800 shadow">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
              Agent Cluster Orchestration
            </h1>
            <div className="flex items-center gap-4">
              <div className={`w-3 h-3 rounded-full ${wsService.isConnected ? 'bg-green-500' : 'bg-red-500'}`} />
              <span className="text-sm text-gray-600 dark:text-gray-400">
                {wsService.isConnected ? 'Connected' : 'Disconnected'}
              </span>
            </div>
          </div>
        </div>
      </header>
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <Routes>
          <Route path="/" element={<LazyClusterDashboardView />} />
          <Route path="/agents" element={<LazyAgentManagementPanel />} />
          <Route path="/tasks" element={<LazyTaskExecutionConsole />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}

export function ApplicationRootComponent() {
  const [isOnline, setIsOnline] = useState(navigator.onLine);

  useEffect(() => {
    const handleOnline = () => setIsOnline(true);
    const handleOffline = () => setIsOnline(false);
    
    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);
    
    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  const handleError = useCallback((error: Error, errorInfo: React.ErrorInfo) => {
    console.error('Application error:', error, errorInfo);
  }, []);

  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <GlobalApplicationErrorBoundary onError={handleError}>
          {!isOnline && (
            <div className="fixed top-0 left-0 right-0 bg-yellow-500 text-white px-4 py-2 text-center z-50">
              You are currently offline. Some features may not work properly.
            </div>
          )}
          <ApplicationRoutes />
        </GlobalApplicationErrorBoundary>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default ApplicationRootComponent;
