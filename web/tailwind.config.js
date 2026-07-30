/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./lib/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        aeon: {
          bg: "var(--aeon-bg)",
          "bg-1": "var(--aeon-bg-1)",
          "bg-2": "var(--aeon-bg-2)",
          "bg-elevated": "var(--aeon-bg-elevated)",
          fg: "var(--aeon-fg)",
          "fg-soft": "var(--aeon-fg-soft)",
          "fg-mute": "var(--aeon-fg-mute)",
          border: "var(--aeon-border)",
          primary: "var(--aeon-primary)",
          "primary-hover": "var(--aeon-primary-hover)",
          success: "var(--aeon-success)",
          warning: "var(--aeon-warning)",
          danger: "var(--aeon-danger)",
          info: "var(--aeon-info)",
        },
      },
      borderRadius: {
        aeon: "var(--aeon-radius)",
        "aeon-sm": "var(--aeon-radius-sm)",
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "-apple-system", "BlinkMacSystemFont", "Segoe UI", "Roboto", "Helvetica Neue", "Arial", "sans-serif"],
        mono: ["SF Mono", "Fira Code", "ui-monospace", "SFMono-Regular", "Menlo", "Monaco", "Consolas", "Liberation Mono", "Courier New", "monospace"],
      },
      boxShadow: {
        aeon: "0 4px 20px rgba(0, 0, 0, 0.25)",
        "aeon-lg": "0 8px 32px rgba(0, 0, 0, 0.35)",
      },
      animation: {
        "fade-in": "fadeIn 0.2s ease-out",
        "slide-up": "slideUp 0.25s ease-out",
        pulse: "pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite",
      },
      keyframes: {
        fadeIn: {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        slideUp: {
          "0%": { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
    },
  },
  plugins: [],
};
