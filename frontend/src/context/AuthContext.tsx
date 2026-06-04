import { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import apiClient from '../lib/apiClient';

export interface User {
  userId: string;
  name: string;
  email: string;
  birth?: string;
  profileImageUrl?: string;
  socialProvider?: string;
}

interface LoginResponse {
  accessToken: string;
  refreshToken: string;
  name: string;
}

interface AuthContextType {
  user: User | null;
  isLoading: boolean;
  login: (token: string) => Promise<void>;
  loginWithCredentials: (userId: string, password: string) => Promise<void>;
  loginDemo: () => void;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (window.location.pathname === '/oauth/callback') {
      setIsLoading(false);
      return;
    }
    const token = localStorage.getItem('accessToken');
    if (!token) {
      setIsLoading(false);
      return;
    }
    if (token === 'demo-token') {
      setUser({ userId: 'demo', name: '데모 사용자', email: 'demo@example.com' });
      setIsLoading(false);
      return;
    }
    apiClient
      .get<User>('/api/auth/profile')
      .then((res) => setUser(res.data))
      .catch(() => {
        localStorage.removeItem('accessToken');
        localStorage.removeItem('refreshToken');
      })
      .finally(() => setIsLoading(false));
  }, []);

  // OAuth 소셜 로그인: 토큰을 받아 프로필 조회
  const login = async (token: string) => {
    localStorage.setItem('accessToken', token);
    const res = await apiClient.get<User>('/api/auth/profile');
    setUser(res.data);
  };

  // 아이디/비밀번호 로그인: 백엔드 /api/auth/login 호출
  const loginWithCredentials = async (userId: string, password: string) => {
    const res = await apiClient.post<LoginResponse>('/api/auth/login', { userId, password });
    const { accessToken, refreshToken } = res.data;
    localStorage.setItem('accessToken', accessToken);
    if (refreshToken) localStorage.setItem('refreshToken', refreshToken);
    const profileRes = await apiClient.get<User>('/api/auth/profile');
    setUser(profileRes.data);
  };

  const loginDemo = () => {
    localStorage.setItem('accessToken', 'demo-token');
    setUser({ userId: 'demo', name: '데모 사용자', email: 'demo@example.com' });
  };

  const logout = async () => {
    try {
      await apiClient.delete('/api/auth/logout');
    } catch {
      // 로그아웃 API 실패해도 로컬은 무조건 초기화
    } finally {
      localStorage.removeItem('accessToken');
      localStorage.removeItem('refreshToken');
      setUser(null);
    }
  };

  return (
    <AuthContext.Provider value={{ user, isLoading, login, loginWithCredentials, loginDemo, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth는 AuthProvider 안에서만 사용할 수 있습니다.');
  }
  return ctx;
}
