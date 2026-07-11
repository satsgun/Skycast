import { AppShell } from "./components/AppShell";
import { useSettingsStore } from "./state/settingsStore";
import { useQuery } from "./state/useQuery";

function App() {
  const query = useQuery();
  const settings = useSettingsStore();

  return <AppShell query={query} settings={settings} />;
}

export default App;
