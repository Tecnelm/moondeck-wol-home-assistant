import { ExternalAppInfo, GameStreamAppInfo } from "../lib/externalappshortcuts";
import { useContext, useEffect, useState } from "react";
import { AppType } from "../lib";
import { MoonDeckContext } from "../contexts";

function filterApps(apps: Map<number, ExternalAppInfo>): GameStreamAppInfo[] {
  return Array.from(apps.values())
    .filter((app) => app.appType === AppType.GameStream)
    .sort((a, b) => a.appName < b.appName ? -1 : a.appName > b.appName ? 1 : 0);
}

export function useGameStreamAppShortcuts(): GameStreamAppInfo[] {
  const { externalAppShortcuts } = useContext(MoonDeckContext);
  const [shortcuts, setShortcuts] = useState(filterApps(externalAppShortcuts.appInfo.value));

  useEffect(() => {
    const sub = externalAppShortcuts.appInfo.asObservable().subscribe((value) => setShortcuts(filterApps(value)));
    return () => {
      sub.unsubscribe();
    };
  }, []);

  return shortcuts;
}
