/**
 * Enhanced WebSocket Client with Auto-Reconnection
 * 
 * Features:
 * - Exponential backoff reconnection
 * - Heartbeat detection
 * - Automatic subscription recovery
 * - Connection state management
 * - Error handling with recovery
 */

type MessageType = 
  | 'agent_status_change'
  | 'task_created'
  | 'task_status_change'
  | 'task_completed'
  | 'task_failed'
  | 'cluster_stats_update'
  | 'notification'
  | 'heartbeat'
  | 'error'
  | 'connected'
  | 'disconnected';

interface WebSocketMessage {
  type: MessageType;
  data?: any;
  message?: string;
  timestamp?: number;
}

interface WebSocketOptions {
  url: string;
  token?: string;
  autoReconnect?: boolean;
  maxReconnectAttempts?: number;
  baseDelay?: number;
  maxDelay?: number;
  heartbeatInterval?: number;
  heartbeatTimeout?: number;
  debug?: boolean;
}

type ConnectionState = 
  | 'disconnected'
  | 'connecting'
  | 'authenticating'
  | 'connected'
  | 'reconnecting';

type MessageHandler = (message: WebSocketMessage) => void;
type ConnectionStateHandler = (state: ConnectionState) => void;

export class EnhancedWebSocketClient {
  private ws: WebSocket | null = null;
  private options: Required<WebSocketOptions>;
  private state: ConnectionState = 'disconnected';
  private reconnectAttempts = 0;
  private subscriptions: Set<string> = new Set();
  private messageHandlers: Map<string, MessageHandler[]> = new Map();
  private stateHandlers: ConnectionStateHandler[] = [];
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null;
  private heartbeatTimeoutTimer: ReturnType<typeof setTimeout> | null = null;
  private lastHeartbeatReceived: number = Date.now();

  constructor(options: WebSocketOptions) {
    this.options = {
      url: options.url,
      token: options.token || '',
      autoReconnect: options.autoReconnect !== false,
      maxReconnectAttempts: options.maxReconnectAttempts || 20,
      baseDelay: options.baseDelay || 1000,
      maxDelay: options.maxDelay || 30000,
      heartbeatInterval: options.heartbeatInterval || 30000,
      heartbeatTimeout: options.heartbeatTimeout || 10000,
      debug: options.debug !== false,
    };
  }

  /**
   * Connect to WebSocket server
   */
  async connect(): Promise<void> {
    if (this.state !== 'disconnected') {
      this.log('Already connecting or connected');
      return;
    }

    this.setState('connecting');
    this.log('Connecting to', this.options.url);

    try {
      this.ws = new WebSocket(this.options.url);
      
      this.ws.onopen = this.handleOpen.bind(this);
      this.ws.onmessage = this.handleMessage.bind(this);
      this.ws.onclose = this.handleClose.bind(this);
      this.ws.onerror = this.handleError.bind(this);

    } catch (error) {
      this.log('Connection error:', error);
      this.handleReconnect();
    }
  }

  /**
   * Disconnect from WebSocket server
   */
  disconnect(): void {
    this.log('Disconnecting...');
    
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
    
    if (this.heartbeatTimeoutTimer) {
      clearTimeout(this.heartbeatTimeoutTimer);
      this.heartbeatTimeoutTimer = null;
    }

    if (this.ws) {
      this.ws.close(1000, 'Client disconnect');
      this.ws = null;
    }
    
    this.setState('disconnected');
  }

  /**
   * Subscribe to a channel
   */
  subscribe(channel: string): void {
    this.subscriptions.add(channel);
    
    if (this.state === 'connected') {
      this.send({
        type: 'subscribe',
        data: { channel },
      });
    }
  }

  /**
   * Unsubscribe from a channel
   */
  unsubscribe(channel: string): void {
    this.subscriptions.delete(channel);
    
    if (this.state === 'connected') {
      this.send({
        type: 'unsubscribe',
        data: { channel },
      });
    }
  }

  /**
   * Register message handler
   */
  onMessage(type: MessageType | '*', handler: MessageHandler): () => void {
    if (!this.messageHandlers.has(type)) {
      this.messageHandlers.set(type, []);
    }
    this.messageHandlers.get(type)!.push(handler);
    
    return () => {
      const handlers = this.messageHandlers.get(type);
      if (handlers) {
        const index = handlers.indexOf(handler);
        if (index > -1) {
          handlers.splice(index, 1);
        }
      }
    };
  }

  /**
   * Register connection state handler
   */
  onStateChange(handler: ConnectionStateHandler): () => void {
    this.stateHandlers.push(handler);
    return () => {
      const index = this.stateHandlers.indexOf(handler);
      if (index > -1) {
        this.stateHandlers.splice(index, 1);
      }
    };
  }

