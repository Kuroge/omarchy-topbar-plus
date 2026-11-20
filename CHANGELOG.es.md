# Novedades

[English](CHANGELOG.md) · **Español**

Aquí se apuntan los cambios importantes de Omarchy Top Bar Plus. El formato sigue
[Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y la numeración de
versiones, el [versionado semántico](https://semver.org/lang/es/).

## [0.3.0] - 2026-11-19

Primera versión pública.

### Cambios

- Para saber dónde no debe aparecer la barra, solo se consulta a Hyprland cuando
  cambian las ventanas; ya no al cambiar de espacio de trabajo ni al volver un
  monitor.
- `Bar.qml` se organiza como la barra nativa: componentes en línea para la barra
  de cada pantalla, la franja del borde y la sonda de depuración, y la lógica que
  no depende de la interfaz en `PeekModel.js`.
- Lo que solo sirve para el registro de depuración ya no hace nada con el
  registro desactivado.
- `check.py` organiza las pruebas por nombre en una sola lista, con `--only` y
  `--repeat`, y antes de empezar comprueba que no le falte nada; si falta algo,
  te dice cómo arreglarlo.
- README y novedades en inglés y en español, con logo, captura y vídeos propios.

### Nuevo

- Pruebas unitarias de `PeekModel.js`: `node --test tests/`.
- `check.py --reconnect` mantiene abierta una ventana etiquetada a pantalla
  completa mientras se reconecta el monitor.

### Eliminado

- Las llamadas IPC manuales `probe` y `nudge`. La sonda que apunta dónde está el
  ratón al salir de la barra sigue funcionando con el registro de depuración
  activo.
- Las capturas y la demo que venían de Top Bar Peek.

## [0.2.1] - 2026-11-19

### Correcciones

- Una ventana a pantalla completa ya cerrada podía quedarse en la lista de
  ventanas de Quickshell e impedir que la barra apareciera en esa pantalla hasta
  reiniciar el shell. Ahora la información sale directamente de
  `hyprctl clients -j`.

## [0.2.0] - 2026-11-18

### Nuevo

- Las ventanas con la etiqueta `no-bar-peek` que están a pantalla completa o
  maximizadas se quedan con el borde superior para su propia barra: ahí la barra
  no aparece, si estaba fuera se esconde y la franja del borde no recoge el
  ratón.

## [0.1.0] - 2026-11-18

Primera versión como Top Bar Plus, adaptada de Top Bar Peek a Omarchy 4.5.

### Nuevo

- Identificador propio, `io.github.kuroge.topbar-plus`, para que pueda convivir
  con Top Bar Peek.
- `omarchy shell topbar-plus status` y un registro de depuración que se activa
  con `setDebug`.

### Correcciones

- En reposo ya no queda una capa transparente del tamaño de la pantalla por
  encima de las ventanas: la barra nativa conserva su posición y su capa hasta
  que tiene que aparecer.
- La barra responde al ratón cuando aparece sobre una ventana a pantalla
  completa.
- Se acabaron los parpadeos al entrar rápido desde el borde, al dejar el ratón
  pegado al borde y al cerrar un desplegable sobre la barra.
- Después de reconectar un monitor ya no se reserva espacio ni se empujan las
  ventanas hacia abajo.
- Ya no da error cuando desaparece la barra de un monitor.

[0.3.0]: https://github.com/Kuroge/omarchy-topbar-plus/releases/tag/v0.3.0
