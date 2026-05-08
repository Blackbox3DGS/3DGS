import { useState } from 'react';
import { Eye, Edit2, Check, X, Search, Calendar, Maximize2, Minimize2 } from 'lucide-react';
import { DayPicker, DateRange } from 'react-day-picker';
import { format, isWithinInterval, parseISO } from 'date-fns';
import { ko } from 'date-fns/locale';
import { AnalysisRecord } from './Dashboard';

interface AnalysisHistoryProps {
  records: AnalysisRecord[];
  selectedJobId: string | null;
  onSelectJob: (jobId: string) => void;
  onRenameVideo: (jobId: string, newTitle: string) => void;
}

export function AnalysisHistory({ records, selectedJobId, onSelectJob, onRenameVideo }: AnalysisHistoryProps) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [showAccidentDatePicker, setShowAccidentDatePicker] = useState(false);
  const [showUploadDatePicker, setShowUploadDatePicker] = useState(false);
  const [accidentDateRange, setAccidentDateRange] = useState<DateRange | undefined>();
  const [uploadDateRange, setUploadDateRange] = useState<DateRange | undefined>();
  const [isExpanded, setIsExpanded] = useState(false);

  const getStatusColor = (status: AnalysisRecord['status']) => {
    switch (status) {
      case 'COMPLETED':         return 'text-green-600 bg-green-50';
      case 'PROCESSING':
      case 'PRE_PROCESSING':    return 'text-blue-600 bg-blue-50';
      case 'WAITING_FOR_TARGET':return 'text-yellow-600 bg-yellow-50';
      case 'PENDING':           return 'text-gray-600 bg-gray-50';
      case 'FAILED':            return 'text-red-600 bg-red-50';
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

  // 필터링
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
      <div className="flex flex-col gap-4 mb-4">
        <div className="flex justify-between items-center">
          <h2 className="text-gray-900">나의 분석 기록</h2>
          <div className="flex items-center gap-3">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input
                type="text"
                placeholder="영상명 검색..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-10 pr-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500 text-sm"
              />
            </div>
            {!isExpanded && (
              <button
                onClick={() => setIsExpanded(true)}
                className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700 transition-colors"
              >
                <Maximize2 className="w-4 h-4" />
                전체 보기
              </button>
            )}
          </div>
        </div>

        {/* 날짜 필터 */}
        <div className="flex flex-wrap gap-3">
          <div className="relative">
            <button
              onClick={() => { setShowAccidentDatePicker(!showAccidentDatePicker); setShowUploadDatePicker(false); }}
              className={`flex items-center gap-2 px-4 py-2 border rounded-md text-sm transition-colors ${
                accidentDateRange?.from
                  ? 'border-indigo-500 bg-indigo-50 text-indigo-700'
                  : 'border-gray-300 bg-white text-gray-700 hover:bg-gray-50'
              }`}
            >
              <Calendar className="w-4 h-4" />
              <span>사고 날짜: {formatDateRange(accidentDateRange)}</span>
            </button>
            {showAccidentDatePicker && (
              <div className="absolute top-full mt-2 z-20 bg-white border border-gray-200 rounded-lg shadow-lg p-3">
                <div className="flex justify-between items-center mb-2">
                  <span className="text-sm text-gray-700">사고 날짜 범위 선택</span>
                  <button onClick={() => setAccidentDateRange(undefined)} className="text-xs text-gray-500 hover:text-red-600">초기화</button>
                </div>
                <DayPicker mode="range" selected={accidentDateRange} onSelect={setAccidentDateRange} locale={ko} className="rdp-custom" />
                <button onClick={() => setShowAccidentDatePicker(false)} className="w-full mt-2 px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700 text-sm">적용</button>
              </div>
            )}
          </div>

          <div className="relative">
            <button
              onClick={() => { setShowUploadDatePicker(!showUploadDatePicker); setShowAccidentDatePicker(false); }}
              className={`flex items-center gap-2 px-4 py-2 border rounded-md text-sm transition-colors ${
                uploadDateRange?.from
                  ? 'border-indigo-500 bg-indigo-50 text-indigo-700'
                  : 'border-gray-300 bg-white text-gray-700 hover:bg-gray-50'
              }`}
            >
              <Calendar className="w-4 h-4" />
              <span>업로드 날짜: {formatDateRange(uploadDateRange)}</span>
            </button>
            {showUploadDatePicker && (
              <div className="absolute top-full mt-2 z-20 bg-white border border-gray-200 rounded-lg shadow-lg p-3">
                <div className="flex justify-between items-center mb-2">
                  <span className="text-sm text-gray-700">업로드 날짜 범위 선택</span>
                  <button onClick={() => setUploadDateRange(undefined)} className="text-xs text-gray-500 hover:text-red-600">초기화</button>
                </div>
                <DayPicker mode="range" selected={uploadDateRange} onSelect={setUploadDateRange} locale={ko} className="rdp-custom" />
                <button onClick={() => setShowUploadDatePicker(false)} className="w-full mt-2 px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700 text-sm">적용</button>
              </div>
            )}
          </div>

          {(accidentDateRange?.from || uploadDateRange?.from || searchQuery) && (
            <button
              onClick={() => { setAccidentDateRange(undefined); setUploadDateRange(undefined); setSearchQuery(''); }}
              className="flex items-center gap-2 px-4 py-2 border border-red-300 bg-red-50 text-red-700 rounded-md text-sm hover:bg-red-100 transition-colors"
            >
              <X className="w-4 h-4" />
              모든 필터 초기화
            </button>
          )}
        </div>
      </div>

      {filteredRecords.length === 0 ? (
        <div className="text-center py-8 text-gray-500">
          {searchQuery || accidentDateRange?.from || uploadDateRange?.from
            ? '검색 결과가 없습니다.'
            : '분석 기록이 없습니다.'}
        </div>
      ) : (
        <div className="overflow-x-auto">
          <div className={isExpanded ? 'max-h-[70vh] overflow-y-auto' : 'max-h-[400px] overflow-y-auto'}>
            <table className="w-full">
              <thead className="sticky top-0 bg-white z-10 shadow-sm">
                <tr className="border-b border-gray-200">
                  <th className="text-left py-3 px-4 text-gray-700">영상명</th>
                  <th className="text-left py-3 px-4 text-gray-700">업로드 날짜</th>
                  <th className="text-left py-3 px-4 text-gray-700">사고 날짜</th>
                  <th className="text-left py-3 px-4 text-gray-700">상태</th>
                  <th className="text-left py-3 px-4 text-gray-700">작업</th>
                </tr>
              </thead>
              <tbody>
                {filteredRecords.map((record) => (
                  <tr
                    key={record.jobId}
                    className={`border-b border-gray-100 hover:bg-gray-50 transition-colors ${
                      selectedJobId === record.jobId ? 'bg-indigo-50' : ''
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
                            className="flex-1 px-2 py-1 border border-indigo-500 rounded focus:outline-none focus:ring-2 focus:ring-indigo-500"
                            autoFocus
                          />
                          <button onClick={() => saveEdit(record.jobId)} className="p-1 text-green-600 hover:bg-green-50 rounded" title="저장">
                            <Check className="w-4 h-4" />
                          </button>
                          <button onClick={cancelEdit} className="p-1 text-red-600 hover:bg-red-50 rounded" title="취소">
                            <X className="w-4 h-4" />
                          </button>
                        </div>
                      ) : (
                        <div className="flex items-center gap-2">
                          <span className="text-gray-900">{record.customTitle || '(제목 없음)'}</span>
                          <button
                            onClick={() => startEditing(record)}
                            className="p-1 text-gray-400 hover:text-indigo-600 hover:bg-indigo-50 rounded transition-colors"
                            title="이름 변경"
                          >
                            <Edit2 className="w-4 h-4" />
                          </button>
                        </div>
                      )}
                    </td>

                    {/* 업로드 날짜 */}
                    <td className="py-3 px-4 text-gray-600">
                      {record.createdAt ? record.createdAt.slice(0, 10) : '-'}
                    </td>

                    {/* 사고 날짜 */}
                    <td className="py-3 px-4 text-gray-900">
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
                            <div className="w-24 h-1.5 bg-gray-200 rounded-full overflow-hidden">
                              <div
                                className="h-full bg-blue-500 rounded-full transition-all"
                                style={{ width: `${record.progress}%` }}
                              />
                            </div>
                            <span className="text-xs text-gray-500">{record.progress}%</span>
                          </div>
                        )}
                      </div>
                    </td>

                    {/* 보기 버튼 */}
                    <td className="py-3 px-4">
                      <button
                        onClick={() => { onSelectJob(record.jobId); setIsExpanded(false); }}
                        className="flex items-center gap-2 px-4 py-1 bg-indigo-600 text-white rounded-md hover:bg-indigo-700 transition-colors disabled:bg-gray-300 disabled:cursor-not-allowed"
                        disabled={record.status !== 'COMPLETED'}
                      >
                        <Eye className="w-4 h-4" />
                        보기
                      </button>
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
      <div className="bg-white rounded-lg shadow-sm p-6 mb-8">
        {renderTableContent()}
      </div>

      {isExpanded && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-7xl h-[90vh] flex flex-col">
            <div className="flex justify-between items-center p-6 border-b border-gray-200">
              <h2 className="text-2xl text-gray-900">나의 분석 기록 - 전체 보기</h2>
              <button
                onClick={() => setIsExpanded(false)}
                className="flex items-center gap-2 px-4 py-2 bg-gray-600 text-white rounded-md hover:bg-gray-700 transition-colors"
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
    </>
  );
}
