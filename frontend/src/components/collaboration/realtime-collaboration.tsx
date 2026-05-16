/**
 * 实时协作与通知系统
 * 提供实时任务更新、用户状态同步和即时通知功能
 */

import React, { createContext, useContext, useEffect, useRef, useState, useCallback } from 'react';
import { io, Socket } from 'socket.io-client';
import { useToast } from '@/hooks/use-toast';

export interface CollaborationUser {
  id: string;
  name: string;
  avatar?: string;
  color: string;
  status: 'online' | 'away' | 'busy' | 'offline';
  lastSeen?: Date;
}

export interface CollaborationEvent {
  type: 'task_update' | 'user_joined' | 'user_left' | 'cursor_move' | 'typing_start' | 'typing_stop';
  userId?: string;
  taskId?: string;
  data?: Record<string, unknown>;
  timestamp: Date;
}

export interface RealtimeNotification {
  id: string;
  type: 'success' | 'error' | 'warning' | 'info';
  title: string;
  message: string;
  duration?: number;
  action?: {
    label: string;
    onClick: () => void;
  };
}

interface CollaborationContextValue {
  isConnected: boolean;
  currentUser: CollaborationUser | null;
  onlineUsers: CollaborationUser[];
  notifications: RealtimeNotification[];
  
  // 用户管理
  setCurrentUser: (user: CollaborationUser) => void;
  updateUserStatus: (status: CollaborationUser['status']) => void;
  
  // 实时功能
  subscribe: (channel: string, callback: (event: CollaborationEvent) => void) => () => void;
  publish: (channel: string, event: Omit<CollaborationEvent, 'timestamp'>) => void;
  
  // 通知管理
  notify: (notification: Omit<RealtimeNotification, 'id'>) => void;
  dismissNotification: (id: string) => void;
  clearAllNotifications: () => void;
  
  // 任务协作
  watchTask: (taskId: string) => void;
  unwatchTask: (taskId: string) => void;
  broadcastTaskUpdate: (taskId: string, updates: Record<string, unknown>) => void;
}

const CollaborationContext = createContext<CollaborationContextValue | null>(null);

const COLORS = [
  '#3B82F6', '#10B981', '#F59E0B', '#EF4444', 
  '#8B5CF6', '#EC4899', '#06B6D4', '#84CC16'
];

const generateUserColor = (userId: string): string => {
  const hash = userId.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0);
  return COLORS[hash % COLORS.length];
};

interface CollaborationProviderProps {
  children: React.ReactNode;
  websocketUrl?: string;
  currentUserId?: string;
}

