import { BrowserRouter, Route, Routes, useParams } from "react-router-dom";
import { Toaster } from "react-hot-toast";

import Header from "./components/Header";
import Home from "./pages/Home";
import CategoryView from "./pages/CategoryView";
import AssetDetail from "./pages/AssetDetail";
import Register from "./pages/Register";
import Login from "./pages/Login";

function CategoryWrapper() {
  const { type } = useParams();
  const map = {
    us_top10: "US TOP 10",
    kr_top10: "KR TOP 10",
    bonds: "Bonds",
    commodities: "Commodities",
    cryptos: "Cryptos",
  };

  return <CategoryView key={type} categoryKey={type} title={map[type] || "Assets"} />;
}

function App() {
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
              <Route path="/detail/:ticker" element={<AssetDetail />} />
              <Route path="/login" element={<Login />} />
              <Route path="/register" element={<Register />} />
            </Routes>
          </main>
        </div>
      </div>
    </BrowserRouter>
  );
}

export default App;
