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
        setTimeout(() => {
          navigate('/dashboard', { replace: true });
        }, 100);
      })
      .catch(() => {
        navigate('/login?error=user_fetch_failed', { replace: true });
      });

  } else if (error) {
    navigate(`/login?error=${encodeURIComponent(error)}`, { replace: true });

  } else {
    navigate('/login', { replace: true });
  }
    // if (accessToken) {
    //   if (refreshToken) {
    //     localStorage.setItem('refreshToken', refreshToken);
    //   }

    //   login(accessToken)
    //     .then(() => navigate('/dashboard', { replace: true }))
    //     .catch(() => {
    //       navigate('/login?error=user_fetch_failed', { replace: true });
    //     });
    // } else if (error) {
    //   navigate(`/login?error=${encodeURIComponent(error)}`, { replace: true });
    // } else {
    //   navigate('/login', { replace: true });
    // }
    // login(accessToken)
    //   .then(() => {
    //     // 🔥 약간 딜레이 줘서 상태 반영 보장
    //     setTimeout(() => {
    //       navigate('/dashboard', { replace: true });
    //     }, 100);
    //   })
    //   .catch(() => {
    //     navigate('/login?error=user_fetch_failed', { replace: true });
    //   });
    // }
  }, [login, navigate]);

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center">
      <div className="bg-white rounded-lg shadow-xl p-8 flex flex-col items-center gap-4">
        <div className="w-10 h-10 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin" />
        <p className="text-gray-600">로그인 처리 중...</p>
      </div>
    </div>
  );
}