import { NavLink, useLocation } from "react-router-dom";
import ChartPage from "./ChartPage";
import Overview from "./Overview";
import PortfolioPage from "./PortfolioPage";
import ScreenerPage from "./ScreenerPage";
import SettingsMenu from "./SettingsMenu";

export default function App() {
  const { pathname } = useLocation();
  const onOverview = pathname.startsWith("/overview");
  const onPortfolio = pathname.startsWith("/portfolio");
  const onScreener = pathname.startsWith("/screener");

  return (
    <div className="shell">
      <nav className="topnav">
        <NavLink to="/overview">Overview</NavLink>
        <NavLink to="/" end>Chart</NavLink>
        <NavLink to="/screener">Screener</NavLink>
        <NavLink to="/portfolio">Portfolio</NavLink>
        <span className="spacer" />
        <SettingsMenu />
      </nav>

      <div className="page">
        {/* Chart stays mounted (just hidden) so your ticker and timeframe survive a trip to another page */}
        <div className={`page-inner${onOverview || onPortfolio || onScreener ? " is-hidden" : ""}`}>
          <ChartPage />
        </div>
        {onOverview && <Overview />}
        {onScreener && <ScreenerPage />}
        {onPortfolio && <PortfolioPage />}
      </div>
    </div>
  );
}
