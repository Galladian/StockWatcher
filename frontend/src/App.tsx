import { NavLink, useLocation } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import ChartPage from "./ChartPage";
import PortfolioPage from "./PortfolioPage";
import ScreenerPage from "./ScreenerPage";
import { fetchMe, logout } from "./portfolioApi";

export default function App() {
  const qc = useQueryClient();
  const { pathname } = useLocation();
  const onPortfolio = pathname.startsWith("/portfolio");
  const onScreener = pathname.startsWith("/screener");

  const me = useQuery({ queryKey: ["me"], queryFn: fetchMe, staleTime: Infinity });
  const signOut = useMutation({
    mutationFn: logout,
    onSuccess: () => {
      qc.setQueryData(["me"], { username: null });
      qc.removeQueries({ queryKey: ["transactions"] });
      qc.removeQueries({ queryKey: ["summary"] });
    },
  });

  return (
    <div className="shell">
      <nav className="topnav">
        <NavLink to="/" end>Chart</NavLink>
        <NavLink to="/screener">Screener</NavLink>
        <NavLink to="/portfolio">Portfolio</NavLink>
        <span className="spacer" />
        {me.data?.username && (
          <>
            <span className="muted">{me.data.username}</span>
            <button className="linkbtn" onClick={() => signOut.mutate()}>Log out</button>
          </>
        )}
      </nav>

      <div className="page">
        {/* Chart stays mounted (just hidden) so your ticker and timeframe survive a trip to Portfolio */}
        <div className={`page-inner${onPortfolio || onScreener ? " is-hidden" : ""}`}>
          <ChartPage />
        </div>
        {onScreener && <ScreenerPage />}
        {onPortfolio && <PortfolioPage />}
      </div>
    </div>
  );
}
