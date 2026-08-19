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
        // El plano de página va claramente MÁS oscuro que la tarjeta. Con
        // #f9f9f7 (3 puntos de diferencia) las tarjetas y los botones perdían
        // el borde visual y todo se veía plano y borroso.
        bg: "#f3f2ed",      // plano de página
        panel: "#fcfcfb",   // superficie de tarjeta/tabla
        // Un paso más oscuro que el azul base: el botón activo lleva texto
        // blanco encima y a #2a78d6 quedaba en 4,42:1, por debajo del mínimo
        // para texto chico. A #256abf sube a 5,2:1 y a simple vista es el
        // mismo azul. Revalidado como slot 1 de la paleta categórica.
        accent: "#256abf",  // azul de acción y serie 1
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
