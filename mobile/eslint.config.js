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
  // Layer boundaries (CLAUDE.md Architecture). src/app (Expo Router screens) is
  // the top layer — nothing below it may import it back.
  {
    files: [
      "src/features/**",
      "src/lib/**",
      "src/components/**",
      "src/constants/**",
      "src/hooks/**",
    ],
    rules: {
      "no-restricted-imports": [
        "error",
        {
          patterns: [
            {
              group: ["@/app", "@/app/*", "**/src/app/*"],
              message:
                "src/app is the top layer (Expo Router screens) — lower layers must not import it.",
            },
          ],
        },
      ],
    },
  },
  // Shared layers must not depend on feature code — move shared logic down or
  // feature-specific code up into its feature.
  {
    files: ["src/lib/**", "src/components/**", "src/constants/**", "src/hooks/**"],
    rules: {
      "no-restricted-imports": [
        "error",
        {
          patterns: [
            {
              group: ["@/app", "@/app/*", "**/src/app/*"],
              message:
                "src/app is the top layer (Expo Router screens) — lower layers must not import it.",
            },
            {
              group: ["@/features/*", "**/src/features/*"],
              message:
                "Shared layers (lib/components/constants/hooks) must not depend on feature code.",
            },
          ],
        },
      ],
    },
  },
];
