// Silence noisy native warnings in tests; add module mocks here as needed.
jest.mock("expo-secure-store", () => ({
  getItemAsync: jest.fn(),
  setItemAsync: jest.fn(),
  deleteItemAsync: jest.fn(),
  WHEN_UNLOCKED_THIS_DEVICE_ONLY: "WHEN_UNLOCKED_THIS_DEVICE_ONLY",
}));

// Default: behave like an already-initialized install (marker present). Tests
// that exercise the fresh-install path override File.mockImplementation.
jest.mock("expo-file-system", () => ({
  File: jest.fn(() => ({ exists: true, create: jest.fn() })),
  Paths: { document: "file:///document/" },
}));
