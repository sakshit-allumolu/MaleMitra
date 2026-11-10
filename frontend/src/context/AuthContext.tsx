import React, { createContext, useContext, useState, useEffect } from 'react';
import { UserProfile, UserRole, RegisterFormData } from '../types';
import { ApiClient } from '../services/api';

export const DEMO_ACCOUNTS: UserProfile[] = [
  {
    id: 'usr-citizen-1',
    name: 'Citizen Commuter (Pooja)',
    email: 'citizen@malemitra.in',
    role: 'citizen'
  },
  {
    id: 'usr-admin-1',
    name: 'BBMP Monsoon Control Room Admin',
    email: 'admin@malemitra.in',
    role: 'admin'
  },
  {
    id: 'usr-resp-1',
    name: 'Inspector Ramesh (Stormwater Unit)',
    email: 'responder1@malemitra.in',
    role: 'responder',
    team_id: 'team-alpha'
  },
  {
    id: 'usr-resp-2',
    name: 'Officer Kavitha (Traffic & Pump Unit)',
    email: 'responder2@malemitra.in',
    role: 'responder',
    team_id: 'team-beta'
  }
];

interface AuthContextType {
  currentUser: UserProfile;
  switchUser: (userId: string) => void;
  activeRole: UserRole;
  setActiveRole: (role: UserRole) => void;
  login: (email: string, pass: string) => Promise<void>;
  register: (data: RegisterFormData) => Promise<void>;
  logout: () => void;
  authModalOpen: boolean;
  authModalTab: 'login' | 'register';
  openAuthModal: (tab?: 'login' | 'register') => void;
  closeAuthModal: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [currentUser, setCurrentUser] = useState<UserProfile>(() => {
    const saved = localStorage.getItem('malemitra_user');
    if (saved) {
      try {
        return JSON.parse(saved);
      } catch {
        return DEMO_ACCOUNTS[0];
      }
    }
    return DEMO_ACCOUNTS[0];
  });

  const [activeRole, setActiveRole] = useState<UserRole>(currentUser.role);
  const [authModalOpen, setAuthModalOpen] = useState<boolean>(false);
  const [authModalTab, setAuthModalTab] = useState<'login' | 'register'>('login');

  useEffect(() => {
    ApiClient.setAuthToken(currentUser.id);
    localStorage.setItem('malemitra_user', JSON.stringify(currentUser));
  }, [currentUser]);

  const switchUser = (userId: string) => {
    const found = DEMO_ACCOUNTS.find(u => u.id === userId);
    if (found) {
      setCurrentUser(found);
      setActiveRole(found.role);
      ApiClient.setAuthToken(found.id);
    }
  };

  const login = async (email: string, pass: string) => {
    const res = await ApiClient.loginUser(email, pass);
    const userProfile: UserProfile = {
      id: res.user_id,
      name: res.name,
      email: email,
      role: res.role as UserRole,
      team_id: res.team_id
    };
    setCurrentUser(userProfile);
    setActiveRole(userProfile.role);
    ApiClient.setAuthToken(res.access_token);
    setAuthModalOpen(false);
  };

  const register = async (data: RegisterFormData) => {
    const res = await ApiClient.registerUser(data);
    const userProfile: UserProfile = {
      id: res.user_id,
      name: res.name,
      email: data.email,
      role: res.role as UserRole,
      team_id: res.team_id
    };
    setCurrentUser(userProfile);
    setActiveRole(userProfile.role);
    ApiClient.setAuthToken(res.access_token);
    setAuthModalOpen(false);
  };

  const logout = () => {
    // Default back to Pooja demo or prompt login
    setCurrentUser(DEMO_ACCOUNTS[0]);
    setActiveRole('citizen');
    ApiClient.setAuthToken(DEMO_ACCOUNTS[0].id);
    localStorage.removeItem('malemitra_user');
  };

  const openAuthModal = (tab: 'login' | 'register' = 'login') => {
    setAuthModalTab(tab);
    setAuthModalOpen(true);
  };

  const closeAuthModal = () => {
    setAuthModalOpen(false);
  };

  return (
    <AuthContext.Provider value={{ 
      currentUser, 
      switchUser, 
      activeRole, 
      setActiveRole,
      login,
      register,
      logout,
      authModalOpen,
      authModalTab,
      openAuthModal,
      closeAuthModal
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
