import { useEffect, useRef } from 'react';
import { useNavigate } from 'react-router';
import { useAuth } from '../../context/AuthContext';

export function OAuthCallback() {
  const navigate = useNavigate();
  const { login } = useAuth();
  const called = useRef(false);

  useEffect(() => {
    if (called.current) return;
    called.current = true;

    const params = new URLSearchParams(window.location.search);
    const accessToken = params.get('accessToken');
    const refreshToken = params.get('refreshToken');
    const error = params.get('error');

    if (accessToken) {
      if (refreshToken) {
        localStorage.setItem('refreshToken', refreshToken);
      }
      login(accessToken)
        .then(() => {
          setTimeout(() => navigate('/dashboard', { replace: true }), 100);
        })
        .catch(() => {
          navigate('/login?error=user_fetch_failed', { replace: true });
        });
    } else if (error) {
      navigate(`/login?error=${encodeURIComponent(error)}`, { replace: true });
    } else {
      navigate('/login', { replace: true });
    }
  }, [login, navigate]);

  return (
    <div
      className="min-h-screen flex items-center justify-center"
      style={{ backgroundColor: '#0a1e14' }}
    >
      <div
        className="rounded-xl p-8 flex flex-col items-center gap-4"
        style={{
          backgroundColor: 'rgba(15,46,31,0.6)',
          border: '1px solid rgba(255,255,255,0.06)',
        }}
      >
        <div className="w-10 h-10 border-[3px] border-[#299283] border-t-transparent rounded-full animate-spin" />
        <p className="text-[14px]" style={{ color: 'rgba(255,255,255,0.6)' }}>
          로그인 처리 중...
        </p>
      </div>
    </div>
  );
}
