import { useEffect, useState } from "react";

const WAKE_MESSAGE_DELAY_MS = 4_000;

// Most starts finish quickly, so the longer explanation only appears once
// this looks like a server waking from sleep rather than a normal load.
export function ConnectingScreen() {
  const [isSlow, setIsSlow] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setIsSlow(true), WAKE_MESSAGE_DELAY_MS);
    return () => clearTimeout(timer);
  }, []);

  return (
    <div className="loading-screen">
      <p>Loading…</p>
      {isSlow && <p>Waking the server. This can take up to a minute.</p>}
    </div>
  );
}
