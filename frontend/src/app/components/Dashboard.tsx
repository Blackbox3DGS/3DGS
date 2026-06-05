import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router';
import { Upload, LogOut, Activity, CheckCircle2, Clock } from 'lucide-react';
import { toast } from 'sonner';
import { AnalysisHistory } from './AnalysisHistory';
import { Viewer3D } from './Viewer3D';
import { useAuth } from '../../context/AuthContext';
import apiClient from '../../lib/apiClient';

// 백엔드 JobStatusResponse 필드명에 맞춤
export interface AnalysisRecord {
  jobId: string;
  customTitle: string;
  status: 'PENDING' | 'PRE_PROCESSING' | 'WAITING_FOR_TARGET' | 'PROCESSING' | 'COMPLETED' | 'FAILED';
  statusDescription: string;
  progress: number;
  currentStep: string;
  createdAt: string;
  incidentDate: string;
  resultUrl?: string;
  trajectoryUrl?: string;
}

// userId 기반 일관된 랜덤 닉네임 생성
function generateNickname(userId: string): string {
  const adjectives = ['빠른', '느린', '조용한', '활발한', '신중한', '대담한', '차분한', '씩씩한', '영리한', '용감한'];
  const nouns = ['독수리', '호랑이', '판다', '여우', '늑대', '사자', '고래', '매', '곰', '토끼'];
  // userId 문자열로 간단한 해시 생성
  let hash = 0;
  for (let i = 0; i < userId.length; i++) {
    hash = (hash * 31 + userId.charCodeAt(i)) >>> 0;
  }
  const adj = adjectives[hash % adjectives.length];
  const noun = nouns[Math.floor(hash / adjectives.length) % nouns.length];
  const num = (hash % 9000) + 1000; // 1000~9999
  return `${adj}${noun}${num}`;
}

// 폴링이 필요한 상태
const POLLING_STATUSES: AnalysisRecord['status'][] = [
  'PENDING',
  'PRE_PROCESSING',
  'WAITING_FOR_TARGET',
  'PROCESSING',
];

// 데모 사용자용 샘플 데이터
const DEMO_RECORDS: AnalysisRecord[] = [
  {
    jobId: 'demo-1',
    customTitle: '강남구 사거리 추돌사고',
    status: 'COMPLETED',
    statusDescription: '분석 완료',
    progress: 100,
    currentStep: '완료',
    createdAt: '2025-03-10T09:15:00',
    incidentDate: '2025-03-08T14:30:00',
    resultUrl: undefined,
  },
  {
    jobId: 'demo-2',
    customTitle: '고속도로 측면 충돌',
    status: 'PROCESSING',
    statusDescription: '3D 복원 중',
    progress: 62,
    currentStep: '궤적 계산',
    createdAt: '2025-03-12T11:00:00',
    incidentDate: '2025-03-11T08:20:00',
  },
  {
    jobId: 'demo-3',
    customTitle: '주차장 후진 접촉',
    status: 'PENDING',
    statusDescription: '대기 중',
    progress: 0,
    currentStep: '대기',
    createdAt: '2025-03-13T16:45:00',
    incidentDate: '2025-03-13T15:10:00',
  },
];

const POLL_INTERVAL_MS = 5000;
const SEARCH_DEBOUNCE_MS = 300;

