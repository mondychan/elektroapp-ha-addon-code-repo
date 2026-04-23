import { act, renderHook } from "@testing-library/react";
import { usePullToRefresh } from "./usePullToRefresh";
import { useSwipeGesture } from "./useSwipeGesture";

describe("useSwipeGesture", () => {
  test("calls onSwipeLeft for horizontal left swipe", () => {
    const onSwipeLeft = vi.fn();
    const onSwipeRight = vi.fn();
    const { result } = renderHook(() =>
      useSwipeGesture({
        onSwipeLeft,
        onSwipeRight,
      })
    );

    act(() => {
      result.current.onTouchStart({ touches: [{ clientX: 200, clientY: 100 }] });
      result.current.onTouchMove({ touches: [{ clientX: 100, clientY: 110 }] });
      result.current.onTouchEnd();
    });

    expect(onSwipeLeft).toHaveBeenCalledTimes(1);
    expect(onSwipeRight).not.toHaveBeenCalled();
  });

  test("calls onSwipeRight for horizontal right swipe", () => {
    const onSwipeLeft = vi.fn();
    const onSwipeRight = vi.fn();
    const { result } = renderHook(() =>
      useSwipeGesture({
        onSwipeLeft,
        onSwipeRight,
      })
    );

    act(() => {
      result.current.onTouchStart({ touches: [{ clientX: 100, clientY: 120 }] });
      result.current.onTouchMove({ touches: [{ clientX: 190, clientY: 130 }] });
      result.current.onTouchEnd();
    });

    expect(onSwipeRight).toHaveBeenCalledTimes(1);
    expect(onSwipeLeft).not.toHaveBeenCalled();
  });

  test("does not trigger when gesture is mostly vertical", () => {
    const onSwipeLeft = vi.fn();
    const onSwipeRight = vi.fn();
    const { result } = renderHook(() =>
      useSwipeGesture({
        onSwipeLeft,
        onSwipeRight,
      })
    );

    act(() => {
      result.current.onTouchStart({ touches: [{ clientX: 100, clientY: 100 }] });
      result.current.onTouchMove({ touches: [{ clientX: 50, clientY: 180 }] });
      result.current.onTouchEnd();
    });

    expect(onSwipeLeft).not.toHaveBeenCalled();
    expect(onSwipeRight).not.toHaveBeenCalled();
  });
});

describe("usePullToRefresh", () => {
  test("arms and triggers refresh when threshold is reached", async () => {
    const onRefresh = vi.fn().mockResolvedValue(undefined);
    const { result } = renderHook(() =>
      usePullToRefresh({
        threshold: 40,
        resistance: 1,
        onRefresh,
      })
    );

    const preventDefault = vi.fn();
    await act(async () => {
      result.current.gestureHandlers.onTouchStart({ touches: [{ clientY: 100 }] });
      result.current.gestureHandlers.onTouchMove({ touches: [{ clientY: 160 }], preventDefault });
      await result.current.gestureHandlers.onTouchEnd();
    });

    expect(preventDefault).toHaveBeenCalled();
    expect(onRefresh).toHaveBeenCalledTimes(1);
    expect(result.current.pullDistance).toBe(0);
    expect(result.current.isArmed).toBe(false);
    expect(result.current.isRefreshing).toBe(false);
  });

  test("does not refresh below threshold", async () => {
    const onRefresh = vi.fn().mockResolvedValue(undefined);
    const { result } = renderHook(() =>
      usePullToRefresh({
        threshold: 80,
        resistance: 1,
        onRefresh,
      })
    );

    await act(async () => {
      result.current.gestureHandlers.onTouchStart({ touches: [{ clientY: 100 }] });
      result.current.gestureHandlers.onTouchMove({ touches: [{ clientY: 140 }], preventDefault: () => {} });
      await result.current.gestureHandlers.onTouchEnd();
    });

    expect(onRefresh).not.toHaveBeenCalled();
    expect(result.current.pullDistance).toBe(0);
    expect(result.current.isArmed).toBe(false);
  });
});
