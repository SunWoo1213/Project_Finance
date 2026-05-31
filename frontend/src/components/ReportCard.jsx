import { CheckCircle, TrendingUp, TrendingDown, Clock, SearchX } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

export default function ReportCard({ reportData, isReportLoading }) {
  if (isReportLoading) {
    return (
      <div className="bg-slate-800/80 backdrop-blur-md rounded-3xl p-6 border border-slate-700/50 shadow-xl flex flex-col gap-6 min-h-[300px] justify-center items-center">
        <div className="animate-pulse flex flex-col items-center gap-4">
          <Clock size={32} className="text-slate-500 animate-spin" />
          <p className="text-slate-400 font-medium">AI가 실시간 리포트를 분석 중입니다...</p>
        </div>
      </div>
    );
  }

  if (!reportData) {
    return (
      <div className="bg-slate-800/80 backdrop-blur-md rounded-3xl p-6 border border-slate-700/50 shadow-xl flex flex-col gap-6 min-h-[200px] justify-center items-center text-center">
        <div className="w-16 h-16 bg-slate-700/50 rounded-full flex items-center justify-center mb-2">
          <SearchX size={28} className="text-slate-400" />
        </div>
        <p className="text-slate-300 font-medium">아직 이 종목의 AI 리포트가 생성되지 않았습니다.</p>
        <p className="text-sm text-slate-500">잠시 후 다시 시도하거나 다른 종목을 선택해 주세요.</p>
      </div>
    );
  }

  const { bull_summary, bear_summary, final_content, metadata = {}, unavailable } = reportData;
  const readiness = metadata.readiness || {};
  const qualityStatus = metadata.quality_status || (metadata.is_pass ? 'pass' : '');
  const missingFacts = Array.isArray(metadata.missing_required_facts) ? metadata.missing_required_facts : [];
  const sourceStatus = metadata.source_status || {};
  const dataAsOf = metadata.data_as_of ? new Date(metadata.data_as_of) : null;
  const formattedDataAsOf = dataAsOf && !Number.isNaN(dataAsOf.getTime())
    ? dataAsOf.toLocaleString('ko-KR', { timeZone: 'Asia/Seoul', hour12: false })
    : '';
  const isLimited = readiness.status === 'limited' || missingFacts.length > 0;
  const isBlocked = unavailable || readiness.status === 'blocked' || qualityStatus === 'blocked';

  if (isBlocked) {
    return (
      <div className="bg-slate-800/80 backdrop-blur-md rounded-3xl p-6 border border-amber-500/30 shadow-xl flex flex-col gap-4 min-h-[220px] justify-center">
        <div className="flex items-center gap-2 text-amber-300 font-bold">
          <SearchX size={22} />
          리포트 생성 보류
        </div>
        <p className="text-sm leading-6 text-slate-300">
          필수 데이터가 부족해 AI 리포트를 생성하지 않았습니다. 데이터가 갱신되면 다시 시도할 수 있습니다.
        </p>
        {readiness.blocking_reasons?.length > 0 && (
          <ul className="list-disc space-y-1 pl-5 text-sm text-slate-400">
            {readiness.blocking_reasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        )}
      </div>
    );
  }

  return (
    <div className="bg-slate-800/80 backdrop-blur-md rounded-3xl p-6 border border-slate-700/50 shadow-xl flex flex-col gap-6">
      <div className="flex justify-between items-center">
        <h3 className="text-xl font-bold flex flex-col">
          AI 분석 리포트
          <span className="text-sm font-normal text-slate-400 mt-1">
            {formattedDataAsOf ? `데이터 기준 ${formattedDataAsOf}` : '최신 실시간 데이터 생성됨'}
          </span>
        </h3>
        <span className="px-4 py-1.5 bg-emerald-500/20 text-emerald-400 rounded-full font-bold text-sm border border-emerald-500/30 flex items-center gap-1.5 shadow-sm">
          <CheckCircle size={16} /> AI 분석 완료
        </span>
      </div>

      {(isLimited || metadata.risk_summary || sourceStatus.latest_context) && (
        <div className="rounded-2xl border border-slate-700/70 bg-slate-900/40 p-4 text-sm text-slate-300">
          <div className="mb-2 font-semibold text-slate-200">품질 및 출처 메타데이터</div>
          <div className="flex flex-wrap gap-2 text-xs text-slate-400">
            {readiness.status && <span>준비도: {readiness.status}</span>}
            {sourceStatus.latest_context && <span>최신 컨텍스트: {sourceStatus.latest_context}</span>}
            {metadata.format_check_pass !== undefined && <span>형식 검증: {metadata.format_check_pass ? '통과' : '미통과'}</span>}
            {metadata.fact_check_pass !== undefined && <span>숫자 검증: {metadata.fact_check_pass ? '통과' : '미통과'}</span>}
            {metadata.qualitative_check_pass !== undefined && <span>정성 검증: {metadata.qualitative_check_pass ? '통과' : '미통과'}</span>}
          </div>
          {missingFacts.length > 0 && (
            <p className="mt-2 text-xs leading-5 text-amber-200">누락 팩트: {missingFacts.join(', ')}</p>
          )}
          {metadata.risk_summary && (
            <p className="mt-2 line-clamp-2 text-xs leading-5 text-slate-400">{metadata.risk_summary}</p>
          )}
        </div>
      )}

      <div className="grid grid-cols-2 gap-4">
        <div className="bg-emerald-900/10 rounded-2xl p-4 border border-emerald-500/20 hover:bg-emerald-900/20 transition-colors">
          <h4 className="text-emerald-400 font-bold mb-2 flex items-center gap-2">
            <TrendingUp size={18} /> 강세장 (Bull) 의견
          </h4>
          <p className="text-sm text-slate-300 leading-relaxed whitespace-pre-line">
            {bull_summary}
          </p>
        </div>
        <div className="bg-blue-900/10 rounded-2xl p-4 border border-blue-500/20 hover:bg-blue-900/20 transition-colors">
          <h4 className="text-blue-400 font-bold mb-2 flex items-center gap-2">
            <TrendingDown size={18} /> 약세장 (Bear) 의견
          </h4>
          <p className="text-sm text-slate-300 leading-relaxed whitespace-pre-line">
            {bear_summary}
          </p>
        </div>
      </div>

      <div className="bg-slate-900/50 rounded-2xl p-6 border border-slate-700/50 shadow-inner mt-2">
        <h4 className="font-bold text-slate-200 mb-4 border-b border-slate-700 pb-2">최종 종합 분석</h4>
        <div className="prose prose-invert prose-slate prose-sm max-w-none 
                        prose-headings:text-slate-100 prose-headings:font-bold 
                        prose-a:text-emerald-400 prose-strong:text-slate-200 prose-ul:pl-4">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {final_content || '최종 리포트 본문이 저장되지 않았습니다.'}
          </ReactMarkdown>
        </div>
      </div>
    </div>
  );
}
