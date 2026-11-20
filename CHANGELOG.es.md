# Novedades

[English](CHANGELOG.md) · **Español**

Los cambios importantes de Omarchy Top Bar Plus. El formato sigue
[Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y las versiones siguen
[Versionado Semántico](https://semver.org/lang/es/).

## [0.3.0] - 2026-11-19

Primera versión pública.

### Cambiado

- La supresión de la barra solo pide a Hyprland sus ventanas con los eventos de
  ventana, ya no en cada cambio de espacio de trabajo ni al volver un monitor.
- `Bar.qml` reorganizado como la barra nativa: componentes en línea para la barra
  de cada pantalla, la franja del borde y la sonda de depuración, y la lógica pura
  en `PeekModel.js`.
- Lo que solo sirve para el registro de depuración no trabaja con el registro
  apagado.
- `check.py` ejecuta pruebas con nombre desde una sola lista, con `--only` y
  `--repeat`, y antes de empezar comprueba lo que necesita: si falta algo, se para y
  dice cómo arreglarlo.
- README y novedades en inglés y en español, con logo, captura y demo propios.

### Añadido

- Pruebas unitarias de `PeekModel.js`: `node --test tests/`.
- `check.py --reconnect` mantiene abierta durante la reconexión una ventana
  etiquetada a pantalla completa.

### Quitado

- Las llamadas IPC manuales `probe` y `nudge`. La sonda automática de salida sigue
  registrando con la depuración activada.
- Las capturas y la demo heredadas de Top Bar Peek.

## [0.2.1] - 2026-11-19

### Corregido

- Una ventana a pantalla completa ya cerrada podía quedarse en la lista de ventanas
  de Quickshell e impedir que la barra asomara en su pantalla hasta reiniciar el
  shell. Ahora la supresión sale de `hyprctl clients -j`.

## [0.2.0] - 2026-11-18

### Añadido

- Las ventanas con la etiqueta `no-bar-peek` a pantalla completa o maximizadas se
  quedan el borde superior para su propia barra: ahí la barra no asoma, si estaba
  asomada se oculta y la franja del borde no recibe el ratón.

## [0.1.0] - 2026-11-18

Primera versión como Top Bar Plus, adaptada de Top Bar Peek a Omarchy 4.5.

### Añadido

- Identificador propio, `io.github.kuroge.topbar-plus`, para poder convivir con
  Top Bar Peek.
- `omarchy shell topbar-plus status` y registro de depuración opcional con
  `setDebug`.

### Corregido

- En reposo no queda ninguna capa transparente del tamaño de la pantalla sobre las
  ventanas: la barra nativa conserva su posición y su capa hasta que asoma.
- La barra recibe el ratón cuando asoma sobre una ventana a pantalla completa.
- Sin parpadeos al entrar rápido desde el borde, al dejar el ratón apoyado en el
  borde ni al cerrar un desplegable sobre la barra.
- Sin espacio reservado ni ventanas empujadas hacia abajo después de reconectar un
  monitor.
- Sin errores cuando desaparece la barra de un monitor.

[0.3.0]: https://github.com/Kuroge/omarchy-topbar-plus/releases/tag/v0.3.0
