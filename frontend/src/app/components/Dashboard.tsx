import { useState, useEffect, useRef } from 'react';
import { Upload, LogOut } from 'lucide-react';
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

export function Dashboard() {
  const { user, logout } = useAuth();

  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [selectedRecord, setSelectedRecord] = useState<AnalysisRecord | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [records, setRecords] = useState<AnalysisRecord[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isUploading, setIsUploading] = useState(false);

  const isDemo = user?.userId === 'demo';
  const pollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // 분석 기록 목록 조회 (데모면 더미 데이터)
  const fetchRecords = async () => {
    if (isDemo) {
      setRecords(DEMO_RECORDS);
      return DEMO_RECORDS;
    }
    try {
      const res = await apiClient.get<AnalysisRecord[]>('/api/v1/reconstruction');
      const data = Array.isArray(res.data) ? res.data : [];
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
      const updated = await fetchRecords();
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
  }, []);

  // 폴링 갱신 시 selectedRecord도 동기화
  useEffect(() => {
    if (!records.length) return;
    schedulePolling(records);
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
      const data = await fetchRecords();
      if (data) schedulePolling(data);
    } catch (err) {
      console.error('업로드 실패:', err);
      toast.error('파일 업로드에 실패했습니다.');
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex justify-between items-center">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-indigo-600 rounded-lg">
              <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z" />
              </svg>
            </div>
            <h1 className="text-gray-900">3D 사고 복원 시스템</h1>
          </div>
          <div className="flex items-center gap-4">
            {user && (
              <span className="text-sm text-gray-600">
                {user.name?.trim() || generateNickname(user.userId || user.email || 'user')}님
              </span>
            )}
            <button
              onClick={logout}
              className="flex items-center gap-2 px-4 py-2 text-gray-700 hover:text-gray-900 hover:bg-gray-100 rounded-md transition-colors"
            >
              <LogOut className="w-4 h-4" />
              로그아웃
            </button>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Upload Section */}
        <div className="bg-white rounded-lg shadow-sm p-6 mb-8">
          <h2 className="text-gray-900 mb-4">새 영상 업로드</h2>

          <div
            onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={handleDrop}
            className={`border-2 border-dashed rounded-lg p-12 text-center transition-colors ${
              isDragging ? 'border-indigo-500 bg-indigo-50' : 'border-gray-300 bg-gray-50'
            }`}
          >
            {isUploading ? (
              <div className="flex flex-col items-center gap-4">
                <div className="w-10 h-10 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin" />
                <p className="text-gray-600">업로드 중...</p>
              </div>
            ) : (
              <>
                <Upload className="w-12 h-12 mx-auto mb-4 text-gray-400" />
                <p className="text-gray-700 mb-2">블랙박스 영상을 업로드하세요</p>
                <p className="text-sm text-gray-500 mb-4">
                  파일을 드래그 앤 드롭하거나 클릭하여 선택 (최대 2GB)
                </p>
                <label className="px-6 py-2 bg-white border border-gray-300 rounded-md hover:bg-gray-50 cursor-pointer transition-colors">
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

        {/* Analysis History */}
        {isLoading ? (
          <div className="bg-white rounded-lg shadow-sm p-6 mb-8 flex items-center justify-center h-40">
            <div className="flex flex-col items-center gap-3 text-gray-500">
              <div className="w-8 h-8 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin" />
              <span className="text-sm">분석 기록을 불러오는 중...</span>
            </div>
          </div>
        ) : (
          <AnalysisHistory
            records={records}
            selectedJobId={selectedJobId}
            onSelectJob={setSelectedJobId}
            onRenameVideo={handleRenameVideo}
          />
        )}

        {/* 3D Viewer: COMPLETED 상태인 것만 표시 */}
        {selectedRecord && selectedRecord.status === 'COMPLETED' && (
          <Viewer3D
            jobId={selectedRecord.jobId}
            resultUrl={selectedRecord.resultUrl}
            trajectoryUrl={selectedRecord.trajectoryUrl}
          />
        )}
      </div>
    </div>
  );
}
