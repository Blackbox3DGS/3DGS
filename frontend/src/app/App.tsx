import { ReactNode } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router';
import { AuthProvider, useAuth } from '../context/AuthContext';
import { LoginScreen } from './components/LoginScreen';
import { SignupScreen } from './components/SignupScreen';
import { LandingPage } from './components/LandingPage';
import { Dashboard } from './components/Dashboard';
import { OAuthCallback } from './pages/OAuthCallback';
import { Viewer3D } from './components/Viewer3D';

// 로그인한 사용자만 접근 가능한 라우트
function PrivateRoute({ children }: { children: ReactNode }) {
  const { user, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="w-10 h-10 border-4 border-[#299283] border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!user) {
    // 원래 가려던 경로를 state에 저장해서 로그인 후 복원 가능하게
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return <>{children}</>;
}

// 이미 로그인된 사용자가 /login에 접근하면 /dashboard로
function PublicRoute({ children }: { children: ReactNode }) {
  const { user, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="w-10 h-10 border-4 border-[#299283] border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (user) {
    return <Navigate to="/dashboard" replace />;
  }

  return <>{children}</>;
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          {/* 랜딩 페이지 (모두 접근 가능) */}
          <Route path="/" element={<LandingPage />} />

          {/* 로그인 페이지 (비로그인 전용) */}
          <Route
            path="/login"
            element={
              <PublicRoute>
                <LoginScreen />
              </PublicRoute>
            }
          />

          {/* 회원가입 페이지 (비로그인 전용) */}
          <Route
            path="/signup"
            element={
              <PublicRoute>
                <SignupScreen />
              </PublicRoute>
            }
          />

          {/* OAuth 콜백 (소셜 로그인 후 백엔드에서 리디렉션되는 경로) */}
          <Route path="/oauth/callback" element={<OAuthCallback />} />

          {/* 대시보드 (로그인 전용) */}
          <Route
            path="/dashboard"
            element={
              <PrivateRoute>
                <Dashboard />
              </PrivateRoute>
            }
          />

          {/* 뷰어 로컬 테스트 (백엔드 없이 public/의 정적 파일로 확인) */}
          <Route
            path="/viewer-test"
            element={
              <div className="min-h-screen bg-[#f3f6f4] p-6">
                <Viewer3D
                  jobId="viewer-test"
                  resultUrl="/sample3.splat"
                  vehiclesUrl="/sample3_vehicles.json"
                />
              </div>
            }
          />

          {/* 그 외 경로: 랜딩으로 */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
