import { useEffect, useRef, useCallback } from "preact/hooks";

const TABS = [
  { key: "overview", label: "Overview" },
  { key: "holdings", label: "Holdings" },
  { key: "tax", label: "Tax" },
  { key: "rebalancing", label: "Rebalancing" },
  { key: "analysis", label: "AI Analysis" },
];

export function TabNav({ activeTab, onTabChange }) {
  const navRef = useRef(null);
  const pillRef = useRef(null);

  const updatePill = useCallback(() => {
    const nav = navRef.current;
    const pill = pillRef.current;
    if (!nav || !pill) return;
    const activeBtn = nav.querySelector(".tab-btn.active");
    if (!activeBtn) return;
    const navRect = nav.getBoundingClientRect();
    const btnRect = activeBtn.getBoundingClientRect();
    pill.style.left = btnRect.left - navRect.left + "px";
    pill.style.width = btnRect.width + "px";
  }, []);

  useEffect(() => {
    requestAnimationFrame(updatePill);
  }, [activeTab, updatePill]);

  useEffect(() => {
    window.addEventListener("resize", updatePill);
    return () => window.removeEventListener("resize", updatePill);
  }, [updatePill]);

  const handleKeyDown = useCallback(
    (e) => {
      const btns = TABS.map((t) => t.key);
      const idx = btns.indexOf(activeTab);
      let next = -1;
      if (e.key === "ArrowRight" || e.key === "ArrowDown") next = (idx + 1) % btns.length;
      else if (e.key === "ArrowLeft" || e.key === "ArrowUp") next = (idx - 1 + btns.length) % btns.length;
      else if (e.key === "Home") next = 0;
      else if (e.key === "End") next = btns.length - 1;
      if (next >= 0) {
        e.preventDefault();
        onTabChange(btns[next]);
      }
    },
    [activeTab, onTabChange],
  );

  return (
    <div class="tab-nav animate-in" style="--delay:400ms" role="tablist" aria-label="Dashboard sections" ref={navRef}>
      <div class="tab-pill" ref={pillRef} />
      {TABS.map((t) => {
        const isActive = t.key === activeTab;
        return (
          <button
            key={t.key}
            class={`tab-btn${isActive ? " active" : ""}`}
            role="tab"
            aria-selected={isActive}
            aria-controls={`tab-${t.key}`}
            tabIndex={isActive ? 0 : -1}
            onClick={() => onTabChange(t.key)}
            onKeyDown={handleKeyDown}
          >
            {t.label}
          </button>
        );
      })}
    </div>
  );
}
