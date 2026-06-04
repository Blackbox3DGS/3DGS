import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router';
import { TrajectoryDiagram } from './TrajectoryDiagram';

/**
 * ReScene 랜딩 페이지
 * 브랜드 가이드 v2.0 — 9장 (이머시브 다크 모던) 기반
 * Color: Deep Green (#20543d) + Teal (#299283)
 */
export function LandingPage() {
  const navigate = useNavigate();
  const [scrolled, setScrolled] = useState(false);
  const observerRef = useRef<IntersectionObserver | null>(null);

  // Scrolled nav state
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 30);
    window.addEventListener('scroll', onScroll);
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  // Scroll-trigger fade-in
  useEffect(() => {
    observerRef.current = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add('rs-in');
          }
        });
      },
      { threshold: 0.15 },
    );
    document.querySelectorAll('.rs-reveal').forEach((el) => {
      observerRef.current?.observe(el);
    });
    return () => observerRef.current?.disconnect();
  }, []);

  const goLogin = () => navigate('/login');

  return (
    <>
      <style>{`
        /* 브랜드 색상 토큰은 styles/theme.css 전역 :root에서 상속 */
        .rs-reveal {
          opacity: 0;
          transform: translateY(28px);
          transition: opacity 0.7s ease-out, transform 0.7s ease-out;
        }
        .rs-reveal.rs-in {
          opacity: 1;
          transform: translateY(0);
        }
        .rs-stagger > * { transition-delay: 0s; }
        .rs-stagger.rs-in > *:nth-child(1) { transition-delay: 0.05s; }
        .rs-stagger.rs-in > *:nth-child(2) { transition-delay: 0.15s; }
        .rs-stagger.rs-in > *:nth-child(3) { transition-delay: 0.25s; }
        .rs-stagger.rs-in > *:nth-child(4) { transition-delay: 0.35s; }
        .rs-stagger.rs-in > *:nth-child(5) { transition-delay: 0.45s; }
        @keyframes rs-bounce {
          0%, 100% { transform: translateY(0); opacity: 0.4; }
          50% { transform: translateY(8px); opacity: 0.9; }
        }
        @keyframes rs-float {
          0%, 100% { transform: translateY(0); }
          50% { transform: translateY(-10px); }
        }
        @media (prefers-reduced-motion: reduce) {
          .rs-reveal { opacity: 1; transform: none; transition: none; }
        }
      `}</style>

      <div
        className="min-h-screen text-white font-sans"
        style={{
          backgroundColor: 'var(--green-950)',
          fontFamily: '"Plus Jakarta Sans", "Pretendard", system-ui, sans-serif',
        }}
      >
        {/* ─── Navigation ─── */}
        <nav
          className="fixed top-0 left-0 right-0 z-50 transition-all duration-300"
          style={{
            backgroundColor: scrolled ? 'rgba(10, 30, 20, 0.85)' : 'transparent',
            backdropFilter: scrolled ? 'blur(12px)' : 'none',
            WebkitBackdropFilter: scrolled ? 'blur(12px)' : 'none',
            borderBottom: scrolled
              ? '1px solid rgba(255,255,255,0.06)'
              : '1px solid transparent',
          }}
        >
          <div className="max-w-[1200px] mx-auto px-6 lg:px-10 h-16 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <img
                src="/rs-mark.png"
                alt="ReScene"
                className="h-7 w-7"
                style={{ filter: 'brightness(0) invert(1)' }}
              />
              <span className="text-[15px] font-semibold tracking-tight">ReScene</span>
            </div>
            <div className="hidden md:flex items-center gap-8 text-[14px]" style={{ color: 'rgba(255,255,255,0.7)' }}>
              <a href="#problem" className="hover:text-white transition-colors">문제</a>
              <a href="#solution" className="hover:text-white transition-colors">솔루션</a>
              <a href="#pipeline" className="hover:text-white transition-colors">파이프라인</a>
              <a href="#result" className="hover:text-white transition-colors">결과</a>
            </div>
            <button
              onClick={goLogin}
              className="rs-btn-primary px-5 py-2 rounded-lg text-[13px] font-medium"
            >
              시작하기
            </button>
          </div>
        </nav>

        {/* ─── Hero ─── */}
        <section
          className="relative flex items-center"
          style={{
            minHeight: '100vh',
            background:
              'linear-gradient(135deg, #0a1e14 0%, #0f2e1f 60%, #0d3d35 100%)',
          }}
        >
          {/* Subtle grid overlay */}
          <div
            aria-hidden
            className="absolute inset-0 pointer-events-none"
            style={{
              backgroundImage:
                'linear-gradient(rgba(92,191,174,0.04) 1px, transparent 1px), linear-gradient(90deg, rgba(92,191,174,0.04) 1px, transparent 1px)',
              backgroundSize: '64px 64px',
              maskImage: 'radial-gradient(ellipse 70% 70% at 30% 50%, black 20%, transparent 75%)',
              WebkitMaskImage: 'radial-gradient(ellipse 70% 70% at 30% 50%, black 20%, transparent 75%)',
            }}
          />

          {/* Teal dot cluster (point-cloud motif) */}
          <div aria-hidden className="absolute right-[10%] top-1/2 -translate-y-1/2 pointer-events-none">
            <div className="relative w-[280px] h-[280px]">
              {[
                { x: 30, y: 20, s: 4, o: 0.9 },
                { x: 80, y: 60, s: 3, o: 0.7 },
                { x: 140, y: 30, s: 5, o: 1 },
                { x: 200, y: 90, s: 3, o: 0.6 },
                { x: 60, y: 130, s: 4, o: 0.8 },
                { x: 170, y: 170, s: 6, o: 1 },
                { x: 230, y: 140, s: 3, o: 0.5 },
                { x: 110, y: 220, s: 4, o: 0.7 },
                { x: 40, y: 200, s: 3, o: 0.6 },
                { x: 220, y: 230, s: 5, o: 0.8 },
              ].map((p, i) => (
                <div
                  key={i}
                  className="absolute rounded-full"
                  style={{
                    left: p.x,
                    top: p.y,
                    width: p.s,
                    height: p.s,
                    backgroundColor: 'var(--teal-500)',
                    opacity: p.o,
                    boxShadow: `0 0 ${p.s * 3}px rgba(41,146,131,0.3)`,
                    animation: `rs-float ${4 + (i % 3)}s ease-in-out ${i * 0.3}s infinite`,
                  }}
                />
              ))}
              {/* Connecting lines */}
              <svg className="absolute inset-0 w-full h-full" style={{ opacity: 0.25 }}>
                <line x1="32" y1="22" x2="142" y2="32" stroke="var(--teal-300)" strokeWidth="0.5" />
                <line x1="142" y1="32" x2="172" y2="172" stroke="var(--teal-300)" strokeWidth="0.5" />
                <line x1="62" y1="132" x2="172" y2="172" stroke="var(--teal-300)" strokeWidth="0.5" />
                <line x1="172" y1="172" x2="222" y2="232" stroke="var(--teal-300)" strokeWidth="0.5" />
              </svg>
            </div>
          </div>

          <div className="relative max-w-[1200px] w-full mx-auto px-6 lg:px-10">
            <div className="max-w-[680px]">
              <div className="rs-reveal">
                <div
                  className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full mb-8"
                  style={{
                    backgroundColor: 'rgba(41,146,131,0.12)',
                    border: '1px solid rgba(41,146,131,0.25)',
                  }}
                >
                  <div
                    className="w-1.5 h-1.5 rounded-full"
                    style={{ backgroundColor: 'var(--teal-300)' }}
                  />
                  <span className="text-[12px] tracking-wide" style={{ color: 'var(--teal-300)' }}>
                    3D Gaussian Splatting · 단안 영상 재구성
                  </span>
                </div>
              </div>

              <h1
                className="rs-reveal text-[44px] md:text-[56px] font-bold leading-[1.1] tracking-tight mb-6"
                style={{ fontFamily: '"DM Serif Display", Georgia, serif' }}
              >
                사고 장면을,{' '}
                <span style={{ color: 'var(--teal-500)' }}>Re</span>Scene하다.
              </h1>

              <p
                className="rs-reveal text-[18px] md:text-[20px] leading-relaxed mb-10 max-w-[560px]"
                style={{ color: 'rgba(255,255,255,0.65)' }}
              >
                블랙박스 한 대의 영상만으로 사고 장면을 3D로 재구성합니다.
                <br />
                LiDAR 없이도 충돌 순간의 궤적과 속도를 객관적으로 분석합니다.
              </p>

              <div className="rs-reveal flex flex-col sm:flex-row gap-3">
                <a
                  href="#solution"
                  className="px-7 py-3.5 rounded-lg text-[15px] font-medium text-white transition-all text-center"
                  style={{
                    backgroundColor: 'transparent',
                    border: '1.5px solid rgba(255,255,255,0.2)',
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = 'rgba(255,255,255,0.05)')}
                  onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
                >
                  자세히 보기
                </a>
              </div>
            </div>
          </div>

          {/* Scroll hint */}
          <div
            aria-hidden
            className="absolute bottom-8 left-1/2 -translate-x-1/2 flex flex-col items-center gap-1"
            style={{ color: 'rgba(255,255,255,0.4)' }}
          >
            <span className="text-[11px] tracking-widest uppercase">scroll</span>
            <div style={{ animation: 'rs-bounce 2s ease-in-out infinite' }}>
              <svg viewBox="0 0 16 16" className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M4 6l4 4 4-4" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </div>
          </div>
        </section>

        {/* ─── Problem (Light) ─── */}
        <section id="problem" className="py-[120px]" style={{ backgroundColor: 'var(--neutral-50)' }}>
          <div className="max-w-[1200px] mx-auto px-6 lg:px-10">
            <div className="rs-reveal mb-16 max-w-[680px]">
              <div className="text-[12px] tracking-widest uppercase mb-4" style={{ color: 'var(--teal-500)' }}>
                Problem
              </div>
              <h2 className="text-[36px] md:text-[40px] font-bold leading-tight tracking-tight" style={{ color: 'var(--green-500)' }}>
                기존 사고 분석의 한계
              </h2>
              <p className="mt-5 text-[16px] leading-relaxed" style={{ color: 'var(--neutral-500)' }}>
                블랙박스는 일상화되었지만, 평면 영상만으로는 충돌 순간의 공간 정보를 파악할 수 없습니다.
                전문 재구성 장비는 경찰·대형 보험사 전용이며 일반 피해자는 객관적 증거를 확보하기 어렵습니다.
              </p>
            </div>

            <div className="rs-reveal rs-stagger grid grid-cols-1 md:grid-cols-3 gap-6">
              {[
                {
                  stat: '80%+',
                  label: '국내 블랙박스 보급률',
                  desc: '단안 영상 데이터는 이미 대량으로 존재합니다.',
                },
                {
                  stat: '20만+',
                  label: '연간 교통사고 건수',
                  desc: '경찰청 통계 기준, 매년 발생하는 사고 건수입니다.',
                },
                {
                  stat: '2D',
                  label: '현재 증거 한계',
                  desc: '평면 영상만으로는 거리·속도·각도를 정확히 알 수 없습니다.',
                },
              ].map((item, i) => (
                <div
                  key={i}
                  className="rs-reveal p-8 rounded-xl bg-white transition-all hover:-translate-y-1"
                  style={{
                    border: '1px solid var(--neutral-200)',
                  }}
                >
                  <div
                    className="text-[48px] font-bold leading-none mb-4"
                    style={{ color: 'var(--teal-500)' }}
                  >
                    {item.stat}
                  </div>
                  <div className="text-[15px] font-semibold mb-2" style={{ color: 'var(--green-500)' }}>
                    {item.label}
                  </div>
                  <div className="text-[14px] leading-relaxed" style={{ color: 'var(--neutral-500)' }}>
                    {item.desc}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ─── Solution (Dark) ─── */}
        <section id="solution" className="py-[120px]" style={{ backgroundColor: 'var(--green-900)' }}>
          <div className="max-w-[1200px] mx-auto px-6 lg:px-10">
            <div className="grid grid-cols-1 lg:grid-cols-[1.1fr_1fr] gap-16 items-center">
              {/* 3D Mock visualization */}
              <div
                className="rs-reveal relative rounded-xl overflow-hidden"
                style={{
                  backgroundColor: 'var(--green-950)',
                  border: '1px solid rgba(255,255,255,0.08)',
                  aspectRatio: '4 / 3',
                }}
              >
                {/* Header bar */}
                <div
                  className="flex items-center justify-between px-4 py-2.5"
                  style={{ borderBottom: '1px solid rgba(255,255,255,0.06)' }}
                >
                  <div className="flex items-center gap-3 text-[10px] font-mono" style={{ color: 'rgba(255,255,255,0.4)' }}>
                    <span style={{ color: 'var(--teal-300)' }}>RC-2026-0041</span>
                    <span
                      className="px-1.5 py-0.5 rounded text-[9px]"
                      style={{ color: 'var(--teal-300)', backgroundColor: 'rgba(41,146,131,0.15)' }}
                    >
                      복원 완료
                    </span>
                  </div>
                  <span className="text-[10px] font-mono" style={{ color: 'rgba(255,255,255,0.3)' }}>847 / 847</span>
                </div>

                {/* SVG diagram */}
                <div className="absolute left-0 right-0" style={{ top: '38px', bottom: '0' }}>
                  <TrajectoryDiagram />
                </div>
              </div>

              {/* Text */}
              <div className="rs-reveal">
                <div className="text-[12px] tracking-widest uppercase mb-4" style={{ color: 'var(--teal-300)' }}>
                  Solution
                </div>
                <h2 className="text-[36px] md:text-[40px] font-bold leading-tight tracking-tight text-white mb-6">
                  단안 영상에서<br />
                  <span style={{ color: 'var(--teal-500)' }}>3D 장면</span>을 복원합니다
                </h2>
                <p className="text-[16px] leading-relaxed mb-8" style={{ color: 'rgba(255,255,255,0.75)' }}>
                  최신 단안 깊이 추정과 3D Gaussian Splatting을 결합한 End-to-End 파이프라인으로,
                  블랙박스 영상 하나만 있으면 사고 장면을 다각도에서 분석할 수 있습니다.
                </p>
                <div className="space-y-4">
                  {[
                    { k: '차량별 궤적 자동 추출', v: '객체 추적과 깊이 정보 융합' },
                    { k: '충돌 각도·속도 산출', v: '시간축 위치 미분으로 직접 계산' },
                    { k: '자유 시점 렌더링', v: '브라우저에서 실시간 카메라 조작' },
                  ].map((item, i) => (
                    <div key={i} className="flex items-start gap-3">
                      <div
                        className="mt-1.5 w-1 h-1 rounded-full shrink-0"
                        style={{ backgroundColor: 'var(--teal-500)' }}
                      />
                      <div>
                        <div className="text-[15px] font-medium text-white">{item.k}</div>
                        <div className="text-[13px] mt-0.5" style={{ color: 'rgba(255,255,255,0.5)' }}>{item.v}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ─── Pipeline (Darker) ─── */}
        <section id="pipeline" className="py-[120px]" style={{ backgroundColor: 'var(--green-950)' }}>
          <div className="max-w-[1200px] mx-auto px-6 lg:px-10">
            <div className="rs-reveal mb-16 max-w-[680px]">
              <div className="text-[12px] tracking-widest uppercase mb-4" style={{ color: 'var(--teal-300)' }}>
                Pipeline
              </div>
              <h2 className="text-[36px] md:text-[40px] font-bold leading-tight tracking-tight text-white">
                10단계 End-to-End 처리
              </h2>
              <p className="mt-5 text-[16px] leading-relaxed" style={{ color: 'rgba(255,255,255,0.7)' }}>
                입력 영상부터 .splat 출력까지 모든 단계가 독립적으로 교체·개선 가능한 구조입니다.
              </p>
            </div>

            <div className="rs-reveal rs-stagger grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
              {[
                { n: '01', t: '프레임 추출', d: 'FFmpeg, FPS 분리' },
                { n: '02', t: '객체 분할 / 추적', d: 'YOLOv8 + ByteTrack' },
                { n: '03', t: 'COLMAP SfM', d: '마스크 적용 포즈 추정' },
                { n: '04', t: '단안 깊이 추정', d: 'Depth Anything V2' },
                { n: '05', t: '스케일 정렬', d: 'COLMAP + 카메라 prior' },
                { n: '06', t: '포인트 클라우드', d: '역투영 + 다중 프레임 병합' },
                { n: '07', t: '아웃라이어 제거', d: 'Open3D SOR' },
                { n: '08', t: '3D 궤적 추출', d: '객체별 시간축 위치' },
                { n: '09', t: '3DGS 학습', d: '마스크 loss 제외' },
                { n: '10', t: '.splat 변환', d: '웹 뷰어 출력' },
              ].map((step, i) => (
                <div
                  key={i}
                  className="rs-reveal p-5 rounded-xl transition-all hover:-translate-y-1"
                  style={{
                    backgroundColor: 'var(--green-800)',
                    border: '1px solid rgba(255,255,255,0.06)',
                    borderLeft: '3px solid var(--teal-500)',
                  }}
                >
                  <div className="text-[11px] font-mono mb-2" style={{ color: 'var(--teal-300)' }}>
                    STEP {step.n}
                  </div>
                  <div className="text-[15px] font-semibold text-white mb-1">{step.t}</div>
                  <div className="text-[12px]" style={{ color: 'rgba(255,255,255,0.55)' }}>{step.d}</div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ─── Result Comparison (Light) ─── */}
        <section id="result" className="py-[120px]" style={{ backgroundColor: 'var(--neutral-50)' }}>
          <div className="max-w-[1200px] mx-auto px-6 lg:px-10">
            <div className="rs-reveal mb-16 max-w-[680px]">
              <div className="text-[12px] tracking-widest uppercase mb-4" style={{ color: 'var(--teal-500)' }}>
                Result
              </div>
              <h2 className="text-[36px] md:text-[40px] font-bold leading-tight tracking-tight" style={{ color: 'var(--green-500)' }}>
                기존 기술과의 차이
              </h2>
            </div>

            <div className="rs-reveal grid grid-cols-1 md:grid-cols-3 gap-6">
              {[
                {
                  title: 'Vanilla 3DGS',
                  sub: '단안 + 마스크 없음',
                  rows: [
                    ['동적 객체 처리', '없음'],
                    ['배경 재구성', '저하'],
                    ['LiDAR 필요', '없음'],
                  ],
                  highlight: false,
                },
                {
                  title: 'ReScene',
                  sub: '본 파이프라인',
                  rows: [
                    ['동적 객체 처리', '마스크 분리'],
                    ['배경 재구성', '고품질'],
                    ['LiDAR 필요', '없음'],
                  ],
                  highlight: true,
                },
                {
                  title: 'Street Gaussians',
                  sub: 'LiDAR 기반',
                  rows: [
                    ['동적 객체 처리', '있음'],
                    ['배경 재구성', '고품질'],
                    ['LiDAR 필요', '필수'],
                  ],
                  highlight: false,
                },
              ].map((col, i) => (
                <div
                  key={i}
                  className="rounded-xl p-6 transition-all hover:-translate-y-1"
                  style={{
                    backgroundColor: '#ffffff',
                    border: col.highlight
                      ? '2px solid var(--teal-500)'
                      : '1px solid var(--neutral-200)',
                    boxShadow: col.highlight ? '0 0 60px rgba(41, 146, 131, 0.12)' : 'none',
                  }}
                >
                  <div className="flex items-center justify-between mb-1">
                    <div className="text-[18px] font-bold" style={{ color: col.highlight ? 'var(--teal-500)' : 'var(--green-500)' }}>
                      {col.title}
                    </div>
                    {col.highlight && (
                      <span
                        className="text-[10px] font-mono px-2 py-0.5 rounded"
                        style={{ color: 'var(--teal-500)', backgroundColor: 'rgba(41,146,131,0.1)' }}
                      >
                        본 프로젝트
                      </span>
                    )}
                  </div>
                  <div className="text-[12px] mb-5" style={{ color: 'var(--neutral-400)' }}>
                    {col.sub}
                  </div>
                  <div className="space-y-3">
                    {col.rows.map(([k, v], j) => (
                      <div key={j} className="flex items-center justify-between py-2" style={{ borderBottom: '1px solid var(--neutral-100)' }}>
                        <span className="text-[13px]" style={{ color: 'var(--neutral-500)' }}>{k}</span>
                        <span className="text-[13px] font-medium" style={{ color: col.highlight ? 'var(--teal-500)' : 'var(--green-500)' }}>
                          {v}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ─── CTA / Footer ─── */}
        <section className="relative" style={{ backgroundColor: 'var(--green-950)' }}>
          <div className="py-[120px] max-w-[1200px] mx-auto px-6 lg:px-10 text-center">
            <div className="rs-reveal">
              <img
                src="/rs-mark.png"
                alt="ReScene"
                className="h-10 w-10 mx-auto mb-8 opacity-70"
                style={{ filter: 'brightness(0) invert(1)' }}
              />
              <h2
                className="text-[40px] md:text-[48px] font-bold leading-tight tracking-tight text-white mb-5"
                style={{ fontFamily: '"DM Serif Display", Georgia, serif' }}
              >
                사고 장면을, <span style={{ color: 'var(--teal-500)' }}>다시</span> 만들다
              </h2>
              <p className="text-[17px] max-w-[520px] mx-auto" style={{ color: 'rgba(255,255,255,0.6)' }}>
                블랙박스 단안 영상만으로 사고 장면을 3D Gaussian Splatting으로 재구성하는 End-to-End 파이프라인.
              </p>
            </div>
          </div>

          {/* Footer */}
          <div
            className="py-8 px-6 lg:px-10"
            style={{ borderTop: '1px solid rgba(255,255,255,0.06)' }}
          >
            <div className="max-w-[1200px] mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
              <div className="flex items-center gap-2">
                <img
                  src="/rs-mark.png"
                  alt="ReScene"
                  className="h-5 w-5 opacity-60"
                  style={{ filter: 'brightness(0) invert(1)' }}
                />
                <span className="text-[13px]" style={{ color: 'rgba(255,255,255,0.5)' }}>
                  ReScene
                </span>
                <span className="text-[11px] font-mono ml-2" style={{ color: 'rgba(255,255,255,0.3)' }}>
                  v0.1.0
                </span>
              </div>
              <span className="text-[12px]" style={{ color: 'rgba(255,255,255,0.35)' }}>
                © 2026 ReScene · 졸업작품 프로젝트
              </span>
            </div>
          </div>
        </section>
      </div>
    </>
  );
}
