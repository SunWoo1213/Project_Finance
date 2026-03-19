import React, { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import axios from "axios";
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import ReactMarkdown from "react-markdown";
import { Heart, Send } from "lucide-react";

import useAuthStore from "../store/authStore";
import { formatChangeBadge, formatMarketCap, formatPrice, formatTicker } from "../utils/formatters";
import { resolveAssetName } from "../utils/constants";

export default function AssetDetail() {
  const { ticker } = useParams();
  const assetTicker = String(ticker || "").trim();
  const navigate = useNavigate();
  const { token, user } = useAuthStore();
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
  const [editingCommentId, setEditingCommentId] = useState(null);
  const [editingContent, setEditingContent] = useState("");
  const reportRequestCacheRef = useRef(new Set());

  const authHeaders = authToken ? { Authorization: `Bearer ${authToken}` } : {};

  const fetchComments = async () => {
    try {
      const res = await axios.get(`http://localhost:8000/api/community/${encodeURIComponent(assetTicker)}/comments`);
      setComments(res.data);
    } catch (error) {
      console.error("Failed to fetch comments:", error);
    }
  };

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
                await axios.post(`http://localhost:8000/api/ai/generate/${encodeURIComponent(assetTicker)}`);
                const retryRes = await axios.get(`http://localhost:8000/api/reports/${encodeURIComponent(assetTicker)}`, {
                  headers: authHeaders,
                });
                setReport(retryRes.data);
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
  }, [assetTicker, authToken]);

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
      await fetchComments();
    } catch (error) {
      console.error("Failed to post comment:", error);
    }
  };

  const startEditComment = (comment) => {
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
      await fetchComments();
    } catch (error) {
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
      await fetchComments();
    } catch (error) {
      console.error("Failed to delete comment:", error);
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
  const hasChartData = Array.isArray(chartData) && chartData.length > 0;

  const uiCategory =
    assetGroup === "bonds"
      ? assetTicker.startsWith("KTB_")
        ? "KR_BOND"
        : "US_BOND"
      : assetGroup === "commodities"
      ? "COMMODITY"
      : "US_STOCK";

  const isBond = uiCategory.includes("BOND");
  const marketCap = Number(marketInfo.marketCap ?? 0);
  const isMacro = marketCap <= 0 || uiCategory === "US_BOND" || uiCategory === "KR_BOND" || uiCategory === "COMMODITY";

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

  return (
    <div className="mx-auto flex max-w-screen-md flex-col gap-12 px-4 py-8">
      <section>
        <div className="mb-6">
          <h1 className="mb-2 bg-gradient-to-r from-emerald-400 to-cyan-400 bg-clip-text text-3xl font-bold text-transparent">
            {displayName}
            <span className="ml-2 align-middle text-lg font-medium text-slate-300">({formattedTicker})</span>
          </h1>
          <div className="flex items-end gap-4">
            <span className="text-5xl font-extrabold text-slate-100">{formatPrice(marketInfo.price, uiCategory)}</span>
            <span className={`pb-1 text-2xl font-bold ${badge.className}`}>{badge.text}</span>
          </div>

          {isMacro ? (
            <div className="mt-2 inline-flex rounded-full bg-slate-700 px-3 py-1 text-xs text-slate-300">거시 지표</div>
          ) : (
            <div className="mt-2 text-sm text-slate-400">시가총액 {formatMarketCap(marketCap, uiCategory)}</div>
          )}
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

      <section className={`relative ${isBond ? "mt-2" : ""}`}>
        <h2 className="mb-4 px-2 text-2xl font-bold tracking-tight">AI 분석 리포트</h2>
        <div className={`rounded-3xl bg-slate-800 p-6 shadow-md transition-all duration-500 ${!authToken ? "select-none opacity-60 blur-md" : ""}`}>
          {report ? (
            <div className="prose prose-invert max-w-none prose-h1:text-xl prose-h2:text-lg prose-p:text-slate-300">
              <ReactMarkdown>{report.final_content}</ReactMarkdown>
            </div>
          ) : (
            <div className="py-10 text-center text-slate-400">이 종목의 AI 리포트가 아직 생성되지 않았습니다.</div>
          )}
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
        </div>

        <div className="flex flex-col gap-3 px-2">
          {comments.length === 0 ? (
            <div className="py-6 text-center text-slate-500">아직 작성된 댓글이 없습니다.</div>
          ) : (
            comments.map((comment) => {
              const isOwner = Boolean(authToken && user && user.id === comment.user_id);
              const isEditing = editingCommentId === comment.id;

              return (
                <div key={comment.id} className="flex flex-col gap-2 rounded-xl bg-slate-800/60 p-4">
                  <div className="flex items-start justify-between">
                    <div className="flex flex-1 flex-col">
                      <div className="comment-actions flex items-center gap-2">
                        <span className="font-bold text-slate-200">{comment.author_nickname}</span>
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
