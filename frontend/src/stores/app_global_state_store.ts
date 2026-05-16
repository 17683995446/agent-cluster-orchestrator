import { create } from 'zustand';

interface AppState {
  sidebarOpen: boolean;
  toggleSidebar: () => void;
  
  selectedAgentId: string | null;
  setSelectedAgent: (id: string | null) => void;
  
  taskFilters: {
    status: string | null;
    search: string;
  };
  setTaskFilters: (filters: Partial<AppState['taskFilters']>) => void;
  
  notifications: Notification[];
  addNotification: (notification: Omit<Notification, 'id'>) => void;
  removeNotification: (id: string) => void;
}

interface Notification {
  id: string;
  type: 'success' | 'error' | 'info' | 'warning';
  title: string;
  message?: string;
  duration?: number;
}

export const useAppStore = create<AppState>((set) => ({
  sidebarOpen: true,
  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
  
  selectedAgentId: null,
  setSelectedAgent: (id) => set({ selectedAgentId: id }),
  
  taskFilters: {
    status: null,
    search: '',
  },
  setTaskFilters: (filters) => 
    set((state) => ({ taskFilters: { ...state.taskFilters, ...filters } })),
  
  notifications: [],
  addNotification: (notification) =>
    set((state) => ({
      notifications: [
        ...state.notifications,
        { ...notification, id: crypto.randomUUID() },
      ],
    })),
  removeNotification: (id) =>
    set((state) => ({
      notifications: state.notifications.filter((n) => n.id !== id),
    })),
}));
