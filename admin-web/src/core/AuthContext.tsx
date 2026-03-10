import React, { createContext, useContext, useState, useEffect } from 'react';
import { apiClient } from './apiClient';

interface User {
  id: string;
  email: string;
}

interface Tenant {
  id: string;
  name: string;
}

interface AuthContextType {
  isAuthenticated: boolean;
  isLoading: boolean;
  user: User | null;
  tenant: Tenant | null;
  login: (token: string, refreshToken: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [user, setUser] = useState<User | null>(null);
  const [tenant, setTenant] = useState<Tenant | null>(null);

  const fetchProfile = async () => {
    try {
      const response = await apiClient.get('/v1/me');
      setUser(response.data.data.user);
      setTenant(response.data.data.tenant);
      setIsAuthenticated(true);
    } catch (error) {
      console.error('Failed to fetch profile', error);
      setIsAuthenticated(false);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (token) {
      fetchProfile();
    } else {
      setIsLoading(false);
    }
  }, []);

  const login = async (token: string, refreshToken: string) => {
    localStorage.setItem('access_token', token);
    localStorage.setItem('refresh_token', refreshToken);
    setIsLoading(true);
    await fetchProfile();
  };

  const logout = () => {
    try {
      apiClient.post('/v1/auth/logout');
    } catch (e) {
      // Ignore network errors on logout
    }
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    setIsAuthenticated(false);
    setUser(null);
    setTenant(null);
  };

  return (
    <AuthContext.Provider value={{ isAuthenticated, isLoading, user, tenant, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
