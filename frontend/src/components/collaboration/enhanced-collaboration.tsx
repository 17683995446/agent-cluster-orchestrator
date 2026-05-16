/**
 * Phase 1: 增强实时协作UI
 * 完整的实时协作组件，包括用户状态、任务更新、通知系统
 */

import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import { toast } from 'sonner';
import { Bell, Users, Activity, AlertCircle, CheckCircle2, Clock, Eye } from 'lucide-react';

// ============== 类型定义 ==============

export interface CollaborationUser {
  user_id: string;
  username: string;
  avatar_url?: string;
  status: 'online' | 'away' | 'busy' | 'offline';
  timestamp: string;
}

export interface TaskUpdate {
  task_id: string;
  status?: string;
  progress?: number;
  result?: Record<string, unknown>;
  error?: string;
  agent_id?: string;
  message?: string;
  timestamp: string;
}

export interface AgentUpdate {
  agent_id: string;
  name?: string;
  status?: string;
  current_task_id?: string;
  timestamp: string;
}

export interface Notification {
  notification_id: string;
  type: 'info' | 'warning' | 'success' | 'error';
  title: string;
  message: string;
  data?: Record<string, unknown>;
  actionable: boolean;
  action_label?: string;
  timestamp: string;
}

interface WebSocketMessage {
  type: string;
  data: Record<string, unknown>;
}

// ============== 协作上下文 ==============

interface CollaborationContextValue {
  // 连接状态
  isConnected: boolean;
  connect: (userId: string) => Promise<void>;
  disconnect: () => void;
  
  // 用户管理
  currentUser: CollaborationUser | null;
  onlineUsers: CollaborationUser[];
  updateUserStatus: (status: CollaborationUser['status']) => void;
  
  // 任务观察
  watchedTasks: Set<string>;
  watchTask: (taskId: string) => void;
  unwatchTask: (taskId: string) => void;
  
  // 任务更新
  taskUpdates: TaskUpdate[];
  
  // 代理状态
  agentUpdates: AgentUpdate[];
  
  // 通知系统
  notifications: Notification[];
  dismissNotification: (id: string) => void;
  clearAllNotifications: () => void;
}

const CollaborationContext = createContext<CollaborationContextValue | null>(null);

// ============== WebSocket Hook ==============

const RECONNECT_DELAY = 3000;
const HEARTBEAT_INTERVAL = 25000;

interface CollaborationProviderProps {
  children: React.ReactNode;
  websocketUrl?: string;
}

