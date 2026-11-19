import { useEffect, useState } from "react";

const hasFocus = () => {
  if (typeof document === "undefined") return true;
  if (typeof document.hasFocus === "function") {
    try {
      return document.hasFocus();
    } catch {
      return true;
    }
  }
  return document.visibilityState === "visible";
};

/**
 * Live-dashboard activity signal.
 *
 * True only while the tab is visible *and* it owns the window focus: a wall
 * tablet with the app in a background tab, a browser minimised by the user, or a
 * second monitor with another window focused all go quiet and the 1 Hz polling
 * stops.  Coming back — either via ``visibilitychange`` or the window ``focus``
 * event, including ``pageshow`` after a back/forward-cache restore — flips it
 * true again, which is what the instant refetch hangs off.
 */
export const usePageVisibility = () => {
  const [isPageVisible, setIsPageVisible] = useState(
    () => typeof document === "undefined" || document.visibilityState === "visible",
  );
  const [hasWindowFocus, setHasWindowFocus] = useState(hasFocus);

  useEffect(() => {
    const handleVisibility = () => {
      setIsPageVisible(document.visibilityState === "visible");
      setHasWindowFocus(hasFocus());
    };
    const handleFocus = () => setHasWindowFocus(true);
    const handleBlur = () => setHasWindowFocus(hasFocus());
    const handlePageShow = () => {
      setIsPageVisible(document.visibilityState === "visible");
      setHasWindowFocus(hasFocus());
    };
    const handlePageHide = () => {
      setIsPageVisible(false);
      setHasWindowFocus(false);
    };

    document.addEventListener("visibilitychange", handleVisibility);
    window.addEventListener("focus", handleFocus);
    window.addEventListener("blur", handleBlur);
    window.addEventListener("pageshow", handlePageShow);
    window.addEventListener("pagehide", handlePageHide);
    return () => {
      document.removeEventListener("visibilitychange", handleVisibility);
      window.removeEventListener("focus", handleFocus);
      window.removeEventListener("blur", handleBlur);
      window.removeEventListener("pageshow", handlePageShow);
      window.removeEventListener("pagehide", handlePageHide);
    };
  }, []);

  return isPageVisible && hasWindowFocus;
};
