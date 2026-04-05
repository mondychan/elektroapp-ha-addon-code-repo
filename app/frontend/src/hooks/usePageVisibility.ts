import { useEffect, useState } from "react";

export const usePageVisibility = () => {
  const [isPageVisible, setIsPageVisible] = useState(() => document.visibilityState === "visible");

  useEffect(() => {
    const handleVisibility = () => {
      setIsPageVisible(document.visibilityState === "visible");
    };
    document.addEventListener("visibilitychange", handleVisibility);
    return () => document.removeEventListener("visibilitychange", handleVisibility);
  }, []);

  return isPageVisible;
};
