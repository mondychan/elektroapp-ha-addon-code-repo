import { formatCurrency, formatBytes, formatSlotToTime } from "./utils/formatters";

test("formatCurrency returns localized CZK string", () => {
  expect(formatCurrency(123.456)).toBe("123.46,-Kc");
});

test("formatBytes formats bytes to MB", () => {
  expect(formatBytes(2 * 1024 * 1024)).toBe("2.0 MB");
});

test("formatSlotToTime converts quarter-hour slot index to HH:mm", () => {
  expect(formatSlotToTime(6)).toBe("01:30");
});