export function Dashboard() {
  const navigate = useNavigate();
  const { user, logout } = useAuth();

  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [selectedRecord, setSelectedRecord] = useState<AnalysisRecord | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [records, setRecords] = useState<AnalysisRecord[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isUploading, setIsUploading] = useState(false);

  // 검색어 (AnalysisHistory에서 통지받음) + 디바운스된 값
  const [searchKeyword, setSearchKeyword] = useState('');
  const [debouncedKeyword, setDebouncedKeyword] = useState('');

  const isDemo = user?.userId === 'demo';
  const pollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // 분석 기록 목록 조회 (데모면 더미 데이터, 실모드면 keyword 서버 전달)
  const fetchRecords = async (keyword?: string) => {
    if (isDemo) {
      setRecords(DEMO_RECORDS);
      return DEMO_RECORDS;
    }
    try {
      const params: Record<string, string> = {};
      if (keyword && keyword.trim()) params.keyword = keyword.trim();
      const res = await apiClient.get<AnalysisRecord[] | { result: AnalysisRecord[] }>(
        '/api/v1/reconstruction',
        { params }
      );
      // BaseResponse 래퍼({ result: [...] })와 직접 배열 응답 둘 다 허용
      const raw = res.data as unknown;
      const data: AnalysisRecord[] = Array.isArray(raw)
        ? (raw as AnalysisRecord[])
        : Array.isArray((raw as { result?: unknown })?.result)
        ? ((raw as { result: AnalysisRecord[] }).result)
        : [];
      setRecords(data);
      return data;
    } catch (err) {
      console.error('목록 조회 실패:', err);
      return null;
    }
  };

  // 폴링: 진행 중인 job이 있으면 5초마다 자동 갱신 (데모는 폴링 안 함)
  const schedulePolling = (data: AnalysisRecord[]) => {
    if (isDemo) return;
    if (pollTimerRef.current) clearTimeout(pollTimerRef.current);
    const hasInProgress = data.some((r) => POLLING_STATUSES.includes(r.status));
    if (!hasInProgress) return;

    pollTimerRef.current = setTimeout(async () => {
      const updated = await fetchRecords(debouncedKeyword);
      if (updated) schedulePolling(updated);
    }, POLL_INTERVAL_MS);
  };

  useEffect(() => {
    (async () => {
      const data = await fetchRecords();
      setIsLoading(false);
      if (data) schedulePolling(data);
    })();

    return () => {
      if (pollTimerRef.current) clearTimeout(pollTimerRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 검색어 디바운스: 입력 멈춘 뒤 300ms 후 debouncedKeyword에 반영
  useEffect(() => {
    const t = setTimeout(() => setDebouncedKeyword(searchKeyword), SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(t);
  }, [searchKeyword]);

  // 디바운스된 검색어 변경 시 서버 재조회 (데모는 클라이언트 필터로 충분하므로 스킵)
  useEffect(() => {
    if (isDemo) return;
    // 초기 로딩 중에는 위의 첫 useEffect가 처리하므로 중복 호출 방지
    if (isLoading) return;
    (async () => {
      const data = await fetchRecords(debouncedKeyword);
      if (data) schedulePolling(data);
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedKeyword]);

  // 폴링 갱신 시 selectedRecord도 동기화
  useEffect(() => {
    if (!records.length) return;
    schedulePolling(records);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [records]);

  // 선택된 jobId에 맞는 record 동기화
  useEffect(() => {
    if (selectedJobId) {
      const found = records.find(r => r.jobId === selectedJobId) ?? null;
      setSelectedRecord(found);
    } else {
      setSelectedRecord(null);
    }
  }, [selectedJobId, records]);

  // 이름 변경 → 백엔드 저장 (데모면 로컬만 변경)
  const handleRenameVideo = async (jobId: string, newTitle: string) => {
    if (isDemo) {
      setRecords(prev =>
        prev.map(r => r.jobId === jobId ? { ...r, customTitle: newTitle } : r)
      );
      return;
    }
    try {
      await apiClient.patch(
        `/api/v1/reconstruction/${jobId}/title?newTitle=${encodeURIComponent(newTitle)}`
      );
      setRecords(prev =>
        prev.map(r => r.jobId === jobId ? { ...r, customTitle: newTitle } : r)
      );
    } catch (err) {
      console.error('이름 변경 실패:', err);
      toast.error('이름 변경에 실패했습니다.');
    }
  };

  // 분석 기록 삭제 → 백엔드 호출 (데모면 로컬만 제거)
  const handleDeleteRecord = async (jobId: string) => {
    // 삭제하려는 기록이 현재 선택된 항목이면 선택 해제 (3D 뷰어 닫기)
    if (selectedJobId === jobId) {
      setSelectedJobId(null);
    }

    if (isDemo) {
      setRecords(prev => prev.filter(r => r.jobId !== jobId));
      toast.success('삭제되었습니다.');
      return;
    }
    try {
      await apiClient.delete(`/api/v1/reconstruction/${jobId}`);
      setRecords(prev => prev.filter(r => r.jobId !== jobId));
      toast.success('삭제되었습니다.');
    } catch (err) {
      console.error('삭제 실패:', err);
      toast.error('삭제에 실패했습니다.');
    }
  };

  // 드래그 앤 드롭 업로드
  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) await uploadFile(file);
  };

  // 파일 선택 업로드
  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) await uploadFile(file);
    e.target.value = '';
  };

  const uploadFile = async (file: File) => {
    if (isDemo) {
      toast.info('데모 모드에서는 파일 업로드가 지원되지 않습니다.');
      return;
    }
    // 파일 형식 검증
    if (!file.type.startsWith('video/')) {
      toast.error('동영상 파일만 업로드할 수 있습니다.');
      return;
    }
    // 파일 크기 검증 (2GB 제한)
    if (file.size > 2 * 1024 * 1024 * 1024) {
      toast.error('파일 크기는 2GB 이하여야 합니다.');
      return;
    }

    const formData = new FormData();
    formData.append('file', file);
    setIsUploading(true);
    try {
      await apiClient.post('/api/v1/reconstruction/upload', formData);
      toast.success('업로드 완료! 분석을 시작합니다.');
      const data = await fetchRecords(debouncedKeyword);
      if (data) schedulePolling(data);
    } catch (err) {
      console.error('업로드 실패:', err);
      toast.error('파일 업로드에 실패했습니다.');
    } finally {
      setIsUploading(false);
    }
  };

  // Metrics
  const totalCount = records.length;
  const inProgressCount = records.filter(r => POLLING_STATUSES.includes(r.status)).length;
  const completedCount = records.filter(r => r.status === 'COMPLETED').length;

  const displayName =
    user?.name?.trim() || (user ? generateNickname(user.userId || user.email || 'user') : '');

  return (
    <div
      className="min-h-screen relative"
      style={{
        backgroundColor: '#f7f9f8',
        fontFamily: '"Plus Jakarta Sans", "Pretendard", system-ui, sans-serif',
      }}
    >
      {/* Subtle grid background */}
      <div
        aria-hidden
        className="pointer-events-none fixed inset-0"
        style={{
          backgroundImage:
            'linear-gradient(rgba(32,84,61,0.025) 1px, transparent 1px), linear-gradient(90deg, rgba(32,84,61,0.025) 1px, transparent 1px)',
          backgroundSize: '48px 48px',
          maskImage: 'linear-gradient(to bottom, black 0%, transparent 70%)',
          WebkitMaskImage: 'linear-gradient(to bottom, black 0%, transparent 70%)',
        }}
      />

      {/* ─── Header ─── */}
      <header
        className="sticky top-0 z-30 backdrop-blur-md"
        style={{
          backgroundColor: 'rgba(255,255,255,0.85)',
          borderBottom: '1px solid #dae3dd',
        }}
      >
        <div className="max-w-7xl mx-auto px-6 lg:px-10 h-16 flex items-center justify-between">
          <button
            onClick={() => navigate('/')}
            className="flex items-center gap-2.5 transition-opacity hover:opacity-80"
          >
            <img src="/rs-mark.png" alt="ReScene" className="h-7 w-7" />
            <span className="text-[16px] font-semibold tracking-tight text-[#20543d]">
              ReScene
            </span>
            <span
              className="text-[10px] font-mono px-2 py-0.5 rounded ml-1 hidden sm:inline-flex"
              style={{ color: '#299283', backgroundColor: 'rgba(41,146,131,0.08)' }}
            >
              DASHBOARD
            </span>
          </button>
          <div className="flex items-center gap-3">
            {user && (
              <div className="hidden sm:flex items-center gap-2.5 px-3 py-1.5 rounded-full" style={{ backgroundColor: '#eef2f0' }}>
                <div
                  className="w-7 h-7 rounded-full flex items-center justify-center text-[12px] font-semibold text-white"
                  style={{ backgroundColor: '#299283' }}
                >
                  {displayName.charAt(0) || 'U'}
                </div>
                <span className="text-[13px] text-[#5a665e]">{displayName}</span>
              </div>
            )}
            <button
              onClick={logout}
              className="flex items-center gap-1.5 px-3 py-2 text-[13px] text-[#5a665e] hover:text-[#20543d] hover:bg-[#eef2f0] rounded-md transition-colors"
            >
              <LogOut className="w-4 h-4" />
              <span className="hidden sm:inline">로그아웃</span>
            </button>
          </div>
        </div>
      </header>

      <main className="relative max-w-7xl mx-auto px-6 lg:px-10 py-10">

        {/* ─── Top: Welcome + Metrics ─── */}
        <div className="mb-10 grid grid-cols-1 lg:grid-cols-[1fr_auto] gap-8 items-end">
          <div>
            <div
              className="text-[11px] tracking-widest uppercase mb-2 font-medium"
              style={{ color: '#299283' }}
            >
              Dashboard
            </div>
            <h1 className="text-[28px] md:text-[32px] font-bold tracking-tight text-[#20543d] leading-tight">
              {displayName ? `${displayName}님, 안녕하세요` : '안녕하세요'}
            </h1>
            <p className="mt-2 text-[14px] text-[#5a665e]">
              새로운 영상을 업로드하거나 기존 분석 기록을 확인하세요.
            </p>
          </div>

          {/* Metrics */}
          <div className="grid grid-cols-3 gap-3">
            {[
              { label: '전체', value: totalCount, Icon: Activity, accent: false },
              { label: '진행 중', value: inProgressCount, Icon: Clock, accent: true },
              { label: '완료', value: completedCount, Icon: CheckCircle2, accent: false },
            ].map(({ label, value, Icon, accent }) => (
              <div
                key={label}
                className="rounded-lg px-4 py-3 bg-white min-w-[110px] transition-shadow"
                style={{
                  border: accent ? '1px solid rgba(41,146,131,0.25)' : '1px solid var(--neutral-200)',
                  boxShadow: accent ? 'var(--rs-ring)' : 'var(--rs-shadow-xs)',
                }}
              >
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-[11px] text-[#8a9590]">{label}</span>
                  <Icon className="w-3.5 h-3.5" style={{ color: accent ? '#299283' : '#b8c4be' }} />
                </div>
                <div
                  className="text-[22px] font-bold leading-none tabular"
                  style={{ color: accent ? '#299283' : '#20543d' }}
                >
                  {value}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* ─── Upload Section ─── */}
        <section className="mb-10">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2.5">
              <div className="w-1 h-4 rounded-full" style={{ backgroundColor: '#299283' }} />
              <h2 className="text-[15px] font-semibold tracking-tight text-[#20543d]">
                새 영상 업로드
              </h2>
            </div>
            <span className="text-[11px] text-[#8a9590] font-mono">
              MP4 · AVI · MOV · 최대 2GB
            </span>
          </div>

          <div
            className="bg-white rounded-xl overflow-hidden"
            style={{ border: '1px solid var(--neutral-200)', boxShadow: 'var(--rs-shadow-sm)' }}
          >
            <div
              onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
              onDragLeave={() => setIsDragging(false)}
              onDrop={handleDrop}
              className="border-2 border-dashed m-2 rounded-lg p-10 text-center transition-all"
              style={{
                borderColor: isDragging ? '#299283' : '#dae3dd',
                backgroundColor: isDragging ? '#e6f5f2' : 'transparent',
              }}
            >
              {isUploading ? (
                <div className="flex flex-col items-center gap-3 py-4">
                  <div className="w-9 h-9 border-[3px] border-[#299283] border-t-transparent rounded-full animate-spin" />
                  <p className="text-[14px] text-[#5a665e]">업로드 중...</p>
                </div>
              ) : (
                <>
                  <div
                    className="inline-flex items-center justify-center w-14 h-14 rounded-full mb-4"
                    style={{ backgroundColor: '#e6f5f2' }}
                  >
                    <Upload className="w-6 h-6" style={{ color: '#299283' }} />
                  </div>
                  <p className="text-[15px] font-medium text-[#20543d] mb-1">
                    블랙박스 영상을 업로드하세요
                  </p>
                  <p className="text-[13px] text-[#8a9590] mb-5">
                    파일을 드래그 앤 드롭하거나 아래 버튼을 클릭하세요
                  </p>
                  <label
                    className="rs-btn-primary inline-flex items-center gap-2 px-5 py-2.5 rounded-lg text-[13px] font-medium cursor-pointer"
                  >
                    파일 선택
                    <input
                      type="file"
                      accept="video/*"
                      onChange={handleFileSelect}
                      className="hidden"
                    />
                  </label>
                </>
              )}
            </div>
          </div>
        </section>

        {/* ─── Analysis History ─── */}
        <section className="mb-10">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2.5">
              <div className="w-1 h-4 rounded-full" style={{ backgroundColor: '#299283' }} />
              <h2 className="text-[15px] font-semibold tracking-tight text-[#20543d]">
                나의 분석 기록
              </h2>
              {!isLoading && totalCount > 0 && (
                <span
                  className="text-[10px] font-mono px-1.5 py-0.5 rounded"
                  style={{ color: '#5a665e', backgroundColor: '#eef2f0' }}
                >
                  {totalCount}건
                </span>
              )}
            </div>
            {!isDemo && inProgressCount > 0 && (
              <div className="flex items-center gap-1.5 text-[11px]" style={{ color: '#299283' }}>
                <div
                  className="w-1.5 h-1.5 rounded-full"
                  style={{
                    backgroundColor: '#299283',
                    animation: 'pulse 1.5s ease-in-out infinite',
                  }}
                />
                <span className="font-mono">{inProgressCount}건 처리 중 · 자동 갱신</span>
              </div>
            )}
          </div>

          {isLoading ? (
            <div
              className="bg-white rounded-xl flex items-center justify-center h-48"
              style={{ border: '1px solid var(--neutral-200)', boxShadow: 'var(--rs-shadow-sm)' }}
            >
              <div className="flex flex-col items-center gap-3 text-[#8a9590]">
                <div className="w-7 h-7 border-[3px] border-[#299283] border-t-transparent rounded-full animate-spin" />
                <span className="text-[13px]">분석 기록을 불러오는 중...</span>
              </div>
            </div>
          ) : (
            <AnalysisHistory
              records={records}
              selectedJobId={selectedJobId}
              onSelectJob={setSelectedJobId}
              onRenameVideo={handleRenameVideo}
              onDeleteRecord={handleDeleteRecord}
              onSearchChange={setSearchKeyword}
            />
          )}
        </section>

        {/* ─── 3D Viewer ─── */}
        {selectedRecord && selectedRecord.status === 'COMPLETED' && (
          <section className="mb-10">
            <div className="flex items-center gap-2.5 mb-3">
              <div className="w-1 h-4 rounded-full" style={{ backgroundColor: '#299283' }} />
              <h2 className="text-[15px] font-semibold tracking-tight text-[#20543d]">
                3D 사고 복원
              </h2>
              <span className="text-[11px] font-mono text-[#8a9590]">
                {selectedRecord.customTitle}
              </span>
            </div>
            <Viewer3D
              jobId={selectedRecord.jobId}
              resultUrl={selectedRecord.resultUrl}
              trajectoryUrl={selectedRecord.trajectoryUrl}
            />
          </section>
        )}
      </main>

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.4; }
        }
      `}</style>
    </div>
  );
}
