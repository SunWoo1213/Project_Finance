import { ThumbsUp, TrendingUp, TrendingDown, Clock, SearchX } from 'lucide-react';
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

  const { bull_summary, bear_summary, final_content } = reportData;

  return (
    <div className="bg-slate-800/80 backdrop-blur-md rounded-3xl p-6 border border-slate-700/50 shadow-xl flex flex-col gap-6">
      <div className="flex justify-between items-center">
        <h3 className="text-xl font-bold flex flex-col">
          AI 분석 리포트
          <span className="text-sm font-normal text-slate-400 mt-1">최신 실시간 데이터 생성됨</span>
        </h3>
        <span className="px-4 py-1.5 bg-emerald-500/20 text-emerald-400 rounded-full font-bold text-sm border border-emerald-500/30 flex items-center gap-1.5 shadow-sm">
          <ThumbsUp size={16} /> Analyst Recommends
        </span>
      </div>

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
            {final_content}
          </ReactMarkdown>
        </div>
      </div>
    </div>
  );
}
