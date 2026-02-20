
import { createRoot } from "react-dom/client";
import App from "./App.tsx";
import { AnalysisJobsProvider } from "./state/analysisJobs";
import "./index.css";

createRoot(document.getElementById("root")!).render(
  <AnalysisJobsProvider>
    <App />
  </AnalysisJobsProvider>
);
  
