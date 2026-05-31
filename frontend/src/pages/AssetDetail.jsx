import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import axios from "axios";
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { CalendarDays, ExternalLink, Flag, Heart, Newspaper, RefreshCw, Send, Star } from "lucide-react";

import ReportCard from "../components/ReportCard";
import useAuthStore from "../store/authStore";
import useFavoriteStore from "../store/favoriteStore";
import { getUiCategory } from "../utils/assetCategories";
import { formatChangeBadge, formatMarketCap, formatPrice, formatTicker } from "../utils/formatters";
import { resolveAssetName } from "../utils/constants";

const REPORT_REASONS = ["스팸/홍보", "욕설/비방", "부적절한 정보"];

export default function AssetDetail() {
  const { ticker } = useParams();
  const assetTicker = String(ticker || "").trim();
  const navigate = useNavigate();
  const { token, user } = useAuthStore();
  const { isFavorite, toggleFavorite } = useFavoriteStore();
  const authToken = token || localStorage.getItem("token");

  const [marketInfo, setMarketInfo] = useState(null);
  const [report, setReport] = useState(null);
  const [comments, setComments] = useState([]);
  const [newComment, setNewComment] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [selectedPeriod, setSelectedPeriod] = useState("1y");
  const [chartData, setChartData] = useState([]);
  const [historyMeta, setHistoryMeta] = useState({ seriesType: "price", unit: "USD" });
  const [assetGroup, setAssetGroup] = useState("us_top10");
  const [latestContext, setLatestContext] = useState(null);
  const [isLatestContextLoading, setIsLatestContextLoading] = useState(false);
  const [editingCommentId, setEditingCommentId] = useState(null);
  const [editingContent, setEditingContent] = useState("");
  const [commentActionMessage, setCommentActionMessage] = useState("");
  const [activeReportCommentId, setActiveReportCommentId] = useState(null);
  const [reportingCommentId, setReportingCommentId] = useState(null);
  const reportRequestCacheRef = useRef(new Set());

  const authHeaders = useMemo(() => (authToken ? { Authorization: `Bearer ${authToken}` } : {}), [authToken]);

  const fetchComments = useCallback(async () => {
    try {
      const res = await axios.get(`http://localhost:8000/api/community/${encodeURIComponent(assetTicker)}/comments`);
      setComments(res.data);
    } catch (error) {
      console.error("Failed to fetch comments:", error);
    }
  }, [assetTicker]);

  const fetchLatestContext = useCallback(
    async (forceRefresh = false) => {
      if (!assetTicker) return;

      setIsLatestContextLoading(true);
      try {
        const res = await axios.get(
          `http://localhost:8000/api/market/latest-context/${encodeURIComponent(assetTicker)}${
            forceRefresh ? "?force_refresh=true" : ""
          }`
        );
        setLatestContext(res.data);
      } catch (error) {
        console.error("Failed to load latest context:", error);
        setLatestContext(null);
      } finally {
        setIsLatestContextLoading(false);
      }
    },
    [assetTicker]
  );

  useEffect(() => {
    fetchLatestContext(false);
  }, [fetchLatestContext]);

  useEffect(() => {
    const fetchHistory = async () => {
      if (!assetTicker) {
        setChartData([]);
        return;
      }

      try {
        const res = await axios.get(
          `http://localhost:8000/api/market/history/${encodeURIComponent(assetTicker)}?period=${selectedPeriod}`
        );
        const payload = res.data;

        if (Array.isArray(payload)) {
          setChartData(payload);
          setHistoryMeta({ seriesType: "price", unit: "USD" });
          return;
        }

        const points = Array.isArray(payload?.points)
          ? payload.points
          : Array.isArray(payload?.legacy)
          ? payload.legacy
          : [];

        setChartData(points);
        setHistoryMeta({
          seriesType: payload?.series_type || "price",
          unit: payload?.unit || "USD",
        });
      } catch (error) {
        console.error("Failed to load history:", error);
        setChartData([]);
      }
    };

    fetchHistory();
  }, [assetTicker, selectedPeriod]);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const priceRes = await axios.get("http://localhost:8000/api/market/prices");
        let matched = null;

        for (const [groupName, group] of Object.entries(priceRes.data)) {
          for (const info of Object.values(group)) {
            if (info.symbol === assetTicker) {
              matched = info;
              setAssetGroup(groupName);
              break;
            }
          }
          if (matched) break;
        }

        setMarketInfo(matched);

        if (authToken) {
          const requestKey = `${assetTicker}:${authToken.slice(0, 12)}`;
          if (!reportRequestCacheRef.current.has(requestKey)) {
            reportRequestCacheRef.current.add(requestKey);
            try {
              const reportRes = await axios.get(`http://localhost:8000/api/reports/${encodeURIComponent(assetTicker)}`, {
                headers: authHeaders,
              });
              setReport(reportRes.data);
            } catch (error) {
              if (error?.response?.status === 404) {
                try {
                  await axios.post(
                    `http://localhost:8000/api/ai/generate/${encodeURIComponent(assetTicker)}`,
                    {},
                    { headers: authHeaders }
                  );
                  const retryRes = await axios.get(`http://localhost:8000/api/reports/${encodeURIComponent(assetTicker)}`, {
                    headers: authHeaders,
                  });
                  setReport(retryRes.data);
                } catch (generationError) {
                  const detail = generationError?.response?.data?.detail;
                  if (generationError?.response?.status === 422 && detail?.metadata) {
                    setReport({
                      unavailable: true,
                      bull_summary: "",
                      bear_summary: "",
                      final_content: "",
                      metadata: detail.metadata,
                    });
                  } else {
                    setReport(null);
                    console.error("Failed to generate AI report:", generationError);
                  }
                }
              } else {
                setReport(null);
                console.error("Failed to load AI report:", error);
              }
            }
          }
        } else {
          setReport(null);
        }

        await fetchComments();
      } catch (error) {
        console.error("Failed to load detail data:", error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchData();
  }, [assetTicker, authHeaders, authToken, fetchComments]);

  const handleLike = async (commentId) => {
    if (!authToken) return;

    try {
      await axios.post(`http://localhost:8000/api/community/comments/${commentId}/like`, {}, { headers: authHeaders });
      await fetchComments();
    } catch (error) {
      console.error("Failed to toggle like:", error);
    }
  };

  const handlePostComment = async (e) => {
    e.preventDefault();
    if (!authToken || !newComment.trim()) return;

    try {
      await axios.post(
        `http://localhost:8000/api/community/${encodeURIComponent(assetTicker)}/comments`,
        { content: newComment.trim() },
        { headers: authHeaders }
      );
      setNewComment("");
      setCommentActionMessage("");
      await fetchComments();
    } catch (error) {
      setCommentActionMessage(error?.response?.data?.detail || "댓글 작성에 실패했습니다.");
      console.error("Failed to post comment:", error);
    }
  };

  const startEditComment = (comment) => {
    setActiveReportCommentId(null);
    setEditingCommentId(comment.id);
    setEditingContent(comment.content);
  };

  const cancelEditComment = () => {
    setEditingCommentId(null);
    setEditingContent("");
  };

  const saveEditComment = async (commentId) => {
    if (!authToken || !editingContent.trim()) return;

    try {
      await axios.put(
        `http://localhost:8000/api/community/${encodeURIComponent(assetTicker)}/comments/${commentId}`,
        { content: editingContent.trim() },
        { headers: authHeaders }
      );
      cancelEditComment();
      setCommentActionMessage("");
      await fetchComments();
    } catch (error) {
      setCommentActionMessage(error?.response?.data?.detail || "댓글 수정에 실패했습니다.");
      console.error("Failed to update comment:", error);
    }
  };

  const deleteComment = async (commentId) => {
    if (!authToken) return;
    if (!window.confirm("삭제하시겠습니까?")) return;

    try {
      await axios.delete(
        `http://localhost:8000/api/community/${encodeURIComponent(assetTicker)}/comments/${commentId}`,
        { headers: authHeaders }
      );
      setCommentActionMessage("");
      await fetchComments();
    } catch (error) {
      setCommentActionMessage(error?.response?.data?.detail || "댓글 삭제에 실패했습니다.");
      console.error("Failed to delete comment:", error);
    }
  };

  const openReportReasons = (commentId) => {
    if (!authToken) return;
    setCommentActionMessage("");
    setActiveReportCommentId((currentId) => (currentId === commentId ? null : commentId));
  };

  const reportComment = async (commentId) => {
    if (!authToken) return;

    try {
      setReportingCommentId(commentId);
      await axios.post(
        `http://localhost:8000/api/community/comments/${commentId}/report`,
        {},
        { headers: authHeaders }
      );
      setActiveReportCommentId(null);
      setCommentActionMessage("신고가 접수되었습니다.");
      await fetchComments();
    } catch (error) {
      setCommentActionMessage(error?.response?.data?.detail || "댓글 신고에 실패했습니다.");
      console.error("Failed to report comment:", error);
    } finally {
      setReportingCommentId(null);
    }
  };

  if (isLoading) {
    return <div className="py-20 text-center">데이터를 불러오는 중입니다...</div>;
  }

  if (!marketInfo) {
    return <div className="py-20 text-center">해당 티커의 시세 데이터가 없습니다.</div>;
  }

  const changeValue = marketInfo.changePercent ?? marketInfo.change_pct ?? 0;
  const badge = formatChangeBadge(changeValue);
  const strokeColor = changeValue >= 0 ? "#ef4444" : "#3b82f6";
  const formattedTicker = formatTicker(assetTicker);
  const displayName = resolveAssetName(assetTicker, formattedTicker);
  const favorited = isFavorite(assetTicker);
  const hasChartData = Array.isArray(chartData) && chartData.length > 0;

  const uiCategory = getUiCategory(assetGroup, assetTicker);

  const isBond = uiCategory.includes("BOND");
  const marketCap = Number(marketInfo.marketCap ?? 0);
  const isMacro =
    marketCap <= 0 ||
    uiCategory === "US_BOND" ||
    uiCategory === "KR_BOND" ||
    uiCategory === "COMMODITY" ||
    uiCategory === "FX";

  const periods = [
    { label: "1일", value: "1d" },
    { label: "1개월", value: "1mo" },
    { label: "1년", value: "1y" },
    { label: "5년", value: "5y" },
  ];

  const formatCommentCreatedAt = (value) =>
    new Date(value).toLocaleString("ko-KR", {
      timeZone: "Asia/Seoul",
      hour12: false,
    });

  const formatContextTime = (value) => {
    if (!value) return "";
    const numeric = Number(value);
    const date = Number.isFinite(numeric) && numeric > 100000 ? new Date(numeric * 1000) : new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    return date.toLocaleString("ko-KR", {
      timeZone: "Asia/Seoul",
      hour12: false,
    });
  };

  const latestNews = Array.isArray(latestContext?.news) ? latestContext.news : [];
  const latestEvents = Array.isArray(latestContext?.events) ? latestContext.events : [];
  const latestFetchedAt = formatContextTime(latestContext?.fetched_at);
  const latestSourceStatus = latestContext?.source_status === "fresh" ? "갱신됨" : latestContext?.source_status;

  return (
    <div className="mx-auto flex max-w-screen-md flex-col gap-12 px-4 py-8">
      <section>
        <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <h1 className="mb-2 bg-gradient-to-r from-emerald-400 to-cyan-400 bg-clip-text text-3xl font-bold text-transparent">
              {displayName}
              <span className="ml-2 align-middle text-lg font-medium text-slate-300">({formattedTicker})</span>
            </h1>
            <div className="flex flex-wrap items-end gap-4">
              <span className="text-5xl font-extrabold text-slate-100">{formatPrice(marketInfo.price, uiCategory)}</span>
              <span className={`pb-1 text-2xl font-bold ${badge.className}`}>{badge.text}</span>
            </div>

            {isMacro ? (
              <div className="mt-2 inline-flex rounded-full bg-slate-700 px-3 py-1 text-xs text-slate-300">거시 지표</div>
            ) : (
              <div className="mt-2 text-sm text-slate-400">시가총액 {formatMarketCap(marketCap, uiCategory)}</div>
            )}
          </div>

          <button
            type="button"
            aria-pressed={favorited}
            onClick={() =>
              toggleFavorite({
                symbol: assetTicker,
                name: displayName,
                categoryKey: assetGroup,
              })
            }
            className={`inline-flex items-center justify-center gap-2 rounded-xl border px-4 py-2 text-sm font-semibold transition-colors ${
              favorited
                ? "border-amber-300/60 bg-amber-300/10 text-amber-300"
                : "border-slate-600 text-slate-300 hover:border-amber-300/60 hover:text-amber-300"
            }`}
          >
            <Star size={18} fill={favorited ? "currentColor" : "none"} />
            {favorited ? "즐겨찾기 해제" : "즐겨찾기"}
          </button>
        </div>

        {!isBond && (
          <div className="relative flex h-[400px] flex-col rounded-3xl border border-slate-700 bg-slate-800/50 p-6 shadow-inner">
            <div className="relative z-10 mb-4 flex justify-end gap-2">
              {periods.map((p) => (
                <button
                  key={p.value}
                  onClick={() => setSelectedPeriod(p.value)}
                  className={`rounded-full px-4 py-1.5 text-sm font-bold transition-colors ${
                    selectedPeriod === p.value
                      ? "scale-105 transform bg-emerald-500 text-slate-900 shadow-md"
                      : "bg-slate-700 text-slate-300 hover:bg-slate-600"
                  }`}
                >
                  {p.label}
                </button>
              ))}
            </div>

            <div className="h-[280px] w-full">
              {hasChartData ? (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData} margin={{ top: 20, right: 30, left: 10, bottom: 5 }}>
                    <XAxis dataKey="date" stroke="#94a3b8" tick={{ fontSize: 12 }} minTickGap={30} />
                    <YAxis
                      domain={["dataMin", "dataMax"]}
                      orientation="right"
                      axisLine={false}
                      tickLine={false}
                      stroke="#94a3b8"
                      tickFormatter={(value) => formatPrice(value, uiCategory)}
                      tick={{ fontSize: 12 }}
                    />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: "#1e293b",
                        border: "none",
                        borderRadius: "8px",
                        color: "#f8fafc",
                      }}
                      itemStyle={{ color: strokeColor }}
                      formatter={(value) => [formatPrice(value, uiCategory), historyMeta.seriesType === "yield" ? "Yield" : "Price"]}
                    />
                    <Line type="monotone" dataKey="value" stroke={strokeColor} strokeWidth={3} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex h-full w-full items-center justify-center text-slate-400">차트 데이터가 없습니다.</div>
              )}
            </div>
          </div>
        )}

        {isBond && (
          <div className="mt-2 rounded-2xl border border-slate-700/70 bg-slate-800/40 px-4 py-3 text-sm text-slate-400">
            채권 자산은 AI 매크로 분석 리포트를 중심으로 제공합니다.
          </div>
        )}
      </section>

      <section>
        <div className="mb-4 flex items-center justify-between gap-3 px-2">
          <h2 className="flex items-center gap-2 text-2xl font-bold tracking-tight">
            <Newspaper size={22} className="text-emerald-400" />
            최신 뉴스와 발표
          </h2>
          <button
            type="button"
            onClick={() => fetchLatestContext(true)}
            disabled={isLatestContextLoading}
            className="inline-flex items-center gap-2 rounded-xl bg-slate-800 px-3 py-2 text-sm font-semibold text-slate-200 transition-colors hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <RefreshCw size={16} className={isLatestContextLoading ? "animate-spin" : ""} />
            새로고침
          </button>
        </div>

        <div className="rounded-3xl border border-slate-700 bg-slate-800/70 p-5 shadow-md">
          <div className="mb-4 flex flex-wrap items-center gap-2 text-xs text-slate-400">
            <span>{latestFetchedAt ? `기준 ${latestFetchedAt}` : "최신 컨텍스트 대기 중"}</span>
            {latestSourceStatus && <span>· {latestSourceStatus}</span>}
          </div>

          {isLatestContextLoading && !latestContext ? (
            <div className="py-8 text-center text-slate-400">최신 뉴스를 확인하는 중입니다...</div>
          ) : latestNews.length === 0 && latestEvents.length === 0 ? (
            <div className="py-8 text-center text-slate-400">확인된 최신 뉴스나 발표 일정이 없습니다.</div>
          ) : (
            <div className="grid gap-5 md:grid-cols-[1.5fr_1fr]">
              <div className="space-y-3">
                {latestNews.slice(0, 5).map((item, index) => (
                  <a
                    key={`${item.link || item.title}-${index}`}
                    href={item.link || "#"}
                    target="_blank"
                    rel="noreferrer"
                    className="block rounded-2xl border border-slate-700/70 bg-slate-900/40 p-4 transition-colors hover:border-emerald-400/60 hover:bg-slate-900/70"
                  >
                    <div className="mb-2 flex items-start justify-between gap-3">
                      <h3 className="text-sm font-semibold leading-6 text-slate-100">{item.title}</h3>
                      {item.link && <ExternalLink size={15} className="mt-1 shrink-0 text-slate-500" />}
                    </div>
                    {item.summary && <p className="mb-2 line-clamp-2 text-sm leading-6 text-slate-400">{item.summary}</p>}
                    <div className="flex flex-wrap gap-2 text-xs text-slate-500">
                      <span>{item.source || "unknown"}</span>
                      {item.published_at && <span>· {formatContextTime(item.published_at)}</span>}
                    </div>
                  </a>
                ))}
              </div>

              <div className="rounded-2xl bg-slate-900/35 p-4">
                <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-200">
                  <CalendarDays size={17} className="text-cyan-300" />
                  발표 일정
                </div>
                {latestEvents.length === 0 ? (
                  <div className="py-5 text-sm text-slate-500">등록된 일정이 없습니다.</div>
                ) : (
                  <div className="space-y-3">
                    {latestEvents.slice(0, 5).map((event, index) => (
                      <div key={`${event.title}-${index}`} className="border-b border-slate-700/60 pb-3 last:border-0 last:pb-0">
                        <div className="text-sm font-medium text-slate-200">{event.title}</div>
                        <div className="mt-1 break-words text-xs leading-5 text-slate-400">{event.value}</div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </section>

      <section className={`relative ${isBond ? "mt-2" : ""}`}>
        <h2 className="mb-4 px-2 text-2xl font-bold tracking-tight">AI 분석 리포트</h2>
        <div className={`transition-all duration-500 ${!authToken ? "select-none opacity-60 blur-md" : ""}`}>
          <ReportCard reportData={report} isReportLoading={false} />
        </div>

        {!authToken && (
          <div className="absolute inset-0 z-10 flex flex-col items-center justify-center gap-4">
            <div className="absolute inset-0 rounded-3xl bg-slate-900/80" />
            <button
              onClick={() => navigate("/login")}
              className="z-20 rounded-xl bg-emerald-500 px-8 py-4 text-lg font-bold text-slate-900 transition-transform hover:scale-105 hover:bg-emerald-400"
            >
              로그인하고 AI 리포트 보기
            </button>
          </div>
        )}
      </section>

      <section>
        <h2 className="mb-4 px-2 text-2xl font-bold">종목 토론방</h2>

        <div className="mb-6 rounded-2xl bg-slate-800 p-4 shadow-md">
          <form onSubmit={handlePostComment} className="flex gap-2">
            <input
              type="text"
              value={newComment}
              onChange={(e) => setNewComment(e.target.value)}
              placeholder={authToken ? "이 종목에 대한 생각을 남겨보세요" : "로그인 후 댓글 작성이 가능합니다"}
              disabled={!authToken}
              className="flex-1 rounded-xl bg-slate-700/50 p-3 text-slate-200 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-emerald-500 disabled:opacity-50"
            />
            <button
              type="submit"
              disabled={!authToken || !newComment.trim()}
              className="flex items-center justify-center rounded-xl bg-emerald-500 p-3 text-slate-900 hover:bg-emerald-400 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Send size={20} className="ml-1" />
            </button>
          </form>
          {commentActionMessage && <p className="mt-3 text-sm text-slate-300">{commentActionMessage}</p>}
        </div>

        <div className="flex flex-col gap-3 px-2">
          {comments.length === 0 ? (
            <div className="py-6 text-center text-slate-500">아직 작성된 댓글이 없습니다.</div>
          ) : (
            comments.map((comment) => {
              const isOwner = Boolean(authToken && user && Number(user.id) === comment.user_id);
              const isEditing = editingCommentId === comment.id;

              return (
                <div key={comment.id} className="flex flex-col gap-2 rounded-xl bg-slate-800/60 p-4">
                  <div className="flex items-start justify-between">
                    <div className="flex flex-1 flex-col">
                      <div className="comment-actions flex items-center gap-2">
                        <span className="font-bold text-slate-200">{comment.author_nickname}</span>
                        {authToken && !isOwner && (
                          <button
                            type="button"
                            onClick={() => openReportReasons(comment.id)}
                            className="ml-auto inline-flex items-center gap-1 text-xs text-slate-400 hover:text-amber-300"
                            title="댓글 신고"
                          >
                            <Flag size={14} />
                            신고
                          </button>
                        )}
                        {isOwner && (
                          <div className="ml-auto flex gap-2 text-xs">
                            {!isEditing ? (
                              <>
                                <button
                                  type="button"
                                  onClick={() => startEditComment(comment)}
                                  className="text-slate-300 hover:text-emerald-400"
                                >
                                  수정
                                </button>
                                <button
                                  type="button"
                                  onClick={() => deleteComment(comment.id)}
                                  className="text-slate-300 hover:text-red-400"
                                >
                                  삭제
                                </button>
                              </>
                            ) : (
                              <>
                                <button
                                  type="button"
                                  onClick={() => saveEditComment(comment.id)}
                                  className="text-emerald-400 hover:text-emerald-300"
                                >
                                  저장
                                </button>
                                <button
                                  type="button"
                                  onClick={cancelEditComment}
                                  className="text-slate-300 hover:text-slate-200"
                                >
                                  취소
                                </button>
                              </>
                            )}
                          </div>
                        )}
                      </div>

                      {!isEditing ? (
                        <span className="mt-1 whitespace-pre-wrap text-slate-200">{comment.content}</span>
                      ) : (
                        <textarea
                          value={editingContent}
                          onChange={(e) => setEditingContent(e.target.value)}
                          className="mt-2 min-h-20 rounded-lg bg-slate-700/50 p-2 text-sm text-slate-200 focus:outline-none focus:ring-2 focus:ring-emerald-500"
                        />
                      )}
                      {activeReportCommentId === comment.id && (
                        <div className="mt-3 rounded-lg border border-slate-700 bg-slate-900/60 p-3">
                          <p className="mb-2 text-xs font-medium text-slate-300">신고 사유를 선택해주세요.</p>
                          <div className="flex flex-wrap gap-2">
                            {REPORT_REASONS.map((reason) => (
                              <button
                                key={reason}
                                type="button"
                                onClick={() => reportComment(comment.id)}
                                disabled={reportingCommentId === comment.id}
                                className="rounded-md bg-slate-700 px-3 py-1.5 text-xs font-medium text-slate-200 transition-colors hover:bg-amber-500 hover:text-slate-950 disabled:cursor-not-allowed disabled:opacity-50"
                              >
                                {reason}
                              </button>
                            ))}
                            <button
                              type="button"
                              onClick={() => setActiveReportCommentId(null)}
                              disabled={reportingCommentId === comment.id}
                              className="rounded-md px-3 py-1.5 text-xs font-medium text-slate-400 hover:text-slate-200 disabled:cursor-not-allowed disabled:opacity-50"
                            >
                              취소
                            </button>
                          </div>
                        </div>
                      )}
                    </div>

                    <button
                      type="button"
                      onClick={() => handleLike(comment.id)}
                      className="group ml-3 flex flex-col items-center justify-center gap-1"
                    >
                      <Heart size={20} className="text-pink-500 transition-transform group-hover:scale-110" fill="none" />
                      <span className="text-xs font-medium text-slate-400">{comment.likes_count}</span>
                    </button>
                  </div>
                  <div className="mt-1 text-xs text-slate-500">{formatCommentCreatedAt(comment.created_at)}</div>
                </div>
              );
            })
          )}
        </div>
      </section>
    </div>
  );
}
