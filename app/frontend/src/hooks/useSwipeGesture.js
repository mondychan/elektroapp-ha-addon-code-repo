import { useRef } from "react";

export const useSwipeGesture = ({
  enabled = true,
  minDistance = 60,
  maxOffAxis = 50,
  onSwipeLeft,
  onSwipeRight,
}) => {
  const touchRef = useRef(null);

  const onTouchStart = (event) => {
    if (!enabled || event.touches.length !== 1) return;
    const touch = event.touches[0];
    touchRef.current = {
      startX: touch.clientX,
      startY: touch.clientY,
      endX: touch.clientX,
      endY: touch.clientY,
    };
  };

  const onTouchMove = (event) => {
    if (!touchRef.current || event.touches.length !== 1) return;
    const touch = event.touches[0];
    touchRef.current.endX = touch.clientX;
    touchRef.current.endY = touch.clientY;
  };

  const onTouchEnd = () => {
    if (!touchRef.current) return;
    const { startX, startY, endX, endY } = touchRef.current;
    touchRef.current = null;
    const diffX = endX - startX;
    const diffY = endY - startY;
    if (Math.abs(diffY) > maxOffAxis || Math.abs(diffX) < minDistance) return;
    if (diffX < 0) {
      onSwipeLeft?.();
    } else {
      onSwipeRight?.();
    }
  };

  return {
    onTouchStart,
    onTouchMove,
    onTouchEnd,
  };
};
