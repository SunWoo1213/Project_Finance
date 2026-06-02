import { Link, NavLink } from "react-router-dom";

import useAuthStore from "../store/authStore";
import useSubscriptionStore from "../store/subscriptionStore";
import PlanBadge from "./PlanBadge";

export default function Header() {
  const { token, user, logout } = useAuthStore();
  const { tier, isLoading } = useSubscriptionStore();

  const navItems = [
    { name: "홈", path: "/" },
    { name: "미국 주식", path: "/category/us_top10" },
    { name: "한국 주식", path: "/category/kr_top10" },
    { name: "채권", path: "/category/bonds" },
    { name: "원자재", path: "/category/commodities" },
    { name: "암호화폐", path: "/category/cryptos" },
    { name: "요금제", path: "/pricing" },
  ];

  return (
    <header className="flex flex-col gap-4 border-b border-slate-800 px-2 py-4 md:flex-row md:items-center md:justify-between">
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:gap-8">
        <Link
          to="/"
          className="text-2xl font-bold bg-gradient-to-r from-emerald-400 to-cyan-400 bg-clip-text text-transparent"
        >
          AI Invest
        </Link>
        <nav className="flex flex-wrap gap-4">
          {navItems.map((item) => (
            <NavLink
              key={item.name}
              to={item.path}
              className={({ isActive }) =>
                `text-base font-medium transition-colors ${
                  isActive ? "text-emerald-400" : "text-slate-400 hover:text-slate-200"
                }`
              }
            >
              {item.name}
            </NavLink>
          ))}
        </nav>
      </div>
      <div className="flex items-center gap-4 text-slate-300">
        {token ? (
          <>
            <PlanBadge tier={tier} isLoading={isLoading} />
            <Link to="/mypage" className="text-sm font-medium text-slate-200 hover:text-emerald-300">
              {user?.nickname || "마이페이지"}
              {!user?.nickname_confirmed && (
                <span className="ml-2 rounded-full bg-amber-400/15 px-2 py-0.5 text-[11px] text-amber-200">
                  설정 필요
                </span>
              )}
            </Link>
            <button
              onClick={logout}
              className="cursor-pointer rounded-md bg-slate-800 px-3 py-1 text-sm transition-colors hover:bg-slate-700"
            >
              로그아웃
            </button>
          </>
        ) : (
          <Link
            to="/login"
            className="rounded-md bg-emerald-500 px-3 py-1 text-sm font-medium text-slate-900 transition-colors hover:bg-emerald-400"
          >
            로그인
          </Link>
        )}
      </div>
    </header>
  );
}
