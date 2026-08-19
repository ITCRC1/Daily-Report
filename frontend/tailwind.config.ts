import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Paleta clara "papel" (neutros cálidos). El tema anterior era oscuro
        // (#0F1118 / #1E2130 / #2962FF); se cambió porque los reportes se
        // imprimen en blanco y así la pantalla coincide con el papel.
        bg: "#f9f9f7",      // plano de página
        panel: "#fcfcfb",   // superficie de tarjeta/tabla
        accent: "#2a78d6",  // azul de acción y serie 1
        ink: "#0b0b0b",     // tinta primaria -- alimenta text-ink/NN, border-ink/NN
        line: "#e1e0d9",    // filete / gridline
      },
      // La escala de opacidad de Tailwind va de 5 en 5; estos tres tramos finos
      // hacen falta para bordes y lavados de hover, que a /5 desaparecen y a
      // /15 se ven sucios sobre fondo claro.
      opacity: {
        4: "0.04",
        8: "0.08",
        12: "0.12",
      },
    },
  },
  plugins: [],
};

export default config;
