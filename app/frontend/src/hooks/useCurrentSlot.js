import { useEffect, useState } from "react";

export const useCurrentSlot = () => {
  const [currentSlot, setCurrentSlot] = useState(null);

  useEffect(() => {
    const updateSlot = () => {
      const now = new Date();
      const slot = now.getHours() * 4 + Math.floor(now.getMinutes() / 15);
      setCurrentSlot(slot);
    };
    updateSlot();
    const intervalId = setInterval(updateSlot, 60000);
    return () => clearInterval(intervalId);
  }, []);

  return currentSlot;
};
