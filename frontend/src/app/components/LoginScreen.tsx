import { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router';
import { useAuth } from '../../context/AuthContext';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8080';

export function LoginScreen() {
  const navigate = useNavigate();
  const location = useLocation();
  const { loginDemo } = useAuth();

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loadingProvider, setLoadingProvider] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // /login?error=... 파라미터 처리 (OAuthCallback에서 넘어온 에러)
  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const error = params.get('error');
    if (error) {
      setErrorMessage(decodeURIComponent(error));
      navigate('/login', { replace: true });
    }
  }, []);

  const handleLogin = (e: React.FormEvent) => {
    e.preventDefault();
    if (!username || !password) return;
    loginDemo();
    navigate('/dashboard', { replace: true });
  };

  const redirectToOAuth = (provider: 'google' | 'kakao' | 'naver') => {
    setLoadingProvider(provider);
    setErrorMessage(null);
    setTimeout(() => {
      window.location.href = `${API_BASE_URL}/oauth2/authorization/${provider}`;
    }, 100);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4">
      <div className="bg-white rounded-lg shadow-xl p-8 w-full max-w-md">
        <div className="text-center mb-8">
          <div className="inline-block p-3 bg-indigo-600 rounded-lg mb-4">
            <svg className="w-12 h-12 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z" />
            </svg>
          </div>
          <h1 className="text-gray-900 mb-2">3D 사고 복원 시스템</h1>
          <p className="text-muted-foreground">블랙박스 영상 분석 플랫폼</p>
        </div>

        {/* 에러 메시지 */}
        {errorMessage && (
          <div className="mb-4 px-4 py-3 bg-red-50 border border-red-200 rounded-md text-sm text-red-700">
            소셜 로그인에 실패했습니다: {errorMessage}
          </div>
        )}

        <form onSubmit={handleLogin} className="space-y-4">
          <div>
            <label htmlFor="username" className="block text-sm mb-2 text-gray-700">
              아이디
            </label>
            <input
              id="username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500"
              placeholder="아이디를 입력하세요"
            />
          </div>

          <div>
            <label htmlFor="password" className="block text-sm mb-2 text-gray-700">
              비밀번호
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500"
              placeholder="비밀번호를 입력하세요"
            />
          </div>

          <button
            type="submit"
            disabled={!!loadingProvider}
            className="w-full bg-indigo-600 text-white py-2 rounded-md hover:bg-indigo-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            로그인 (데모)
          </button>
        </form>

        <div className="relative my-6">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t border-gray-300"></div>
          </div>
          <div className="relative flex justify-center text-sm">
            <span className="px-2 bg-white text-gray-500">또는 소셜 로그인</span>
          </div>
        </div>

        <div className="space-y-3">
          {/* Google */}
          <button
            type="button"
            onClick={() => redirectToOAuth('google')}
            disabled={!!loadingProvider}
            className="w-full flex items-center justify-center gap-3 px-4 py-2.5 bg-white border border-gray-300 rounded-md hover:bg-gray-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loadingProvider === 'google' ? (
              <div className="w-5 h-5 border-2 border-gray-400 border-t-transparent rounded-full animate-spin" />
            ) : (
              <svg className="w-5 h-5" viewBox="0 0 24 24">
                <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
                <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
                <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
              </svg>
            )}
            <span className="text-gray-700">
              {loadingProvider === 'google' ? '연결 중...' : 'Google로 계속하기'}
            </span>
          </button>

          {/* 카카오 */}
          <button
            type="button"
            onClick={() => redirectToOAuth('kakao')}
            disabled={!!loadingProvider}
            className="w-full flex items-center justify-center gap-3 px-4 py-2.5 rounded-md transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            style={{ backgroundColor: loadingProvider ? '#e8d200' : '#FEE500' }}
          >
            {loadingProvider === 'kakao' ? (
              <div className="w-5 h-5 border-2 border-yellow-800 border-t-transparent rounded-full animate-spin" />
            ) : (
              <svg className="w-5 h-5" viewBox="0 0 24 24" fill="#3C1E1E">
                <path d="M12 3C6.477 3 2 6.477 2 10.8c0 2.713 1.617 5.1 4.073 6.558-.18.67-.651 2.424-.746 2.8-.116.458.168.453.353.33.146-.097 2.313-1.563 3.252-2.198.34.047.687.072 1.068.072 5.523 0 10-3.477 10-7.8C22 6.477 17.523 3 12 3z" />
              </svg>
            )}
            <span style={{ color: '#3C1E1E' }}>
              {loadingProvider === 'kakao' ? '연결 중...' : '카카오로 계속하기'}
            </span>
          </button>

          {/* 네이버 */}
          <button
            type="button"
            onClick={() => redirectToOAuth('naver')}
            disabled={!!loadingProvider}
            className="w-full flex items-center justify-center gap-3 px-4 py-2.5 text-white rounded-md transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            style={{ backgroundColor: loadingProvider ? '#02a84b' : '#03C75A' }}
          >
            {loadingProvider === 'naver' ? (
              <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
            ) : (
              <svg className="w-5 h-5" viewBox="0 0 24 24" fill="white">
                <path d="M16.273 12.845 7.376 0H0v24h7.726V11.156L16.624 24H24V0h-7.727v12.845z" />
              </svg>
            )}
            <span>
              {loadingProvider === 'naver' ? '연결 중...' : '네이버로 계속하기'}
            </span>
          </button>
        </div>

        <div className="mt-6 text-center text-sm text-gray-500">
          <p>데모 버전: 아무 아이디/비밀번호로 로그인 가능</p>
        </div>
      </div>
    </div>
  );
}
