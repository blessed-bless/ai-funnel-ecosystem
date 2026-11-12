(async () => {
  try {
    const params = new URLSearchParams(location.search);
    await fetch("/api/funnel/hit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        source: params.get("src") || "landing",
        utm_campaign: params.get("utm_campaign"),
        path: location.pathname,
        funnel_slug: "default",
      }),
    });
  } catch (_err) {
    // hit не блокирует CTA
  }
})();
