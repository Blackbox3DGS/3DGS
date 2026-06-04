import { useState, useEffect, lazy, Suspense } from 'react';
import { useNavigate, useLocation } from 'react-router';
import { useAuth } from '../../context/AuthContext';
import { TrajectoryDiagram } from './TrajectoryDiagram';

const LoginPreview3D = lazy(() => import('./LoginPreview3D'));

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8080';

export function LoginScreen() {
  const navigate = useNavigate();
  const location = useLocation();
  const { loginWithCredentials } = useAuth();

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [loadingProvider, setLoadingProvider] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [preview3dActive, setPreview3dActive] = useState(false);

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const error = params.get('error');
    if (error) {
      setErrorMessage(decodeURIComponent(error));
      navigate('/login', { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username || !password || isSubmitting) return;
    setIsSubmitting(true);
    setErrorMessage(null);
    try {
      await loginWithCredentials(username, password);
      navigate('/dashboard', { replace: true });
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response?.status;
      if (status === 401 || status === 400) {
        setErrorMessage('아이디 또는 비밀번호가 올바르지 않습니다.');
      } else {
        setErrorMessage('로그인 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSignUp = () => {
    navigate('/signup');
  };

  const redirectToOAuth = (provider: 'google' | 'kakao' | 'naver') => {
    setLoadingProvider(provider);
    setErrorMessage(null);
    setTimeout(() => {
      window.location.href = `${API_BASE_URL}/oauth2/authorization/${provider}`;
    }, 100);
  };

  const goLanding = () => navigate('/');

  return (
    <>
    <style>{`
      @keyframes fadeIn3d {
        from { opacity: 0; }
        to   { opacity: 1; }
      }
    `}</style>
    <div
      className="min-h-screen text-white flex flex-col relative overflow-hidden"
      style={{
        backgroundColor: '#0a1e14',
        fontFamily: '"Plus Jakarta Sans", "Pretendard", system-ui, sans-serif',
      }}
    >

      {/* Shared background grid */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0"
        style={{
          backgroundImage:
            'linear-gradient(rgba(92,191,174,0.035) 1px, transparent 1px), linear-gradient(90deg, rgba(92,191,174,0.035) 1px, transparent 1px)',
          backgroundSize: '48px 48px',
          maskImage: 'radial-gradient(ellipse 80% 70% at 40% 50%, black 30%, transparent 80%)',
          WebkitBackdropFilter: 'radial-gradient(ellipse 80% 70% at 40% 50%, black 30%, transparent 80%)',
          WebkitMaskImage: 'radial-gradient(ellipse 80% 70% at 40% 50%, black 30%, transparent 80%)',
        }}
      />

      {/* Top bar */}
      <header className="relative flex items-center justify-between px-8 pt-5 pb-3">
        <button
          onClick={goLanding}
          className="flex items-center gap-2 transition-opacity hover:opacity-80"
        >
          <img
            src="/rs-mark.png"
            alt="ReScene"
            className="h-5 w-5"
            style={{ filter: 'brightness(0) invert(1)' }}
          />
          <span className="text-[13px] font-semibold tracking-tight">ReScene</span>
          <span className="text-[10px] font-mono ml-2" style={{ color: 'rgba(255,255,255,0.35)' }}>
            v0.1.0
          </span>
        </button>
        <span className="text-[10px] font-mono" style={{ color: 'rgba(255,255,255,0.35)' }}>
          블랙박스 기반 사고 분석 시스템
        </span>
      </header>

      <div className="relative flex-1 grid lg:grid-cols-[1.25fr_1fr] gap-0 min-h-0">

        {/* ─── Left: Reconstruction preview ─── */}
        <div className="hidden lg:flex flex-col pl-8 pr-6 pb-6 pt-2 min-h-0">

          {/* Case header */}
          <div className="flex items-center justify-between mb-2.5">
            <div className="flex items-center gap-3">
              <span className="text-[13px] font-mono tracking-tight" style={{ color: 'rgba(255,255,255,0.85)' }}>
                RC-2026-0041
              </span>
              <span
                className="text-[9px] font-mono px-1.5 py-0.5 rounded"
                style={{ color: '#5cbfae', backgroundColor: 'rgba(41,146,131,0.12)' }}
              >
                복원 완료
              </span>
              <span className="text-[10px] font-mono" style={{ color: 'rgba(255,255,255,0.35)' }}>
                2026-05-15
              </span>
            </div>
            <div
              className="flex items-center gap-4 text-[10px] font-mono"
              style={{ color: 'rgba(255,255,255,0.45)' }}
            >
              <span>차량 2대</span>
              <span>847 프레임</span>
              <span>4.2초</span>
              <span>자동</span>
            </div>
          </div>

          {/* Reconstruction viewer */}
          <div
            className="relative rounded-lg overflow-hidden cursor-pointer flex-1 min-h-0"
            style={{
              backgroundColor: 'rgba(15,46,31,0.6)',
              border: '1px solid rgba(255,255,255,0.06)',
            }}
            onMouseEnter={() => setPreview3dActive(true)}
            onMouseLeave={() => setPreview3dActive(false)}
          >
            {/* Toolbar */}
            <div
              className="flex items-center justify-between px-3.5 py-2"
              style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}
            >
              <div className="flex items-center gap-1">
                <span
                  className="text-[10px] font-mono px-2 py-0.5 rounded"
                  style={{
                    color: '#5cbfae',
                    backgroundColor: 'rgba(41,146,131,0.1)',
                  }}
                >
                  궤적 2D
                </span>
                <span className="text-[10px] font-mono px-2 py-0.5" style={{ color: 'rgba(255,255,255,0.3)' }}>
                  3D 뷰
                </span>
              </div>
              <span className="text-[9px] font-mono" style={{ color: 'rgba(255,255,255,0.35)' }}>847 / 847</span>
            </div>

            {/* SVG diagram */}
            <div
              className="absolute left-0 right-0 bottom-0"
              style={{
                top: '30px',
                opacity: preview3dActive ? 0 : 1,
                transition: 'opacity 0.4s ease',
              }}
            >
              <TrajectoryDiagram compact />
            </div>

            {/* Frame progress */}
            <div
              className="absolute bottom-0 left-0 right-0 z-10"
              style={{
                opacity: preview3dActive ? 0 : 1,
                transition: 'opacity 0.4s ease',
              }}
            >
              <div className="h-[2px]" style={{ backgroundColor: 'rgba(255,255,255,0.03)' }}>
                <div className="h-full" style={{ width: '100%', backgroundColor: 'rgba(41,146,131,0.4)' }} />
              </div>
            </div>

            {/* 3D preview overlay */}
            {preview3dActive && (
              <div
                className="absolute inset-0"
                style={{ animation: 'fadeIn3d 0.4s ease' }}
              >
                <Suspense
                  fallback={
                    <div
                      className="flex items-center justify-center h-full text-[11px]"
                      style={{ color: 'rgba(255,255,255,0.4)' }}
                    >
                      로딩 중...
                    </div>
                  }
                >
                  <LoginPreview3D />
                </Suspense>
              </div>
            )}
          </div>

          {/* Summary + legend */}
          <div className="mt-2.5 flex items-start gap-4">
            <div
              className="flex-1 rounded-md px-3.5 py-2"
              style={{
                backgroundColor: 'rgba(15,46,31,0.4)',
                border: '1px solid rgba(255,255,255,0.05)',
              }}
            >
              <div className="grid grid-cols-4 gap-x-3 gap-y-1.5">
                {[
                  ['충돌 각도', '47.2°'],
                  ['충돌 시각', '14:23:07'],
                  ['분석 거리', '48.3m'],
                  ['동기화', '완료'],
                  ['차량 A', '62.4 km/h'],
                  ['차량 B', '44.8 km/h'],
                  ['포인트 클라우드', '1.2M'],
                  ['정확도', '94.7%'],
                ].map(([k, v]) => (
                  <div key={k}>
                    <div className="text-[9px] mb-0.5" style={{ color: 'rgba(255,255,255,0.4)' }}>{k}</div>
                    <div className="text-[11px] font-mono" style={{ color: 'rgba(255,255,255,0.75)' }}>{v}</div>
                  </div>
                ))}
              </div>
            </div>

            <div className="flex flex-col gap-1.5 pt-1 shrink-0">
              <div className="flex items-center gap-1.5 text-[10px]">
                <div className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: 'rgba(92,191,174,0.6)' }} />
                <span style={{ color: 'rgba(255,255,255,0.45)' }}>차량 A</span>
              </div>
              <div className="flex items-center gap-1.5 text-[10px]">
                <div className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: 'rgba(77,138,107,0.6)' }} />
                <span style={{ color: 'rgba(255,255,255,0.45)' }}>차량 B</span>
              </div>
              <div className="flex items-center gap-1.5 text-[10px]">
                <div className="w-1 h-1 rounded-full" style={{ backgroundColor: 'rgba(41,146,131,0.65)' }} />
                <span style={{ color: 'rgba(255,255,255,0.45)' }}>충돌</span>
              </div>
            </div>
          </div>

        </div>

        {/* ─── Right: Login form ─── */}
        <div className="flex items-center justify-center px-8 lg:pl-6 lg:pr-12">
          <div className="w-full max-w-[340px]">

            {/* Mobile brand */}
            <button
              onClick={goLanding}
              className="lg:hidden flex items-center gap-2 mb-10 transition-opacity hover:opacity-80"
            >
              <img
                src="/rs-mark.png"
                alt="ReScene"
                className="h-5 w-5"
                style={{ filter: 'brightness(0) invert(1)' }}
              />
              <span className="text-[13px] font-semibold tracking-tight text-white">ReScene</span>
            </button>

            {/* System context */}
            <div className="flex items-center gap-2 mb-5">
              <div className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: 'rgba(92,191,174,0.7)' }} />
              <span className="text-[10px] font-mono" style={{ color: 'rgba(255,255,255,0.45)' }}>
                시스템 정상 운영 중
              </span>
            </div>

            {/* Title */}
            <div className="mb-6">
              <h1 className="text-[20px] font-medium tracking-tight text-white">
                로그인
              </h1>
              <p className="mt-1 text-[13px]" style={{ color: 'rgba(255,255,255,0.55)' }}>
                계정에 로그인하여 분석을 시작하세요.
              </p>
            </div>

            {/* Error */}
            {errorMessage && (
              <div
                className="mb-5 px-3.5 py-2.5 rounded-md text-[13px]"
                style={{
                  backgroundColor: 'rgba(196,64,64,0.08)',
                  border: '1px solid rgba(196,64,64,0.2)',
                  color: 'rgba(255,180,180,0.95)',
                }}
              >
                {errorMessage}
              </div>
            )}

            {/* Form */}
            <form onSubmit={handleLogin} className="space-y-3.5">
              <div>
                <label htmlFor="username" className="block text-[12px] mb-1.5" style={{ color: 'rgba(255,255,255,0.55)' }}>
                  아이디
                </label>
                <input
                  id="username"
                  type="text"
                  placeholder="사용자 이름 입력"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-lg text-[14px] text-white transition-colors focus:outline-none"
                  style={{
                    backgroundColor: 'rgba(21,61,43,0.5)',
                    border: '1px solid rgba(255,255,255,0.08)',
                  }}
                  onFocus={(e) => {
                    e.currentTarget.style.borderColor = '#299283';
                    e.currentTarget.style.boxShadow = '0 0 0 3px rgba(41,146,131,0.15)';
                  }}
                  onBlur={(e) => {
                    e.currentTarget.style.borderColor = 'rgba(255,255,255,0.08)';
                    e.currentTarget.style.boxShadow = 'none';
                  }}
                />
              </div>
              <div>
                <label htmlFor="password" className="block text-[12px] mb-1.5" style={{ color: 'rgba(255,255,255,0.55)' }}>
                  비밀번호
                </label>
                <input
                  id="password"
                  type="password"
                  placeholder="비밀번호 입력"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-lg text-[14px] text-white transition-colors focus:outline-none"
                  style={{
                    backgroundColor: 'rgba(21,61,43,0.5)',
                    border: '1px solid rgba(255,255,255,0.08)',
                  }}
                  onFocus={(e) => {
                    e.currentTarget.style.borderColor = '#299283';
                    e.currentTarget.style.boxShadow = '0 0 0 3px rgba(41,146,131,0.15)';
                  }}
                  onBlur={(e) => {
                    e.currentTarget.style.borderColor = 'rgba(255,255,255,0.08)';
                    e.currentTarget.style.boxShadow = 'none';
                  }}
                />
              </div>

              <div className="pt-1">
                <button
                  type="submit"
                  disabled={isSubmitting || !!loadingProvider}
                  className="w-full py-2.5 rounded-lg text-white text-[14px] font-medium transition-all hover:scale-[1.01] disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100 flex items-center justify-center gap-2"
                  style={{ backgroundColor: '#299283' }}
                  onMouseEnter={(e) => { if (!isSubmitting && !loadingProvider) e.currentTarget.style.backgroundColor = '#1a5f54'; }}
                  onMouseLeave={(e) => { if (!isSubmitting && !loadingProvider) e.currentTarget.style.backgroundColor = '#299283'; }}
                >
                  {isSubmitting ? (
                    <>
                      <div className="w-4 h-4 border-2 border-white/50 border-t-white rounded-full animate-spin" />
                      로그인 중...
                    </>
                  ) : '로그인'}
                </button>
              </div>

              <button
                type="button"
                onClick={handleSignUp}
                disabled={isSubmitting || !!loadingProvider}
                className="w-full py-2.5 rounded-lg bg-transparent text-[13px] transition-colors disabled:opacity-50"
                style={{
                  border: '1px solid rgba(255,255,255,0.1)',
                  color: 'rgba(255,255,255,0.7)',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.backgroundColor = 'rgba(255,255,255,0.04)';
                  e.currentTarget.style.borderColor = 'rgba(255,255,255,0.15)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = 'transparent';
                  e.currentTarget.style.borderColor = 'rgba(255,255,255,0.1)';
                }}
              >
                회원가입
              </button>
            </form>

            {/* Divider */}
            <div className="relative my-7">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full" style={{ borderTop: '1px solid rgba(255,255,255,0.06)' }} />
              </div>
              <div className="relative flex justify-center">
                <span
                  className="px-3 text-[11px]"
                  style={{ color: 'rgba(255,255,255,0.4)', backgroundColor: '#0a1e14' }}
                >
                  소셜 계정으로 계속
                </span>
              </div>
            </div>

            {/* Social login */}
            <div className="space-y-2">
              <button
                type="button"
                onClick={() => redirectToOAuth('google')}
                disabled={!!loadingProvider}
                className="w-full flex items-center justify-center gap-2.5 px-4 py-2.5 bg-white hover:bg-gray-50 text-gray-700 rounded-lg text-[13px] font-medium transition-colors disabled:opacity-50"
              >
                {loadingProvider === 'google' ? (
                  <div className="w-4 h-4 border-2 border-gray-300 border-t-transparent rounded-full animate-spin" />
                ) : (
                  <svg className="w-4 h-4" viewBox="0 0 24 24">
                    <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
                    <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                    <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
                    <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
                  </svg>
                )}
                <span>{loadingProvider === 'google' ? '연결 중...' : 'Google'}</span>
              </button>

              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => redirectToOAuth('kakao')}
                  disabled={!!loadingProvider}
                  className="flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg text-[13px] font-medium transition-colors disabled:opacity-50"
                  style={{ backgroundColor: '#FEE500' }}
                >
                  {loadingProvider === 'kakao' ? (
                    <div className="w-4 h-4 border-2 border-yellow-800/50 border-t-transparent rounded-full animate-spin" />
                  ) : (
                    <svg className="w-4 h-4" viewBox="0 0 24 24" fill="#3C1E1E">
                      <path d="M12 3C6.477 3 2 6.477 2 10.8c0 2.713 1.617 5.1 4.073 6.558-.18.67-.651 2.424-.746 2.8-.116.458.168.453.353.33.146-.097 2.313-1.563 3.252-2.198.34.047.687.072 1.068.072 5.523 0 10-3.477 10-7.8C22 6.477 17.523 3 12 3z" />
                    </svg>
                  )}
                  <span style={{ color: '#3C1E1E' }}>
                    {loadingProvider === 'kakao' ? '...' : 'Kakao'}
                  </span>
                </button>

                <button
                  type="button"
                  onClick={() => redirectToOAuth('naver')}
                  disabled={!!loadingProvider}
                  className="flex items-center justify-center gap-2 px-4 py-2.5 text-white rounded-lg text-[13px] font-medium transition-colors disabled:opacity-50"
                  style={{ backgroundColor: '#03C75A' }}
                >
                  {loadingProvider === 'naver' ? (
                    <div className="w-4 h-4 border-2 border-white/50 border-t-transparent rounded-full animate-spin" />
                  ) : (
                    <svg className="w-4 h-4" viewBox="0 0 24 24" fill="white">
                      <path d="M16.273 12.845 7.376 0H0v24h7.726V11.156L16.624 24H24V0h-7.727v12.845z" />
                    </svg>
                  )}
                  <span>{loadingProvider === 'naver' ? '...' : 'Naver'}</span>
                </button>
              </div>
            </div>

            {/* Access context */}
            <div
              className="mt-7 flex items-center justify-between text-[10px]"
              style={{ color: 'rgba(255,255,255,0.35)' }}
            >
              <span className="font-mono">최근 복원: 3건 대기 중</span>
              <span className="font-mono">보안 접속</span>
            </div>

          </div>
        </div>

      </div>
    </div>
    </>
  );
}
