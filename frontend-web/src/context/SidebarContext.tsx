import { createContext, useState, type ReactNode } from 'react';

interface SidebarContextType {
  collapsed: boolean;
  toggle: () => void;
}

export const SidebarContext = createContext<SidebarContextType>({
  collapsed: false,
  toggle: () => {},
});

export function SidebarProvider({ children }: { children: ReactNode }) {
  const [collapsed, setCollapsed] = useState(() => {
    return localStorage.getItem('sidebar_collapsed') === 'true';
  });

  const toggle = () => {
    setCollapsed((prev) => {
      localStorage.setItem('sidebar_collapsed', String(!prev));
      return !prev;
    });
  };

  return (
    <SidebarContext.Provider value={{ collapsed, toggle }}>
      {children}
    </SidebarContext.Provider>
  );
}
