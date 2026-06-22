const expoConfig = require("eslint-config-expo/flat");
const prettierConfig = require("eslint-config-prettier");
const globals = require("globals");

module.exports = [
  ...expoConfig,
  prettierConfig,
  {
    settings: {
      react: {
        version: "19.2.0",
      },
    },
  },
  {
    files: ["**/*.test.{ts,tsx,js,jsx}", "jest.setup.js"],
    languageOptions: {
      globals: {
        ...globals.jest,
      },
    },
  },
  {
    ignores: ["dist/**", ".expo/**", "node_modules/**"],
  },
];
