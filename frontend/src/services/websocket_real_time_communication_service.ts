import { useEffect, useRef, useCallback, useState } from 'react';
import { useAppGlobalStateStore } from '../stores/app_global_state_store';

export type WebSocketMessageType =
  | 'agent_status_change'
  | 'task_created'
  | 'task_status_change'
  | 'task_completed'
  | 'task_failed'
  | 'cluster_stats_update'
  | 'notification'
  | 'heartbeat'
  | 'error';

export interface WebSocketMessage {
  type: WebSocketMessageType;
  data?: unknown;
  message?: string;
  timestamp?: string;
  client_id?: string;
}

export interface WebSocketConnectionOptions {
  url: string;
  token?: string;
  autoReconnect?: boolean;
  reconnectInterval?: number;
  heartbeatInterval?: number;
}

export interface UseWebSocketServiceResult {
  isConnected: boolean;
  connectionState: 'connecting' | 'connected' | 'disconnected' | 'reconnecting';
  lastMessage: WebSocketMessage | null;
  error: string | null;
  subscribe: (channel: string) => void;
  unsubscribe: (channel: string) => void;
  sendMessage: (message: Partial<WebSocketMessage>) => void;
  reconnect: () => void;
  disconnect: () => void;
}

export function useWebSocketService(options: WebSocketConnectionOptions): UseWebSocketServiceResult {
  const {
    url,
    token,
    autoReconnect = true,
    reconnectInterval = 5000,
    heartbeatInterval = 30000,
  } = options;

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const heartbeatIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const subscriptionsRef = useRef<Set<string>>(new Set());

  const [connectionState, setConnectionState] = useState<
    'connecting' | 'connected' | 'disconnected' | 'reconnecting'
  >('disconnected');
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);
  const [error, setError] = useState<string | null>(null);

  const { updateAgentStatus, updateTaskStatus, addNotification } = useAppGlobalStateStore();

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    setConnectionState('connecting');
    setError(null);

    const wsUrl = token ? `${url}?token=${encodeURIComponent(token)}` : url;
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      setConnectionState('connected');
      setError(null);
      subscriptionsRef.current.forEach((channel) => {
        ws.send(JSON.stringify({ type: 'subscribe', channel }));
      });
      if (heartbeatInterval > 0) {
        heartbeatIntervalRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'heartbeat' }));
          }
        }, heartbeatInterval);
      }
    };

    ws.onmessage = (event) => {
      try {
        const message: WebSocketMessage = JSON.parse(event.data);
        setLastMessage(message);
        switch (message.type) {
          case 'agent_status_change':
            if (message.data) {
              updateAgentStatus(message.data as { agent_id: string; status: string });
            }
            break;
          case 'task_status_change':
          case 'task_completed':
          case 'task_failed':
            if (message.data) {
              updateTaskStatus(message.data as { task_id: string; status: string });
            }
            break;
          case 'notification':
            addNotification({
              id: Date.now().toString(),
              type: 'info',
              title: 'Notification',
              message: message.message || 'New notification',
              timestamp: new Date().toISOString(),
            });
            break;
        }
      } catch {
        setError('Failed to parse WebSocket message');
      }
    };

    ws.onerror = () => {
      setError('WebSocket connection error');
      setConnectionState('disconnected');
    };

    ws.onclose = () => {
      setConnectionState('disconnected');
      if (heartbeatIntervalRef.current) {
        clearInterval(heartbeatIntervalRef.current);
      }
      if (autoReconnect) {
        setConnectionState('reconnecting');
        reconnectTimeoutRef.current = setTimeout(() => {
          connect();
        }, reconnectInterval);
      }
    };

    wsRef.current = ws;
  }, [url, token, autoReconnect, reconnectInterval, heartbeatInterval, updateAgentStatus, updateTaskStatus, addNotification]);

  const subscribe = useCallback((channel: string) => {
    subscriptionsRef.current.add(channel);
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'subscribe', channel }));
    }
  }, []);

  const unsubscribe = useCallback((channel: string) => {
    subscriptionsRef.current.delete(channel);
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'unsubscribe', channel }));
    }
  }, []);

  const sendMessage = useCallback((message: Partial<WebSocketMessage>) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message));
    }
  }, []);

  const reconnect = useCallback(() => {
    disconnect();
    connect();
  }, [connect]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }
    if (heartbeatIntervalRef.current) {
      clearInterval(heartbeatIntervalRef.current);
    }
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setConnectionState('disconnected');
  }, []);

  useEffect(() => {
    connect();
    return () => {
      disconnect();
    };
  }, [connect, disconnect]);

  return {
    isConnected: connectionState === 'connected',
    connectionState,
    lastMessage,
    error,
    subscribe,
    unsubscribe,
    sendMessage,
    reconnect,
    disconnect,
  };
}