export const CollaborationProvider: React.FC<CollaborationProviderProps> = ({
  children,
  websocketUrl = 'ws://localhost:8000/api/v1/ws'
}) => {
  const [isConnected, setIsConnected] = useState(false);
  const [currentUser, setCurrentUser] = useState<CollaborationUser | null>(null);
  const [onlineUsers, setOnlineUsers] = useState<CollaborationUser[]>([]);
  const [watchedTasks, setWatchedTasks] = useState<Set<string>>(new Set());
  const [taskUpdates, setTaskUpdates] = useState<TaskUpdate[]>([]);
  const [agentUpdates, setAgentUpdates] = useState<AgentUpdate[]>([]);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  
  const wsRef = useRef<WebSocket | null>(null);
  const heartbeatTimerRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectTimerRef = useRef<NodeJS.Timeout | null>(null);
  const userIdRef = useRef<string | null>(null);
  
  // 发送消息
  const sendMessage = useCallback((type: string, data: Record<string, unknown> = {}) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type, data }));
    }
  }, []);
  
  // 启动心跳
  const startHeartbeat = useCallback(() => {
    if (heartbeatTimerRef.current) {
      clearInterval(heartbeatTimerRef.current);
    }
    
    heartbeatTimerRef.current = setInterval(() => {
      sendMessage('heartbeat');
    }, HEARTBEAT_INTERVAL);
  }, [sendMessage]);
  
  // 停止心跳
  const stopHeartbeat = useCallback(() => {
    if (heartbeatTimerRef.current) {
      clearInterval(heartbeatTimerRef.current);
      heartbeatTimerRef.current = null;
    }
  }, []);
  
  // 处理接收到的消息
  const handleMessage = useCallback((event: MessageEvent) => {
    try {
      const message: WebSocketMessage = JSON.parse(event.data);
      
      switch (message.type) {
        case 'initial_state':
          // 初始化状态
          if (message.data.users) {
            setOnlineUsers(message.data.users as CollaborationUser[]);
          }
          break;
          
        case 'user_presence_update':
          // 用户在线状态更新
          const presence = message.data as unknown as CollaborationUser;
          setOnlineUsers(prev => {
            const filtered = prev.filter(u => u.user_id !== presence.user_id);
            if (presence.status !== 'offline') {
              filtered.push(presence);
            }
            return filtered;
          });
          break;
          
        case 'task_updated':
          // 任务更新
          const taskUpdate = message.data as unknown as TaskUpdate;
          setTaskUpdates(prev => [taskUpdate, ...prev].slice(0, 100));
          
          // 如果是自己观察的任务，显示通知
          if (watchedTasks.has(taskUpdate.task_id)) {
            const notification: Notification = {
              notification_id: `task-${taskUpdate.task_id}-${Date.now()}`,
              type: taskUpdate.status === 'COMPLETED' ? 'success' : 
                    taskUpdate.status === 'FAILED' ? 'error' : 'info',
              title: '任务更新',
              message: taskUpdate.message || `任务 ${taskUpdate.task_id} 状态: ${taskUpdate.status}`,
              actionable: true,
              action_label: '查看任务',
              data: { task_id: taskUpdate.task_id },
              timestamp: taskUpdate.timestamp
            };
            setNotifications(prev => [notification, ...prev].slice(0, 50));
          }
          break;
          
        case 'agent_status_changed':
          // 代理状态更新
          const agentUpdate = message.data as unknown as AgentUpdate;
          setAgentUpdates(prev => [agentUpdate, ...prev].slice(0, 50));
          break;
          
        case 'notification':
          // 通知
          const notification = message.data as unknown as Notification;
          setNotifications(prev => [notification, ...prev].slice(0, 50));
          
          // 显示toast通知
          switch (notification.type) {
            case 'success':
              toast.success(notification.title, { description: notification.message });
              break;
            case 'error':
              toast.error(notification.title, { description: notification.message });
              break;
            case 'warning':
              toast.warning(notification.title, { description: notification.message });
              break;
            default:
              toast.info(notification.title, { description: notification.message });
          }
          break;
          
        case 'heartbeat':
          // 心跳响应
          break;
      }
    } catch (error) {
      console.error('Failed to parse WebSocket message:', error);
    }
  }, [watchedTasks]);
  
  // 连接WebSocket
  const connect = useCallback(async (userId: string) => {
    // 断开现有连接
    if (wsRef.current) {
      wsRef.current.close();
    }
    
    userIdRef.current = userId;
    
    try {
      const url = `${websocketUrl}?user_id=${userId}`;
      const ws = new WebSocket(url);
      wsRef.current = ws;
      
      ws.onopen = () => {
        console.log('WebSocket connected');
        setIsConnected(true);
        
        // 设置当前用户
        const user: CollaborationUser = {
          user_id: userId,
          username: `User_${userId}`,
          status: 'online',
          timestamp: new Date().toISOString()
        };
        setCurrentUser(user);
        
        // 发送用户状态
        sendMessage('user_presence_update', user);
        
        // 启动心跳
        startHeartbeat();
      };
      
      ws.onmessage = handleMessage;
      
      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        setIsConnected(false);
      };
      
      ws.onclose = (event) => {
        console.log('WebSocket closed:', event.code);
        setIsConnected(false);
        stopHeartbeat();
        
        // 自动重连
        if (userIdRef.current) {
          reconnectTimerRef.current = setTimeout(() => {
            connect(userIdRef.current!);
          }, RECONNECT_DELAY);
        }
      };
      
    } catch (error) {
      console.error('Failed to connect WebSocket:', error);
      setIsConnected(false);
    }
  }, [websocketUrl, handleMessage, startHeartbeat, stopHeartbeat, sendMessage]);
  
  // 断开连接
  const disconnect = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
    }
    stopHeartbeat();
    
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    
    setIsConnected(false);
    userIdRef.current = null;
  }, [stopHeartbeat]);
  
  // 更新用户状态
  const updateUserStatus = useCallback((status: CollaborationUser['status']) => {
    if (!currentUser) return;
    
    const updatedUser = { ...currentUser, status, timestamp: new Date().toISOString() };
    setCurrentUser(updatedUser);
    sendMessage('user_presence_update', updatedUser);
  }, [currentUser, sendMessage]);
  
  // 观察任务
  const watchTask = useCallback((taskId: string) => {
    setWatchedTasks(prev => {
      const updated = new Set(prev);
      updated.add(taskId);
      return updated;
    });
    sendMessage('task_watch', { task_id: taskId });
  }, [sendMessage]);
  
  // 取消观察任务
  const unwatchTask = useCallback((taskId: string) => {
    setWatchedTasks(prev => {
      const updated = new Set(prev);
      updated.delete(taskId);
      return updated;
    });
    sendMessage('task_unwatch', { task_id: taskId });
  }, [sendMessage]);
  
  // 关闭通知
  const dismissNotification = useCallback((id: string) => {
    setNotifications(prev => prev.filter(n => n.notification_id !== id));
  }, []);
  
  // 清除所有通知
  const clearAllNotifications = useCallback(() => {
    setNotifications([]);
  }, []);
  
  // 组件卸载时清理
  useEffect(() => {
    return () => {
      disconnect();
    };
  }, [disconnect]);
  
  const value: CollaborationContextValue = {
    isConnected,
    connect,
    disconnect,
    currentUser,
    onlineUsers,
    updateUserStatus,
    watchedTasks,
    watchTask,
    unwatchTask,
    taskUpdates,
    agentUpdates,
    notifications,
    dismissNotification,
    clearAllNotifications
  };
  
  return (
    <CollaborationContext.Provider value={value}>
      {children}
    </CollaborationContext.Provider>
  );
};

