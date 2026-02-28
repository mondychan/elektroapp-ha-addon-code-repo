import { buildInfluxError, extractApiError, formatApiError } from "./elektroappApi";

jest.mock("axios", () => ({
  get: jest.fn(),
  post: jest.fn(),
  put: jest.fn(),
}));

test("extractApiError parses unified backend envelope", () => {
  const err = {
    response: {
      status: 422,
      data: {
        error: {
          code: "VALIDATION_ERROR",
          message: "Request validation failed.",
          detail: [{ loc: ["body", "x"], msg: "required" }],
          request_id: "abc123",
        },
      },
    },
  };
  const parsed = extractApiError(err);
  expect(parsed.code).toBe("VALIDATION_ERROR");
  expect(parsed.message).toBe("Request validation failed.");
  expect(parsed.requestId).toBe("abc123");
});

test("formatApiError appends error code for UI", () => {
  const err = {
    response: {
      status: 400,
      data: {
        error: {
          code: "BAD_REQUEST",
          message: "Invalid payload",
        },
      },
    },
  };
  expect(formatApiError(err, "Fallback")).toBe("Invalid payload [BAD_REQUEST]");
});

test("buildInfluxError contains auth code in UI message", () => {
  const err = {
    response: {
      status: 401,
      data: {
        error: {
          code: "UNAUTHORIZED",
          message: "Unauthorized",
        },
      },
    },
  };
  expect(buildInfluxError(err)).toBe(
    "Nepodarilo se overit pristup k InfluxDB (401). Zkontroluj uzivatele a heslo. [UNAUTHORIZED]"
  );
});
