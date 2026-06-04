import { useState } from 'react';
import { useNavigate } from 'react-router';
import apiClient from '../../lib/apiClient';

export function SignupScreen() {
  const navigate = useNavigate();

  const [form, setForm] = useState({
    userId: '',
    password: '',
    passwordConfirm: '',
    name: '',
    email: '',
  });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const set = (key: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) => {
    setForm((prev) => ({ ...prev, [key]: e.target.value }));
    setErrorMessage(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);

    if (form.password !== form.passwordConfirm) {
      setErrorMessage('비밀번호가 일치하지 않습니다.');
      return;
    }
    if (form.password.length < 8) {
      setErrorMessage('비밀번호는 8자 이상이어야 합니다.');
      return;
    }

    setIsSubmitting(true);
    try {
      await apiClient.post('/api/auth/signup', {
        userId: form.userId,
        password: form.password,
        name: form.name,
        email: form.email,
      });
      navigate('/login', { replace: true });
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response?.status;
      if (status === 409) {
        setErrorMessage('이미 사용 중인 아이디 또는 이메일입니다.');
      } else if (status === 400) {
        setErrorMessage('입력 정보를 확인해주세요.');
      } else {
        setErrorMessage('회원가입 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const inputClass =
    'w-full px-3.5 py-2.5 rounded-lg text-[14px] text-white transition-colors focus:outline-none';
  const inputStyle = {
    backgroundColor: 'rgba(21,61,43,0.5)',
    border: '1px solid rgba(255,255,255,0.08)',
  };
  const onFocus = (e: React.FocusEvent<HTMLInputElement>) => {
    e.currentTarget.style.borderColor = '#299283';
    e.currentTarget.style.boxShadow = '0 0 0 3px rgba(41,146,131,0.15)';
  };
  const onBlur = (e: React.FocusEvent<HTMLInputElement>) => {
    e.currentTarget.style.borderColor = 'rgba(255,255,255,0.08)';
    e.currentTarget.style.boxShadow = 'none';
  };

  return (
    <div
      className="min-h-screen flex items-center justify-center px-4"
      style={{
        backgroundColor: '#0a1e14',
        fontFamily: '"Plus Jakarta Sans", "Pretendard", system-ui, sans-serif',
      }}
    >
      {/* Background grid */}
      <div
        aria-hidden
        className="pointer-events-none fixed inset-0"
        style={{
          backgroundImage:
            'linear-gradient(rgba(92,191,174,0.035) 1px, transparent 1px), linear-gradient(90deg, rgba(92,191,174,0.035) 1px, transparent 1px)',
          backgroundSize: '48px 48px',
          maskImage: 'radial-gradient(ellipse 80% 70% at 50% 50%, black 30%, transparent 80%)',
          WebkitMaskImage: 'radial-gradient(ellipse 80% 70% at 50% 50%, black 30%, transparent 80%)',
        }}
      />

      <div className="relative w-full max-w-[380px]">
        {/* Logo */}
        <button
          onClick={() => navigate('/')}
          className="flex items-center gap-2 mb-8 transition-opacity hover:opacity-80"
        >
          <img
            src="/rs-mark.png"
            alt="ReScene"
            className="h-5 w-5"
            style={{ filter: 'brightness(0) invert(1)' }}
          />
          <span className="text-[13px] font-semibold tracking-tight text-white">ReScene</span>
        </button>

        {/* Title */}
        <div className="mb-6">
          <h1 className="text-[20px] font-medium tracking-tight text-white">회원가입</h1>
          <p className="mt-1 text-[13px]" style={{ color: 'rgba(255,255,255,0.55)' }}>
            계정을 만들어 분석을 시작하세요.
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
        <form onSubmit={handleSubmit} className="space-y-3.5">
          {[
            { id: 'userId',          label: '아이디',        type: 'text',     placeholder: '사용할 아이디 입력' },
            { id: 'name',            label: '이름',          type: 'text',     placeholder: '이름 입력' },
            { id: 'email',           label: '이메일',        type: 'email',    placeholder: 'example@email.com' },
            { id: 'password',        label: '비밀번호',      type: 'password', placeholder: '8자 이상 입력' },
            { id: 'passwordConfirm', label: '비밀번호 확인', type: 'password', placeholder: '비밀번호 재입력' },
          ].map(({ id, label, type, placeholder }) => (
            <div key={id}>
              <label
                htmlFor={id}
                className="block text-[12px] mb-1.5"
                style={{ color: 'rgba(255,255,255,0.55)' }}
              >
                {label}
              </label>
              <input
                id={id}
                type={type}
                placeholder={placeholder}
                value={form[id as keyof typeof form]}
                onChange={set(id as keyof typeof form)}
                required
                className={inputClass}
                style={inputStyle}
                onFocus={onFocus}
                onBlur={onBlur}
              />
            </div>
          ))}

          <div className="pt-1 space-y-2">
            <button
              type="submit"
              disabled={isSubmitting}
              className="rs-btn-primary w-full py-2.5 rounded-lg text-[14px] font-medium flex items-center justify-center gap-2"
            >
              {isSubmitting ? (
                <>
                  <div className="w-4 h-4 border-2 border-white/50 border-t-white rounded-full animate-spin" />
                  가입 중...
                </>
              ) : '가입하기'}
            </button>

            <button
              type="button"
              onClick={() => navigate('/login')}
              disabled={isSubmitting}
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
              이미 계정이 있으신가요? 로그인
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
