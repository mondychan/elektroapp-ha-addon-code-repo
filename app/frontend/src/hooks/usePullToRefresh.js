import { useRef, useState } from "react";

export const usePullToRefresh = ({
  enabled = true,
  threshold = 72,
  maxPull = 120,
  resistance = 0.5,
  onRefresh,
}) => {
  const [pullDistance, setPullDistance] = useState(0);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isArmed, setIsArmed] = useState(false);

  const activeRef = useRef(false);
  const startYRef = useRef(0);
  const distanceRef = useRef(0);

  const resetPullState = () => {
    distanceRef.current = 0;
    setPullDistance(0);
    setIsArmed(false);
  };

  const onTouchStart = (event) => {
    if (!enabled || isRefreshing || event.touches.length !== 1) return;
    if (window.scrollY > 0) return;
    activeRef.current = true;
    startYRef.current = event.touches[0].clientY;
  };

  const onTouchMove = (event) => {
    if (!activeRef.current || event.touches.length !== 1) return;
    if (window.scrollY > 0) {
      activeRef.current = false;
      resetPullState();
      return;
    }
    const delta = event.touches[0].clientY - startYRef.current;
    if (delta <= 0) {
      resetPullState();
      return;
    }

    const damped = Math.min(maxPull, Math.round(delta * resistance));
    distanceRef.current = damped;
    setPullDistance(damped);
    setIsArmed(damped >= threshold);
    if (damped > 0) {
      event.preventDefault();
    }
  };

  const onTouchEnd = async () => {
    if (!activeRef.current) return;
    activeRef.current = false;
    const shouldRefresh = distanceRef.current >= threshold;
    if (!shouldRefresh || typeof onRefresh !== "function") {
      resetPullState();
      return;
    }

    setIsRefreshing(true);
    try {
      await onRefresh();
    } finally {
      setIsRefreshing(false);
      resetPullState();
    }
  };

  return {
    pullDistance,
    isRefreshing,
    isArmed,
    gestureHandlers: {
      onTouchStart,
      onTouchMove,
      onTouchEnd,
      onTouchCancel: onTouchEnd,
    },
  };
};
