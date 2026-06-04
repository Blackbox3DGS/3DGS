import { useState } from 'react';
import { Eye, Edit2, Check, X, Search, Calendar, Maximize2, Minimize2, Trash2 } from 'lucide-react';
import { DayPicker, DateRange } from 'react-day-picker';
import { format, isWithinInterval, parseISO } from 'date-fns';
import { ko } from 'date-fns/locale';
import { AnalysisRecord } from './Dashboard';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from './ui/alert-dialog';

interface AnalysisHistoryProps {
  records: AnalysisRecord[];
  selectedJobId: string | null;
  onSelectJob: (jobId: string) => void;
  onRenameVideo: (jobId: string, newTitle: string) => void;
  onDeleteRecord: (jobId: string) => void;
  // 검색어 변경을 부모(Dashboard)에 통지 → 부모에서 디바운스 후 서버에 keyword 전달
  onSearchChange?: (keyword: string) => void;
}

export function AnalysisHistory({ records, selectedJobId, onSelectJob, onRenameVideo, onDeleteRecord, onSearchChange }: AnalysisHistoryProps) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [showAccidentDatePicker, setShowAccidentDatePicker] = useState(false);
  const [showUploadDatePicker, setShowUploadDatePicker] = useState(false);
  const [accidentDateRange, setAccidentDateRange] = useState<DateRange | undefined>();
  const [uploadDateRange, setUploadDateRange] = useState<DateRange | undefined>();
  const [isExpanded, setIsExpanded] = useState(false);
  // 삭제 확인 다이얼로그용: 삭제 대기 중인 기록
  const [deletingRecord, setDeletingRecord] = useState<AnalysisRecord | null>(null);

  // 검색어 변경 헬퍼: 로컬 state 갱신 + 부모에 통지
  const updateSearchQuery = (value: string) => {
    setSearchQuery(value);
    onSearchChange?.(value);
  };

  const getStatusColor = (status: AnalysisRecord['status']) => {
    switch (status) {
      case 'COMPLETED':         return 'text-[#299283] bg-[#e6f5f2]';
      case 'PROCESSING':
      case 'PRE_PROCESSING':    return 'text-[#299283] bg-[#e6f5f2]';
      case 'WAITING_FOR_TARGET':return 'text-[#c4851c] bg-[#fdf4e3]';
      case 'PENDING':           return 'text-[#5a665e] bg-[#f7f9f8]';
      case 'FAILED':            return 'text-[#c44040] bg-[#fbe9e9]';
    }
  };

  const startEditing = (record: AnalysisRecord) => {
    setEditingId(record.jobId);
    setEditValue(record.customTitle ?? '');
  };

  const saveEdit = (jobId: string) => {
    if (editValue.trim()) {
      onRenameVideo(jobId, editValue.trim());
    }
    setEditingId(null);
  };

  const cancelEdit = () => {
    setEditingId(null);
    setEditValue('');
  };

  // 필터링 (서버사이드 keyword 검색이 적용되더라도 데모/날짜 필터를 위해 클라이언트 필터 유지)
  const filteredRecords = records.filter(record => {
    const matchesSearch = (record.customTitle ?? '').toLowerCase().includes(searchQuery.toLowerCase());

    let matchesAccidentDate = true;
    if (accidentDateRange?.from && record.incidentDate) {
      const d = parseISO(record.incidentDate);
      matchesAccidentDate = accidentDateRange.to
        ? isWithinInterval(d, { start: accidentDateRange.from, end: accidentDateRange.to })
        : format(d, 'yyyy-MM-dd') === format(accidentDateRange.from, 'yyyy-MM-dd');
    }

    let matchesUploadDate = true;
    if (uploadDateRange?.from && record.createdAt) {
      const d = parseISO(record.createdAt);
      matchesUploadDate = uploadDateRange.to
        ? isWithinInterval(d, { start: uploadDateRange.from, end: uploadDateRange.to })
        : format(d, 'yyyy-MM-dd') === format(uploadDateRange.from, 'yyyy-MM-dd');
    }

    return matchesSearch && matchesAccidentDate && matchesUploadDate;
  });

  const formatDateRange = (range: DateRange | undefined) => {
    if (!range?.from) return '날짜 선택';
    if (!range.to) return format(range.from, 'yyyy-MM-dd');
    return `${format(range.from, 'yyyy-MM-dd')} ~ ${format(range.to, 'yyyy-MM-dd')}`;
  };

  const renderTableContent = () => (
    <>
      <div className="flex flex-col gap-3 mb-4">
        <div className="flex flex-wrap justify-between items-center gap-3">
          <div className="relative flex-1 min-w-[200px] max-w-[320px]">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-[#b8c4be]" />
            <input
              type="text"
              placeholder="영상명 검색..."
              value={searchQuery}
              onChange={(e) => updateSearchQuery(e.target.value)}
              className="w-full pl-9 pr-3 py-2 bg-[#f7f9f8] border border-[#dae3dd] rounded-lg focus:outline-none focus:bg-white focus:border-[#299283] focus:ring-2 focus:ring-[#299283]/15 text-[13px] transition-all"
            />
          </div>
          {!isExpanded && (
            <button
              onClick={() => setIsExpanded(true)}
              className="flex items-center gap-1.5 px-3 py-2 text-[13px] text-[#5a665e] hover:text-[#20543d] hover:bg-[#eef2f0] rounded-md transition-colors"
            >
              <Maximize2 className="w-3.5 h-3.5" />
              전체 보기
            </button>
          )}
        </div>

        {/* 날짜 필터 */}
        <div className="flex flex-wrap gap-3">
          <div className="relative">
            <button
              onClick={() => { setShowAccidentDatePicker(!showAccidentDatePicker); setShowUploadDatePicker(false); }}
              className={`flex items-center gap-2 px-4 py-2 border rounded-md text-sm transition-colors ${
                accidentDateRange?.from
                  ? 'border-[#299283] bg-[#e6f5f2] text-[#1a5f54]'
                  : 'border-[#b8c4be] bg-white text-[#5a665e] hover:bg-[#f7f9f8]'
              }`}
            >
              <Calendar className="w-4 h-4" />
              <span>사고 날짜: {formatDateRange(accidentDateRange)}</span>
            </button>
            {showAccidentDatePicker && (
              <div className="absolute top-full mt-2 z-20 bg-white border border-[#dae3dd] rounded-lg shadow-lg p-3">
                <div className="flex justify-between items-center mb-2">
                  <span className="text-sm text-[#5a665e]">사고 날짜 범위 선택</span>
                  <button onClick={() => setAccidentDateRange(undefined)} className="text-xs text-[#8a9590] hover:text-[#c44040]">초기화</button>
                </div>
                <DayPicker mode="range" selected={accidentDateRange} onSelect={setAccidentDateRange} locale={ko} className="rdp-custom" />
                <button onClick={() => setShowAccidentDatePicker(false)} className="w-full mt-2 px-4 py-2 bg-[#299283] text-white rounded-md hover:bg-[#1a5f54] text-sm">적용</button>
              </div>
            )}
          </div>

          <div className="relative">
            <button
              onClick={() => { setShowUploadDatePicker(!showUploadDatePicker); setShowAccidentDatePicker(false); }}
              className={`flex items-center gap-2 px-4 py-2 border rounded-md text-sm transition-colors ${
                uploadDateRange?.from
                  ? 'border-[#299283] bg-[#e6f5f2] text-[#1a5f54]'
                  : 'border-[#b8c4be] bg-white text-[#5a665e] hover:bg-[#f7f9f8]'
              }`}
            >
              <Calendar className="w-4 h-4" />
              <span>업로드 날짜: {formatDateRange(uploadDateRange)}</span>
            </button>
            {showUploadDatePicker && (
              <div className="absolute top-full mt-2 z-20 bg-white border border-[#dae3dd] rounded-lg shadow-lg p-3">
                <div className="flex justify-between items-center mb-2">
                  <span className="text-sm text-[#5a665e]">업로드 날짜 범위 선택</span>
                  <button onClick={() => setUploadDateRange(undefined)} className="text-xs text-[#8a9590] hover:text-[#c44040]">초기화</button>
                </div>
                <DayPicker mode="range" selected={uploadDateRange} onSelect={setUploadDateRange} locale={ko} className="rdp-custom" />
                <button onClick={() => setShowUploadDatePicker(false)} className="w-full mt-2 px-4 py-2 bg-[#299283] text-white rounded-md hover:bg-[#1a5f54] text-sm">적용</button>
              </div>
            )}
          </div>

          {(accidentDateRange?.from || uploadDateRange?.from || searchQuery) && (
            <button
              onClick={() => { setAccidentDateRange(undefined); setUploadDateRange(undefined); updateSearchQuery(''); }}
              className="flex items-center gap-2 px-4 py-2 border border-[#e8a7a7] bg-[#fbe9e9] text-[#a83434] rounded-md text-sm hover:bg-[#f7d6d6] transition-colors"
            >
              <X className="w-4 h-4" />
              모든 필터 초기화
            </button>
          )}
        </div>
      </div>

      {filteredRecords.length === 0 ? (
        <div className="text-center py-8 text-[#8a9590]">
          {searchQuery || accidentDateRange?.from || uploadDateRange?.from
            ? '검색 결과가 없습니다.'
            : '분석 기록이 없습니다.'}
        </div>
      ) : (
        <div className="overflow-x-auto">
          <div className={isExpanded ? 'max-h-[70vh] overflow-y-auto' : 'max-h-[400px] overflow-y-auto'}>
            <table className="w-full">
              <thead className="sticky top-0 bg-white z-10 shadow-sm">
                <tr className="border-b border-[#dae3dd]">
                  <th className="text-left py-3 px-4 text-[#5a665e]">영상명</th>
                  <th className="text-left py-3 px-4 text-[#5a665e]">업로드 날짜</th>
                  <th className="text-left py-3 px-4 text-[#5a665e]">사고 날짜</th>
                  <th className="text-left py-3 px-4 text-[#5a665e]">상태</th>
                  <th className="text-left py-3 px-4 text-[#5a665e]">작업</th>
                </tr>
              </thead>
              <tbody>
                {filteredRecords.map((record) => (
                  <tr
                    key={record.jobId}
                    className={`border-b border-[#eef2f0] hover:bg-[#f7f9f8] transition-colors ${
                      selectedJobId === record.jobId ? 'bg-[#e6f5f2]' : ''
                    }`}
                  >
                    {/* 영상명 (편집 가능) */}
                    <td className="py-3 px-4">
                      {editingId === record.jobId ? (
                        <div className="flex items-center gap-2">
                          <input
                            type="text"
                            value={editValue}
                            onChange={(e) => setEditValue(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter') saveEdit(record.jobId);
                              if (e.key === 'Escape') cancelEdit();
                            }}
                            className="flex-1 px-2 py-1 border border-[#299283] rounded focus:outline-none focus:ring-2 focus:ring-[#299283]"
                            autoFocus
                          />
                          <button onClick={() => saveEdit(record.jobId)} className="p-1 text-[#299283] hover:bg-[#e6f5f2] rounded" title="저장">
                            <Check className="w-4 h-4" />
                          </button>
                          <button onClick={cancelEdit} className="p-1 text-[#c44040] hover:bg-[#fbe9e9] rounded" title="취소">
                            <X className="w-4 h-4" />
                          </button>
                        </div>
                      ) : (
                        <div className="flex items-center gap-2">
                          <span className="text-[#20543d]">{record.customTitle || '(제목 없음)'}</span>
                          <button
                            onClick={() => startEditing(record)}
                            className="p-1 text-[#b8c4be] hover:text-[#299283] hover:bg-[#e6f5f2] rounded transition-colors"
                            title="이름 변경"
                          >
                            <Edit2 className="w-4 h-4" />
                          </button>
                        </div>
                      )}
                    </td>

                    {/* 업로드 날짜 */}
                    <td className="py-3 px-4 text-[#5a665e]">
                      {record.createdAt ? record.createdAt.slice(0, 10) : '-'}
                    </td>

                    {/* 사고 날짜 */}
                    <td className="py-3 px-4 text-[#20543d]">
                      {record.incidentDate ? record.incidentDate.slice(0, 10) : '-'}
                    </td>

                    {/* 상태 */}
                    <td className="py-3 px-4">
                      <div className="flex flex-col gap-1">
                        <span className={`px-3 py-1 rounded-full text-sm w-fit ${getStatusColor(record.status)}`}>
                          {record.statusDescription || record.status}
                        </span>
                        {/* 진행 중일 때 진행률 표시 */}
                        {(record.status === 'PROCESSING' || record.status === 'PRE_PROCESSING') && (
                          <div className="flex items-center gap-2">
                            <div className="w-24 h-1.5 bg-[#dae3dd] rounded-full overflow-hidden">
                              <div
                                className="h-full bg-[#e6f5f2]0 rounded-full transition-all"
                                style={{ width: `${record.progress}%` }}
                              />
                            </div>
                            <span className="text-xs text-[#8a9590]">{record.progress}%</span>
                          </div>
                        )}
                      </div>
                    </td>

                    {/* 보기 / 삭제 버튼 */}
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => { onSelectJob(record.jobId); setIsExpanded(false); }}
                          className="flex items-center gap-2 px-4 py-1 bg-[#299283] text-white rounded-md hover:bg-[#1a5f54] transition-colors disabled:bg-[#b8c4be] disabled:cursor-not-allowed"
                          disabled={record.status !== 'COMPLETED'}
                        >
                          <Eye className="w-4 h-4" />
                          보기
                        </button>
                        <button
                          onClick={() => setDeletingRecord(record)}
                          className="p-1.5 text-[#b8c4be] hover:text-[#c44040] hover:bg-[#fbe9e9] rounded transition-colors"
                          title="삭제"
                          aria-label="분석 기록 삭제"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </>
  );

  return (
    <>
      <div
        className="bg-white rounded-xl p-5"
        style={{ border: '1px solid #dae3dd' }}
      >
        {renderTableContent()}
      </div>

      {isExpanded && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-7xl h-[90vh] flex flex-col">
            <div className="flex justify-between items-center p-6 border-b border-[#dae3dd]">
              <h2 className="text-2xl text-[#20543d]">나의 분석 기록 - 전체 보기</h2>
              <button
                onClick={() => setIsExpanded(false)}
                className="flex items-center gap-2 px-4 py-2 bg-[#5a665e] text-white rounded-md hover:bg-[#2c3530] transition-colors"
              >
                <Minimize2 className="w-4 h-4" />
                닫기
              </button>
            </div>
            <div className="flex-1 overflow-hidden p-6">
              {renderTableContent()}
            </div>
          </div>
        </div>
      )}

      {/* 삭제 확인 다이얼로그 */}
      <AlertDialog
        open={deletingRecord !== null}
        onOpenChange={(open) => { if (!open) setDeletingRecord(null); }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>분석 기록을 삭제하시겠습니까?</AlertDialogTitle>
            <AlertDialogDescription>
              <span className="font-medium text-[#20543d]">
                "{deletingRecord?.customTitle || '(제목 없음)'}"
              </span>
              {' '}기록이 영구적으로 삭제됩니다. 이 작업은 되돌릴 수 없습니다.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>취소</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                if (deletingRecord) onDeleteRecord(deletingRecord.jobId);
                setDeletingRecord(null);
              }}
              className="bg-[#c44040] hover:bg-[#a83434] text-white"
            >
              삭제
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
