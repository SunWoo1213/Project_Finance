import { Link, NavLink } from 'react-router-dom';
import useAuthStore from '../store/authStore';
import useSubscriptionStore from '../store/subscriptionStore';
import PlanBadge from './PlanBadge';

export default function Header() {
  const { token, user, logout } = useAuthStore();
  const { tier, isLoading } = useSubscriptionStore();

  const navItems = [
    { name: '홈', path: '/' },
    { name: '미국 주식', path: '/category/us_top10' },
    { name: '한국 주식', path: '/category/kr_top10' },
    { name: '채권', path: '/category/bonds' },
    { name: '원자재', path: '/category/commodities' },
    { name: '암호화폐', path: '/category/cryptos' },
    { name: '요금제', path: '/pricing' },
  ];

  return (
    <header className="flex justify-between items-center py-4 px-2 border-b border-slate-800 mb-4">
      <div className="flex items-center gap-8">
        <Link to="/" className="text-2xl font-bold bg-gradient-to-r from-emerald-400 to-cyan-400 bg-clip-text text-transparent">
          AI Invest
        </Link>
        <nav className="flex gap-4">
          {navItems.map((item) => (
            <NavLink
              key={item.name}
              to={item.path}
              className={({ isActive }) => 
                `text-base font-medium transition-colors ${isActive ? 'text-emerald-400' : 'text-slate-400 hover:text-slate-200'}`
              }
            >
              {item.name}
            </NavLink>
          ))}
        </nav>
      </div>
      <div className="flex gap-4 text-slate-300 items-center">
        {token ? (
          <>
            <PlanBadge tier={tier} isLoading={isLoading} />
            <span className="text-sm font-medium">{user?.nickname}님</span>
            <button onClick={logout} className="px-3 py-1 text-sm bg-slate-800 hover:bg-slate-700 rounded-md transition-colors cursor-pointer">
              로그아웃
            </button>
          </>
        ) : (
          <div className="flex gap-2">
            <Link to="/login" className="px-3 py-1 text-sm bg-emerald-500 hover:bg-emerald-400 text-slate-900 font-medium rounded-md transition-colors">
              로그인
            </Link>
          </div>
        )}
      </div>
    </header>
  );
}
