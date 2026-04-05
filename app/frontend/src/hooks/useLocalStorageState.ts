import { useEffect, useState, Dispatch, SetStateAction } from "react";

export function useLocalStorageState<T>(key: string, initialValue: T | (() => T)): [T, Dispatch<SetStateAction<T>>] {
  const [state, setState] = useState<T>(() => {
    const stored = localStorage.getItem(key);
    if (stored === null) {
      return typeof initialValue === "function" ? (initialValue as any)() : initialValue;
    }
    return stored as unknown as T;
  });

  useEffect(() => {
    localStorage.setItem(key, String(state));
  }, [key, state]);

  return [state, setState];
}
