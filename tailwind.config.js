module.exports = {
  content: [
    "./templates/**/*.html",
    "./accounts/templates/**/*.html",
    "./agents/templates/**/*.html",
    "./alignment/templates/**/*.html",
    "./exports/templates/**/*.html",
    "./projects/templates/**/*.html",
    "./specs/templates/**/*.html",
    "./specs/templatetags/**/*.py",
    "./static/js/**/*.js"
  ],
  safelist: [
    "diff-line",
    "diff-line-context",
    "diff-line-meta-old",
    "diff-line-meta-new",
    "diff-line-hunk",
    "diff-line-remove",
    "diff-line-add"
  ],
  theme: {
    extend: {
      colors: {
        gray: {
          50: "#FAFAFA",
          100: "#F4F4F5",
          200: "#E4E4E7",
          300: "#D4D4D8",
          400: "#A1A1AA",
          500: "#71717A",
          600: "#52525B",
          700: "#3F3F46",
          800: "#27272A",
          900: "#18181B"
        },
        brand: {
          agent: "#8B5CF6",
          decision: "#10B981",
          warning: "#F59E0B",
          danger: "#EF4444",
          info: "#3B82F6"
        }
      },
      fontFamily: {
        sans: ["Satoshi", "sans-serif"],
        display: ["Cabinet Grotesk", "sans-serif"]
      },
      boxShadow: {
        card: "0 1px 2px rgba(24, 24, 27, 0.05)",
        paper: "0 10px 30px rgba(24, 24, 27, 0.08)"
      }
    }
  },
  plugins: [require("@tailwindcss/typography")]
};