export class WebSocketService {
  private ws: WebSocket | null = null;
  private url: string;
  private token?: string;
  private autoReconnect: boolean;
  private reconnectInterval: number;
  private reconnectTimeout: ReturnType<typeof setTimeout> | null = null;
  private heartbeatInterval: ReturnType<typeof setInterval> | null = null;
  private subscriptions: Set<string> = new Set();
  private messageHandlers: Map<WebSocketMessageType, Set<(message: WebSocketMessage) => void>> = new Map();

  constructor(
    url: string,
    token?: string,
    autoReconnect = true,
    reconnectInterval = 5000
  ) {
    this.url = url;
    this.token = token;
    this.autoReconnect = autoReconnect;
    this.reconnectInterval = reconnectInterval;
  }

  connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      const wsUrl = this.token ? `${this.url}?token=${encodeURIComponent(this.token)}` : this.url;
      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        this.subscriptions.forEach((channel) => {
          this.send({ type: 'subscribe', channel });
        });
        this.startHeartbeat();
        resolve();
      };

      this.ws.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data);
          const handlers = this.messageHandlers.get(message.type);
          handlers?.forEach((handler) => handler(message));
        } catch {
          console.error('Failed to parse WebSocket message');
        }
      };

      this.ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        reject(error);
      };

      this.ws.onclose = () => {
        this.stopHeartbeat();
        if (this.autoReconnect) {
          this.reconnectTimeout = setTimeout(() => {
            this.connect().catch(console.error);
          }, this.reconnectInterval);
        }
      };
    });
  }

  disconnect(): void {
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
    }
    this.stopHeartbeat();
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  send(message: Partial<WebSocketMessage>): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    }
  }

  subscribe(channel: string): void {
    this.subscriptions.add(channel);
    this.send({ type: 'subscribe', channel });
  }

  unsubscribe(channel: string): void {
    this.subscriptions.delete(channel);
    this.send({ type: 'unsubscribe', channel });
  }

  on(type: WebSocketMessageType, handler: (message: WebSocketMessage) => void): void {
    if (!this.messageHandlers.has(type)) {
      this.messageHandlers.set(type, new Set());
    }
    this.messageHandlers.get(type)!.add(handler);
  }

  off(type: WebSocketMessageType, handler: (message: WebSocketMessage) => void): void {
    this.messageHandlers.get(type)?.delete(handler);
  }

  private startHeartbeat(): void {
    this.heartbeatInterval = setInterval(() => {
      this.send({ type: 'heartbeat' });
    }, 30000);
  }

  private stopHeartbeat(): void {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }
  }

  get isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }
}

let wsServiceInstance: WebSocketService | null = null;

export function getWebSocketService(
  baseUrl?: string,
  token?: string
): WebSocketService {
  if (!wsServiceInstance && baseUrl) {
    wsServiceInstance = new WebSocketService(
      baseUrl.replace('http', 'ws') + '/api/v1/ws',
      token
    );
  }
  return wsServiceInstance!;
}

export function initializeWebSocketService(baseUrl: string, token?: string): WebSocketService {
  if (wsServiceInstance) {
    wsServiceInstance.disconnect();
  }
  wsServiceInstance = new WebSocketService(
    baseUrl.replace('http', 'ws') + '/api/v1/ws',
    token
  );
  return wsServiceInstance;
}