  /**
   * Send a message
   */
  send(message: Partial<WebSocketMessage>): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      const fullMessage: WebSocketMessage = {
        type: message.type || 'notification',
        data: message.data,
        message: message.message,
        timestamp: Date.now(),
      };
      this.ws.send(JSON.stringify(fullMessage));
    } else {
      this.log('Cannot send message, not connected');
    }
  }

  /**
   * Get current connection state
   */
  getState(): ConnectionState {
    return this.state;
  }

  /**
   * Check if connected
   */
  isConnected(): boolean {
    return this.state === 'connected';
  }

  // ========== Private Methods ==========

  private setState(state: ConnectionState): void {
    if (this.state !== state) {
      this.log('State changed:', this.state, '→', state);
      this.state = state;
      this.stateHandlers.forEach(handler => handler(state));
    }
  }

  private handleOpen(): void {
    this.log('Connected to WebSocket server');
    this.reconnectAttempts = 0;
    this.setState('authenticating');
    
    // Send authentication token if available
    if (this.options.token) {
      this.send({
        type: 'authenticate',
        data: { token: this.options.token },
      });
    }
    
    // Connection considered authenticated immediately if no token
    if (!this.options.token) {
      this.handleAuthenticated();
    }
  }

  private handleAuthenticated(): void {
    this.setState('connected');
    
    // Resubscribe to channels
    this.subscriptions.forEach(channel => {
      this.send({
        type: 'subscribe',
        data: { channel },
      });
    });
    
    // Start heartbeat
    this.startHeartbeat();
    
    // Notify connection established
    this.emitMessage({
      type: 'connected',
      message: 'Successfully connected',
    });
  }

  private handleMessage(event: MessageEvent): void {
    try {
      const message: WebSocketMessage = JSON.parse(event.data);
      this.log('Received message:', message.type);
      
      // Handle heartbeat
      if (message.type === 'heartbeat') {
        this.lastHeartbeatReceived = Date.now();
        this.handleHeartbeatResponse();
        return;
      }
      
      // Handle authentication
      if (message.type === 'connected' && this.state === 'authenticating') {
        this.handleAuthenticated();
        return;
      }
      
      // Emit to handlers
      this.emitMessage(message);
      
    } catch (error) {
      this.log('Failed to parse message:', error);
    }
  }

  private handleClose(event: CloseEvent): void {
    this.log('Connection closed:', event.code, event.reason);
    
    this.stopHeartbeat();
    
    if (this.state !== 'disconnected') {
      this.setState('disconnected');
      this.emitMessage({
        type: 'disconnected',
        message: `Connection closed: ${event.reason || event.code}`,
      });
      
      if (this.options.autoReconnect && event.code !== 1000) {
        this.handleReconnect();
      }
    }
  }

  private handleError(event: Event): void {
    this.log('WebSocket error:', event);
    // Don't reconnect on error, let onclose handle it
  }

  private handleReconnect(): void {
    if (!this.options.autoReconnect) {
      return;
    }
    
    if (this.reconnectAttempts >= this.options.maxReconnectAttempts) {
      this.log('Max reconnection attempts reached, giving up');
      this.setState('disconnected');
      return;
    }
    
    this.setState('reconnecting');
    this.reconnectAttempts++;
    
    // Exponential backoff with jitter
    const delay = this.calculateReconnectDelay(this.reconnectAttempts);
    this.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts}/${this.options.maxReconnectAttempts})`);
    
    setTimeout(() => {
      if (this.state === 'reconnecting') {
        this.connect();
      }
    }, delay);
  }

  private calculateReconnectDelay(attempt: number): number {
    // Exponential backoff
    const backoff = Math.min(
      this.options.baseDelay * Math.pow(1.5, attempt - 1),
      this.options.maxDelay
    );
    
    // Add jitter to prevent thundering herd
    const jitter = Math.random() * 0.3 + 0.85; // 0.85-1.15 multiplier
    return Math.floor(backoff * jitter);
  }

  private startHeartbeat(): void {
    this.stopHeartbeat();
    
    // Send periodic heartbeats
    this.heartbeatTimer = setInterval(() => {
      this.send({ type: 'heartbeat' });
      
      // Expect response within timeout
      this.heartbeatTimeoutTimer = setTimeout(() => {
        const timeSinceLastHeartbeat = Date.now() - this.lastHeartbeatReceived;
        if (timeSinceLastHeartbeat > this.options.heartbeatTimeout) {
          this.log('Heartbeat timeout, reconnecting...');
          this.disconnect();
          this.handleReconnect();
        }
      }, this.options.heartbeatTimeout);
    }, this.options.heartbeatInterval);
  }

  private stopHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
    if (this.heartbeatTimeoutTimer) {
      clearTimeout(this.heartbeatTimeoutTimer);
      this.heartbeatTimeoutTimer = null;
    }
  }

  private handleHeartbeatResponse(): void {
    if (this.heartbeatTimeoutTimer) {
      clearTimeout(this.heartbeatTimeoutTimer);
      this.heartbeatTimeoutTimer = null;
    }
  }

  private emitMessage(message: WebSocketMessage): void {
    // Call wildcard handlers
    const wildcardHandlers = this.messageHandlers.get('*') || [];
    wildcardHandlers.forEach(handler => handler(message));
    
    // Call type-specific handlers
    const typeHandlers = this.messageHandlers.get(message.type) || [];
    typeHandlers.forEach(handler => handler(message));
  }

  private log(...args: any[]): void {
    if (this.options.debug) {
      console.log('[WebSocket]', ...args);
    }
  }
}

// ========== Convenience Hooks (for React) ==========

// This could be used in a React component:
// const { state, send, subscribe, unsubscribe } = useWebSocket(url, token);

// For other frameworks, use EnhancedWebSocketClient directly.
