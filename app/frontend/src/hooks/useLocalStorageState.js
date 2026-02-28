import { useEffect, useState } from "react";

export const useLocalStorageState = (key, initialValue) => {
  const [state, setState] = useState(() => {
    const stored = localStorage.getItem(key);
    if (stored == null) {
      return typeof initialValue === "function" ? initialValue() : initialValue;
    }
    return stored;
  });

  useEffect(() => {
    localStorage.setItem(key, state);
  }, [key, state]);

  return [state, setState];
};
