import { useEffect } from "react";
import { BrowserRouter, Route, Routes, useParams } from "react-router-dom";
import { Toaster } from "react-hot-toast";

import Header from "./components/Header";
import ChatbotLauncher from "./components/ChatbotLauncher";
import Home from "./pages/Home";
import CategoryView from "./pages/CategoryView";
import AssetDetail from "./pages/AssetDetail";
import MarketSnapshot from "./pages/MarketSnapshot";
import Login from "./pages/Login";
import Pricing from "./pages/Pricing";
import BillingSuccess from "./pages/BillingSuccess";
import BillingCancel from "./pages/BillingCancel";
import useAuthStore from "./store/authStore";
import useSubscriptionStore from "./store/subscriptionStore";

function CategoryWrapper() {
  const { type } = useParams();
  const map = {
    us_top10: "US TOP 10",
    kr_top10: "KR TOP 10",
    macro: "주요 지수·환율",
    bonds: "Bonds",
    commodities: "Commodities",
    cryptos: "Cryptos",
  };

  return <CategoryView key={type} categoryKey={type} title={map[type] || "Assets"} />;
}

function App() {
  const token = useAuthStore((state) => state.token);
  const fetchSubscription = useSubscriptionStore((state) => state.fetchMe);
  const clearSubscription = useSubscriptionStore((state) => state.clear);
  const canUseChatbot = useSubscriptionStore((state) => state.entitlements.can_use_chatbot);

  useEffect(() => {
    if (token) {
      fetchSubscription(token);
    } else {
      clearSubscription();
    }
  }, [clearSubscription, fetchSubscription, token]);

  return (
    <BrowserRouter>
      <div className="min-h-screen bg-slate-900 text-slate-50 font-sans">
        <div className="mx-auto flex min-h-screen max-w-screen-xl flex-col">
          <Header />
          <Toaster
            position="top-right"
            toastOptions={{
              duration: 3000,
              style: { background: "#334155", color: "#fff", borderRadius: "10px" },
            }}
          />
          <main className="flex-1 pb-12">
            <Routes>
              <Route path="/" element={<Home />} />
              <Route path="/category/:type" element={<CategoryWrapper />} />
              <Route path="/market/:ticker" element={<MarketSnapshot />} />
              <Route path="/detail/:ticker" element={<AssetDetail />} />
              <Route path="/login" element={<Login />} />
              <Route path="/pricing" element={<Pricing />} />
              <Route path="/billing/success" element={<BillingSuccess />} />
              <Route path="/billing/cancel" element={<BillingCancel />} />
            </Routes>
          </main>
          {canUseChatbot && <ChatbotLauncher />}
        </div>
      </div>
    </BrowserRouter>
  );
}

export default App;
