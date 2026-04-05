import { useRef, TouchEvent } from "react";

interface useSwipeGestureProps {
  enabled?: boolean;
  minDistance?: number;
  maxOffAxis?: number;
  onSwipeLeft?: () => void;
  onSwipeRight?: () => void;
}

export const useSwipeGesture = ({
  enabled = true,
  minDistance = 60,
  maxOffAxis = 50,
  onSwipeLeft,
  onSwipeRight,
}: useSwipeGestureProps) => {
  const touchRef = useRef<{ startX: number; startY: number; endX: number; endY: number } | null>(null);

  const onTouchStart = (event: TouchEvent) => {
    if (!enabled || event.touches.length !== 1) return;
    const touch = event.touches[0];
    touchRef.current = {
      startX: touch.clientX,
      startY: touch.clientY,
      endX: touch.clientX,
      endY: touch.clientY,
    };
  };

  const onTouchMove = (event: TouchEvent) => {
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
