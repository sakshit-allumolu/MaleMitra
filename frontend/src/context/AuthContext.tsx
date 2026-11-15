import React, { createContext, useContext, useState, useEffect } from 'react';
import { UserProfile, UserRole, RegisterFormData } from '../types';
import { ApiClient } from '../services/api';

interface AuthContextType {
  currentUser: UserProfile | null;
  isAuthenticated: boolean;
  activeRole: UserRole | null;
  login: (email: string, pass: string) => Promise<void>;
  register: (data: RegisterFormData) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [currentUser, setCurrentUser] = useState<UserProfile | null>(() => {
    const saved = localStorage.getItem('malemitra_user');
    if (saved) {
      try {
        return JSON.parse(saved);
      } catch {
        return null;
      }
    }
    return null;
  });

  const isAuthenticated = currentUser !== null;
  const activeRole: UserRole | null = currentUser?.role ?? null;

  // Restore token on mount from persisted session
  useEffect(() => {
    if (currentUser) {
      ApiClient.setAuthToken(localStorage.getItem('malemitra_token') || '');
    }
  }, []);

  // A rejected token (expired / revoked) ends the local session without another round trip.
  useEffect(() => {
    ApiClient.setUnauthorizedHandler(() => {
      setCurrentUser(null);
      ApiClient.setAuthToken('');
      localStorage.removeItem('malemitra_user');
      localStorage.removeItem('malemitra_token');
    });
    return () => ApiClient.setUnauthorizedHandler(null);
  }, []);

  const login = async (email: string, pass: string) => {
    const res = await ApiClient.loginUser(email, pass);
    const userProfile: UserProfile = {
      id: res.user_id,
      name: res.name,
      email: email,
      role: res.role as UserRole,
      team_id: res.team_id ?? null,
    };
    ApiClient.setAuthToken(res.access_token);
    localStorage.setItem('malemitra_token', res.access_token);
    setCurrentUser(userProfile);
    localStorage.setItem('malemitra_user', JSON.stringify(userProfile));
  };

  const register = async (data: RegisterFormData) => {
    const res = await ApiClient.registerUser(data);
    const userProfile: UserProfile = {
      id: res.user_id,
      name: res.name,
      email: data.email,
      role: res.role as UserRole,
      team_id: res.team_id ?? null,
    };
    ApiClient.setAuthToken(res.access_token);
    localStorage.setItem('malemitra_token', res.access_token);
    setCurrentUser(userProfile);
    localStorage.setItem('malemitra_user', JSON.stringify(userProfile));
  };

  const logout = () => {
    void ApiClient.logoutRemote();  // revoke server-side (fire and forget) before the token is dropped
    setCurrentUser(null);
    ApiClient.setAuthToken('');
    localStorage.removeItem('malemitra_user');
    localStorage.removeItem('malemitra_token');
  };

  return (
    <AuthContext.Provider value={{
      currentUser,
      isAuthenticated,
      activeRole,
      login,
      register,
      logout,
    }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within an AuthProvider');
  return context;
};
