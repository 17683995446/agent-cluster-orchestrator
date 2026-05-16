import React, { Suspense, lazy, ComponentType, ReactNode } from 'react';
import { LoadingStateIndicator } from '../components/error_handling';

export interface LazyLoadOptions {
  fallback?: ReactNode;
  ssr?: boolean;
  prefetch?: boolean;
}

export function createLazyComponent<P extends object>(
  importFn: () => Promise<{ default: ComponentType<P> }>,
  options: LazyLoadOptions = {}
): React.FC<P> {
  const { fallback = <LoadingStateIndicator message="Loading..." />, ssr = false } = options;
  
  const LazyComponent = lazy(importFn);
  
  return function LazyLoadedComponent(props: P) {
    if (ssr) {
      return (
        <Suspense fallback={fallback}>
          <LazyComponent {...props} />
        </Suspense>
      );
    }
    
    return (
      <Suspense fallback={fallback}>
        <LazyComponent {...props} />
      </Suspense>
    );
  };
}

export const LazyClusterDashboardView = createLazyComponent(
  () => import('../components/dashboard/cluster_dashboard_view').then(m => ({ default: m.ClusterDashboardView })),
  { fallback: <LoadingStateIndicator message="Loading dashboard..." /> }
);

export const LazyAgentManagementPanel = createLazyComponent(
  () => import('../components/agents/agent_management_panel').then(m => ({ default: m.AgentManagementPanel })),
  { fallback: <LoadingStateIndicator message="Loading agent management..." /> }
);

export const LazyTaskExecutionConsole = createLazyComponent(
  () => import('../components/tasks/task_execution_console').then(m => ({ default: m.TaskExecutionConsole })),
  { fallback: <LoadingStateIndicator message="Loading task console..." /> }
);

export const LazyClusterStatsView = createLazyComponent(
  () => import('../components/dashboard/cluster_stats_view').then(m => ({ default: m.ClusterStatsView })),
  { fallback: <LoadingStateIndicator message="Loading statistics..." /> }
);

export const LazySettingsPanel = createLazyComponent(
  () => import('../components/settings/settings_panel').then(m => ({ default: m.SettingsPanel })),
  { fallback: <LoadingStateIndicator message="Loading settings..." /> }
);

export function withLazyLoading<P extends object>(
  WrappedComponent: ComponentType<P>,
  options: LazyLoadOptions = {}
): React.FC<P> {
  const { fallback = <LoadingStateIndicator /> } = options;
  
  return function WithLazyLoadingComponent(props: P) {
    return (
      <Suspense fallback={fallback}>
        <WrappedComponent {...props} />
      </Suspense>
    );
  };
}

export class LazyLoader {
  private cache: Map<string, React.ComponentType<any>> = new Map();
  private loadingPromises: Map<string, Promise<any>> = new Map();
  
  register<T extends object>(
    name: string,
    importFn: () => Promise<{ default: ComponentType<T> }>
  ): void {
    const LazyComponent = lazy(importFn);
    this.cache.set(name, LazyComponent);
  }
  
  get(name: string): React.ComponentType<any> | undefined {
    return this.cache.get(name);
  }
  
  async preload(name: string): Promise<void> {
    const component = this.cache.get(name);
    if (component) {
      const lazyComponent = component as lazy.LazyExoticComponent<any>;
      if (lazyComponent._payload && lazyComponent._payload._result) {
        return;
      }
    }
  }
  
  preloadAll(): Promise<void[]> {
    return Array.from(this.cache.keys()).map(name => this.preload(name));
  }
}

export const lazyLoader = new LazyLoader();

lazyLoader.register('clusterDashboard', () => import('../components/dashboard/cluster_dashboard_view').then(m => ({ default: m.ClusterDashboardView })));
lazyLoader.register('agentManagement', () => import('../components/agents/agent_management_panel').then(m => ({ default: m.AgentManagementPanel })));
lazyLoader.register('taskConsole', () => import('../components/tasks/task_execution_console').then(m => ({ default: m.TaskExecutionConsole })));