// ============== Hook 暴露 ==============

export const useCollaboration = (): CollaborationContextValue => {
  const context = useContext(CollaborationContext);
  if (!context) {
    throw new Error('useCollaboration must be used within a CollaborationProvider');
  }
  return context;
};

// ============== UI组件 ==============

export const UserPresenceIndicator: React.FC = () => {
  const { isConnected, onlineUsers, currentUser } = useCollaboration();
  
  if (!isConnected) {
    return (
      <div className="flex items-center gap-2 px-3 py-2 bg-red-50 border border-red-200 rounded-lg">
        <div className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
        <span className="text-sm text-red-600">离线</span>
      </div>
    );
  }
  
  return (
    <div className="flex items-center gap-4 px-4 py-2 bg-white border border-gray-200 rounded-lg shadow-sm">
      <div className="flex items-center gap-2">
        <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
        <span className="text-sm text-green-700 font-medium">在线</span>
      </div>
      <div className="flex items-center gap-1">
        <Users className="w-4 h-4 text-gray-500" />
        <span className="text-sm text-gray-600">{onlineUsers.length} 在线</span>
      </div>
    </div>
  );
};

export const NotificationCenter: React.FC = () => {
  const { notifications, dismissNotification, clearAllNotifications } = useCollaboration();
  const [isOpen, setIsOpen] = useState(false);
  
  if (notifications.length === 0) {
    return null;
  }
  
  const unreadCount = notifications.length;
  
  const getIcon = (type: Notification['type']) => {
    switch (type) {
      case 'success':
        return <CheckCircle2 className="w-5 h-5 text-green-500" />;
      case 'error':
        return <AlertCircle className="w-5 h-5 text-red-500" />;
      case 'warning':
        return <AlertCircle className="w-5 h-5 text-yellow-500" />;
      default:
        return <Bell className="w-5 h-5 text-blue-500" />;
    }
  };
  
  const getBgColor = (type: Notification['type']) => {
    switch (type) {
      case 'success':
        return 'bg-green-50 border-green-200';
      case 'error':
        return 'bg-red-50 border-red-200';
      case 'warning':
        return 'bg-yellow-50 border-yellow-200';
      default:
        return 'bg-blue-50 border-blue-200';
    }
  };
  
  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="relative p-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"
      >
        <Bell className="w-5 h-5" />
        {unreadCount > 0 && (
          <span className="absolute -top-1 -right-1 w-5 h-5 bg-red-500 text-white text-xs font-medium flex items-center justify-center rounded-full">
            {unreadCount}
          </span>
        )}
      </button>
      
      {isOpen && (
        <div className="absolute right-0 top-12 w-80 bg-white border border-gray-200 rounded-xl shadow-2xl z-50 max-h-96 overflow-auto">
          <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
            <h3 className="font-semibold text-gray-900">通知</h3>
            <button
              onClick={clearAllNotifications}
              className="text-xs text-gray-500 hover:text-gray-700"
            >
              清除全部
            </button>
          </div>
          
          <div className="p-2 space-y-2">
            {notifications.map(notification => (
              <div
                key={notification.notification_id}
                className={`p-3 rounded-lg border ${getBgColor(notification.type)} flex items-start gap-3`}
              >
                {getIcon(notification.type)}
                <div className="flex-1 min-w-0">
                  <div className="font-medium text-gray-900 text-sm">{notification.title}</div>
                  <div className="text-xs text-gray-600 mt-1">{notification.message}</div>
                  {notification.actionable && notification.action_label && (
                    <button className="mt-2 text-xs font-medium text-blue-600 hover:text-blue-800">
                      {notification.action_label}
                    </button>
                  )}
                </div>
                <button
                  onClick={() => dismissNotification(notification.notification_id)}
                  className="text-gray-400 hover:text-gray-600"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export const OnlineUsersList: React.FC = () => {
  const { onlineUsers, currentUser } = useCollaboration();
  
  if (onlineUsers.length === 0) {
    return null;
  }
  
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'online':
        return 'bg-green-500';
      case 'away':
        return 'bg-yellow-500';
      case 'busy':
        return 'bg-red-500';
      default:
        return 'bg-gray-400';
    }
  };
  
  return (
    <div className="p-4 bg-white border border-gray-200 rounded-xl shadow-sm">
      <h3 className="text-sm font-semibold text-gray-900 mb-3 flex items-center gap-2">
        <Users className="w-4 h-4" />
        在线用户 ({onlineUsers.length})
      </h3>
      <div className="space-y-2">
        {onlineUsers.map(user => (
          <div
            key={user.user_id}
            className={`flex items-center gap-3 p-2 rounded-lg ${
              user.user_id === currentUser?.user_id ? 'bg-blue-50' : 'hover:bg-gray-50'
            }`}
          >
            <div className="relative">
              <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center text-white text-xs font-medium">
                {user.username.charAt(0).toUpperCase()}
              </div>
              <div className={`absolute -bottom-0.5 -right-0.5 w-3 h-3 rounded-full border-2 border-white ${
                getStatusColor(user.status)
              }`} />
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium text-gray-900 truncate">
                {user.username}
                {user.user_id === currentUser?.user_id && (
                  <span className="ml-1 text-xs text-blue-600">(你)</span>
                )}
              </div>
              <div className="text-xs text-gray-500">{user.status}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export const TaskWatcherBadge: React.FC<{ taskId: string }> = ({ taskId }) => {
  const { watchedTasks, watchTask, unwatchTask } = useCollaboration();
  const isWatching = watchedTasks.has(taskId);
  
  return (
    <button
      onClick={() => isWatching ? unwatchTask(taskId) : watchTask(taskId)}
      className={`flex items-center gap-1 px-3 py-1 rounded-full text-xs font-medium transition-colors ${
        isWatching 
          ? 'bg-blue-100 text-blue-700 hover:bg-blue-200'
          : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
      }`}
    >
      <Eye className="w-3 h-3" />
      {isWatching ? '观察中' : '观察'}
    </button>
  );
};
