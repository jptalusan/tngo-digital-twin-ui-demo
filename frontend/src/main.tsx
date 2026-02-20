
import { createRoot } from "react-dom/client";
import { ThemeProvider } from "next-themes";
import App from "./App.tsx";
import { AnalysisJobsProvider } from "./state/analysisJobs";
import "leaflet/dist/leaflet.css";
import "./index.css";

createRoot(document.getElementById("root")!).render(
  <ThemeProvider attribute="class" defaultTheme="light" enableSystem={false}>
    <AnalysisJobsProvider>
      <App />
    </AnalysisJobsProvider>
  </ThemeProvider>
);
  
