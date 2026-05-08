import { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import apiClient from '../lib/apiClient';

// 백엔드 ProfileResponse 필드명에 맞춤
export interface User {
  userId: string;
  name: string;
  email: string;
  birth?: string;
  profileImageUrl?: string;
  socialProvider?: string;
}

interface AuthContextType {
  user: User | null;
  isLoading: boolean;
  login: (token: string) => Promise<void>;
  loginDemo: () => void;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // 앱 시작 시: 저장된 토큰으로 유저 정보 복원
  useEffect(() => {
    // OAuth 콜백 중이면 실행 막기
    if (window.location.pathname === '/oauth/callback') {
      setIsLoading(false);
      return;
    }
    const token = localStorage.getItem('accessToken');
    if (!token) {
      setIsLoading(false);
      return;
    }
    // 데모 토큰이면 백엔드 호출 없이 처리
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

  // OAuth 콜백에서 토큰 받았을 때 호출
  const login = async (token: string) => {
    localStorage.setItem('accessToken', token);
    const res = await apiClient.get<User>('/api/auth/profile');
    setUser(res.data);
  };

  // 데모 로그인 (아이디/비밀번호 폼)
  const loginDemo = () => {
    localStorage.setItem('accessToken', 'demo-token');
    setUser({ userId: 'demo', name: '데모 사용자', email: 'demo@example.com' });
  };

  // 로그아웃: 백엔드 토큰 무효화 + 로컬 상태 초기화
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
    <AuthContext.Provider value={{ user, isLoading, login, loginDemo, logout }}>
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