export const CollaborationProvider: React.FC<CollaborationProviderProps> = ({
  children,
  websocketUrl = 'ws://localhost:8000/ws',
  currentUserId
}) => {
  const socketRef = useRef<Socket | null>(null);
  const subscriptionsRef = useRef<Map<string, Set<(event: CollaborationEvent) => void>>>(new Map());
  const watchedTasksRef = useRef<Set<string>>(new Set());
  
  const [isConnected, setIsConnected] = useState(false);
  const [currentUser, setCurrentUserState] = useState<CollaborationUser | null>(null);
  const [onlineUsers, setOnlineUsers] = useState<CollaborationUser[]>([]);
  const [notifications, setNotifications] = useState<RealtimeNotification[]>([]);
  
  const { toast } = useToast();

  useEffect(() => {
    const socket = io(websocketUrl, {
      transports: ['websocket'],
      autoConnect: true,
      reconnection: true,
      reconnectionAttempts: 5,
      reconnectionDelay: 1000,
      query: currentUserId ? { userId: currentUserId } : undefined
    });

    socketRef.current = socket;

    socket.on('connect', () => {
      console.log('Collaboration WebSocket connected');
      setIsConnected(true);
      
      if (currentUser) {
        socket.emit('user_join', {
          id: currentUser.id,
          name: currentUser.name,
          avatar: currentUser.avatar,
          color: currentUser.color || generateUserColor(currentUser.id)
        });
      }
    });

    socket.on('disconnect', () => {
      console.log('Collaboration WebSocket disconnected');
      setIsConnected(false);
    });

    socket.on('error', (error: Error) => {
      console.error('WebSocket error:', error);
    });

    socket.on('users_online', (users: CollaborationUser[]) => {
      setOnlineUsers(users);
    });

    socket.on('user_joined', (user: CollaborationUser) => {
      setOnlineUsers(prev => {
        const exists = prev.find(u => u.id === user.id);
        if (exists) return prev;
        return [...prev, user];
      });
      
      notify({
        type: 'info',
        title: '用户加入',
        message: `${user.name} 加入了协作`,
        duration: 3000
      });
    });

    socket.on('user_left', (user: CollaborationUser) => {
      setOnlineUsers(prev => prev.filter(u => u.id !== user.id));
      
      notify({
        type: 'info',
        title: '用户离开',
        message: `${user.name} 离开了协作`,
        duration: 3000
      });
    });

    socket.on('task_update', (data: { taskId: string; updates: Record<string, unknown>; userId: string }) => {
      const event: CollaborationEvent = {
        type: 'task_update',
        taskId: data.taskId,
        userId: data.userId,
        data: data.updates,
        timestamp: new Date()
      };
      
      const callbacks = subscriptionsRef.current.get(`task:${data.taskId}`);
      callbacks?.forEach(callback => callback(event));
    });

    socket.on('broadcast', (event: CollaborationEvent) => {
      const callbacks = subscriptionsRef.current.get('global');
      callbacks?.forEach(callback => callback(event));
    });

    return () => {
      socket.disconnect();
      socketRef.current = null;
    };
  }, [websocketUrl, currentUserId]);

  const setCurrentUser = useCallback((user: CollaborationUser) => {
    const userWithColor = {
      ...user,
      color: user.color || generateUserColor(user.id)
    };
    setCurrentUserState(userWithColor);
    
    if (socketRef.current?.connected) {
      socketRef.current.emit('user_join', userWithColor);
    }
  }, []);

  const updateUserStatus = useCallback((status: CollaborationUser['status']) => {
    if (!currentUser) return;
    
    const updatedUser = { ...currentUser, status };
    setCurrentUserState(updatedUser);
    
    socketRef.current?.emit('user_status_update', {
      userId: currentUser.id,
      status
    });
  }, [currentUser]);

  const subscribe = useCallback((channel: string, callback: (event: CollaborationEvent) => void) => {
    if (!subscriptionsRef.current.has(channel)) {
      subscriptionsRef.current.set(channel, new Set());
    }
    subscriptionsRef.current.get(channel)!.add(callback);
    
    return () => {
      subscriptionsRef.current.get(channel)?.delete(callback);
    };
  }, []);

  const publish = useCallback((channel: string, event: Omit<CollaborationEvent, 'timestamp'>) => {
    socketRef.current?.emit('publish', {
      channel,
      event: { ...event, timestamp: new Date() }
    });
  }, []);

  const notify = useCallback((notification: Omit<RealtimeNotification, 'id'>) => {
    const id = `notification-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    const newNotification: RealtimeNotification = { ...notification, id };
    
    setNotifications(prev => [...prev, newNotification]);
    
    const duration = notification.duration ?? 5000;
    if (duration > 0) {
      setTimeout(() => {
        dismissNotification(id);
      }, duration);
    }

    const toastConfig = {
      title: notification.title,
      description: notification.message,
      variant: notification.type === 'error' ? 'destructive' : 'default',
      action: notification.action ? {
        label: notification.action.label,
        onClick: notification.action.onClick
      } : undefined
    };

    switch (notification.type) {
      case 'success':
        toast({ ...toastConfig, variant: 'default' });
        break;
      case 'error':
        toast({ ...toastConfig, variant: 'destructive' });
        break;
      case 'warning':
        toast({ ...toastConfig, variant: 'default' });
        break;
      default:
        toast({ ...toastConfig, variant: 'default' });
    }
  }, [toast]);

  const dismissNotification = useCallback((id: string) => {
    setNotifications(prev => prev.filter(n => n.id !== id));
  }, []);

  const clearAllNotifications = useCallback(() => {
    setNotifications([]);
  }, []);

  const watchTask = useCallback((taskId: string) => {
    watchedTasksRef.current.add(taskId);
    socketRef.current?.emit('watch_task', { taskId });
  }, []);

  const unwatchTask = useCallback((taskId: string) => {
    watchedTasksRef.current.delete(taskId);
    socketRef.current?.emit('unwatch_task', { taskId });
  }, []);

  const broadcastTaskUpdate = useCallback((taskId: string, updates: Record<string, unknown>) => {
    if (!currentUser) return;
    
    socketRef.current?.emit('task_update', {
      taskId,
      updates,
      userId: currentUser.id
    });
  }, [currentUser]);

  const value: CollaborationContextValue = {
    isConnected,
    currentUser,
    onlineUsers,
    notifications,
    setCurrentUser,
    updateUserStatus,
    subscribe,
    publish,
    notify,
    dismissNotification,
    clearAllNotifications,
    watchTask,
    unwatchTask,
    broadcastTaskUpdate
  };

  return (
    <CollaborationContext.Provider value={value}>
      {children}
      <NotificationContainer />
      <UserPresenceIndicator />
    </CollaborationContext.Provider>
  );
};

export const useCollaboration = (): CollaborationContextValue => {
  const context = useContext(CollaborationContext);
  if (!context) {
    throw new Error('useCollaboration must be used within a CollaborationProvider');
  }
  return context;
};

const NotificationContainer: React.FC = () => {
  const { notifications, dismissNotification, clearAllNotifications } = useCollaboration();

  if (notifications.length === 0) return null;

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 w-96">
      <div className="flex items-center justify-between p-2 bg-gray-100 rounded-t-lg">
        <span className="text-sm font-medium text-gray-700">
          通知 ({notifications.length})
        </span>
        <div className="flex gap-2">
          <button
            onClick={clearAllNotifications}
            className="text-xs text-gray-500 hover:text-gray-700"
          >
            清除全部
          </button>
        </div>
      </div>
      {notifications.map((notification, index) => (
        <div
          key={notification.id}
          className={`
            p-4 rounded-lg shadow-lg animate-slide-in
            ${notification.type === 'success' ? 'bg-green-50 border-l-4 border-green-500' : ''}
            ${notification.type === 'error' ? 'bg-red-50 border-l-4 border-red-500' : ''}
            ${notification.type === 'warning' ? 'bg-yellow-50 border-l-4 border-yellow-500' : ''}
            ${notification.type === 'info' ? 'bg-blue-50 border-l-4 border-blue-500' : ''}
          `}
          style={{ animationDelay: `${index * 50}ms` }}
        >
          <div className="flex items-start justify-between">
            <div className="flex-1">
              <h4 className="font-medium text-gray-900">{notification.title}</h4>
              <p className="text-sm text-gray-600 mt-1">{notification.message}</p>
              {notification.action && (
                <button
                  onClick={notification.action.onClick}
                  className="mt-2 text-sm font-medium text-blue-600 hover:text-blue-800"
                >
                  {notification.action.label}
                </button>
              )}
            </div>
            <button
              onClick={() => dismissNotification(notification.id)}
              className="ml-2 text-gray-400 hover:text-gray-600"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>
      ))}
    </div>
  );
};

const UserPresenceIndicator: React.FC = () => {
  const { onlineUsers, isConnected } = useCollaboration();

  return (
    <div className="fixed top-4 right-4 z-40 flex items-center gap-3 p-3 bg-white rounded-lg shadow-lg">
      <div className="flex items-center gap-2">
        <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`} />
        <span className="text-sm text-gray-600">
          {isConnected ? '已连接' : '未连接'}
        </span>
      </div>
      
      {onlineUsers.length > 0 && (
        <div className="flex items-center gap-1 pl-3 border-l border-gray-200">
          <span className="text-sm text-gray-600">在线:</span>
          <div className="flex -space-x-2">
            {onlineUsers.slice(0, 5).map((user) => (
              <div
                key={user.id}
                className="w-8 h-8 rounded-full flex items-center justify-center text-white text-xs font-medium border-2 border-white"
                style={{ backgroundColor: user.color }}
                title={`${user.name} (${user.status})`}
              >
                {user.avatar ? (
                  <img src={user.avatar} alt={user.name} className="w-full h-full rounded-full" />
                ) : (
                  user.name.charAt(0).toUpperCase()
                )}
              </div>
            ))}
            {onlineUsers.length > 5 && (
              <div className="w-8 h-8 rounded-full bg-gray-300 flex items-center justify-center text-xs font-medium border-2 border-white">
                +{onlineUsers.length - 5}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export const useTaskCollaboration = (taskId: string) => {
  const { subscribe, watchTask, unwatchTask, broadcastTaskUpdate } = useCollaboration();
  const [taskUpdates, setTaskUpdates] = useState<Record<string, unknown>[]>([]);
  const [collaborators, setCollaborators] = useState<string[]>([]);

  useEffect(() => {
    watchTask(taskId);

    const unsubscribe = subscribe(`task:${taskId}`, (event) => {
      if (event.type === 'task_update' && event.data) {
        setTaskUpdates(prev => [...prev, event.data as Record<string, unknown>]);
      }
    });

    return () => {
      unsubscribe();
      unwatchTask(taskId);
    };
  }, [taskId, subscribe, watchTask, unwatchTask]);

  const sendUpdate = useCallback((updates: Record<string, unknown>) => {
    broadcastTaskUpdate(taskId, updates);
  }, [taskId, broadcastTaskUpdate]);

  return {
    taskUpdates,
    collaborators,
    sendUpdate
  };
};

export const useTypingIndicator = (channelId: string) => {
  const { subscribe, publish, currentUser } = useCollaboration();
  const [typingUsers, setTypingUsers] = useState<string[]>([]);
  const typingTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    const unsubscribe = subscribe(channelId, (event) => {
      if (!currentUser || event.userId === currentUser.id) return;

      if (event.type === 'typing_start') {
        setTypingUsers(prev => 
          prev.includes(event.userId!) ? prev : [...prev, event.userId!]
        );
      } else if (event.type === 'typing_stop') {
        setTypingUsers(prev => prev.filter(id => id !== event.userId));
      }
    });

    return unsubscribe;
  }, [channelId, subscribe, currentUser]);

  const startTyping = useCallback(() => {
    if (!currentUser) return;

    publish(channelId, {
      type: 'typing_start',
      userId: currentUser.id
    });

    if (typingTimeoutRef.current) {
      clearTimeout(typingTimeoutRef.current);
    }

    typingTimeoutRef.current = setTimeout(() => {
      publish(channelId, {
        type: 'typing_stop',
        userId: currentUser.id
      });
    }, 2000);
  }, [channelId, publish, currentUser]);

  const stopTyping = useCallback(() => {
    if (!currentUser) return;

    if (typingTimeoutRef.current) {
      clearTimeout(typingTimeoutRef.current);
    }

    publish(channelId, {
      type: 'typing_stop',
      userId: currentUser.id
    });
  }, [channelId, publish, currentUser]);

  return {
    typingUsers,
    startTyping,
    stopTyping
  };
};

export default CollaborationProvider;
