/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: 'class',
  content: ["./src/**/*.{html,ts}"],
  theme: {
    extend: {
      colors: {
        primary: '#5271FF',
        secondary: '#1933A8',
        neutral: {
          100: '#F8F8F8', // Light gray for page background, table rows
          200: '#B6B6B6', // Border gray for input fields, table rows
          900: '#646464', // Dark gray for primary text
        },  
      },
      fontFamily: {
        redhat: ['"Red Hat Display"', 'sans-serif']
      }
    },
  },
  plugins: [],
}

