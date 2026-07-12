import { AppShell } from "./components/AppShell";
import { useSettingsStore } from "./state/settingsStore";
import { useQuery } from "./state/useQuery";

function App() {
  const settings = useSettingsStore();
  const query = useQuery(settings);

  return <AppShell query={query} settings={settings} />;
}

export default App;
