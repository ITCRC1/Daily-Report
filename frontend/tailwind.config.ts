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
        ink: "#0b0f0d",     // tinta primaria -- alimenta text-ink/NN, border-ink/NN
        line: "#e1e0d9",    // filete / gridline

        // --- Paleta de marca (glif.app) ---------------------------------
        // Owner, 2026-11-05: *«quiero usar estos colores y este formato de
        // letras»*. Los tokens de glif son para fondo OSCURO (#0b0f0d) y acá
        // el plano es claro porque los reportes se imprimen. Entonces se
        // conserva el TONO de cada color y se baja la luminosidad hasta que
        // pasa 4,5:1 sobre el fondo de página (#f3f2ed), que es el caso más
        // exigente -- sobre el blanco del papel todos quedan ≥5,0:1.
        //
        //   glif #5fc99d verde  2,03:1 ->  #2a7c5a  4,54:1
        //   glif #cd3045 rojo   5,12:1 ->  sin cambio, ya pasaba
        //   glif #fdd34f ámbar  1,44:1 ->  #8a6902  4,57:1
        //   glif #4ba4ff azul   2,61:1 ->  #006cda  4,51:1
        //   glif #bd7bf7 lila   2,86:1 ->  #9933f3  4,54:1
        //   glif #99a49d gris   2,58:1 ->  #657169  4,55:1
        //
        // El verde y el ámbar de glif usados tal cual serían ilegibles: 2,03 y
        // 1,44 sobre claro. Es el tipo de detalle que en pantalla grande se
        // perdona y en una cifra de tabla impresa no.
        brand: "#2a7c5a",        // verde glif -- favorable
        "brand-soft": "#5fc99d", // el verde original: solo para filetes y fondos
        danger: "#cd3045",       // rojo glif, tal cual
        warn: "#8a6902",         // ámbar glif
        info: "#006cda",         // azul glif
        violet: "#9933f3",       // lila glif
        subtle: "#657169",       // gris apagado glif
      },
      fontFamily: {
        // Manrope para todo; el serif queda para el título del reporte
        // impreso. Las dos son las de glif (la segunda es su stack serif).
        sans: ['var(--font-sans)', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        serif: ['"Iowan Old Style"', 'Baskerville', '"Times New Roman"', 'serif'],
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
