<div align="center">

<img src="assets/logo.svg" width="128" alt="Logo de Omarchy Top Bar Plus" />

# Omarchy Top Bar Plus

### La barra superior de Omarchy, oculta hasta que la necesitas

[![Versión](https://img.shields.io/badge/versi%C3%B3n-0.3.0-7fbbb3?style=for-the-badge)](CHANGELOG.es.md)
[![Omarchy 4.5](https://img.shields.io/badge/Omarchy-4.5-a7c080?style=for-the-badge)](https://omarchy.org/)
[![Hyprland 0.56](https://img.shields.io/badge/Hyprland-0.56-83c092?style=for-the-badge&logo=hyprland&logoColor=white)](https://hyprland.org/)
[![Quickshell 0.3](https://img.shields.io/badge/Quickshell-0.3-d699b6?style=for-the-badge&logo=qt&logoColor=white)](https://quickshell.org/)
[![Licencia MIT](https://img.shields.io/badge/licencia-MIT-dbbc7f?style=for-the-badge)](LICENSE)

**[⬇️ Instalar](#instalación)** ·
**[📋 Novedades](CHANGELOG.es.md)** ·
**[⚙️ Cómo funciona](#cómo-funciona)** ·
**[🧪 Pruebas](#pruebas-y-desarrollo)**

[English](README.md) · **Español**

</div>

---

Oculta la barra con el atajo de siempre y aprovecha la pantalla entera. Cuando
la necesites, lleva el ratón al borde superior del monitor y aparecerá por
encima de las ventanas; en cuanto lo apartes, se vuelve a esconder. Los widgets,
el tema, los menús y la bandeja son los de siempre: Top Bar Plus funciona dentro
del propio shell de Omarchy y aprovecha la barra que ya tienes.

![La barra apareciendo desde el borde superior y volviendo a esconderse](assets/demo.gif)

## Por qué

Entre otras cosas, para cuidar al máximo las pantallas OLED. Una barra fija es
lo peor que le puedes poner a un OLED: los mismos iconos y el mismo texto en los
mismos píxeles, hora tras hora, acaban dejando marca (el famoso quemado de
pantalla o *burn-in*). Omarchy ya permite ocultar la barra, pero entonces no la
tienes cuando te hace falta. Con Top Bar Plus vuelve en cuanto tocas el borde
superior, así que puedes tenerla oculta siempre: solo está en pantalla mientras
la usas, y el resto del tiempo esa franja muestra tus ventanas o el fondo, como
el resto de la pantalla.

## Qué ofrece

- 🛡️ **Pensada para pantallas OLED.** Nada de una barra fija quemándose en la
  parte de arriba del panel: solo aparece cuando la usas.
- 🖱️ **Cada monitor, a lo suyo.** Cada pantalla tiene su propia franja de dos
  píxeles en el borde superior y solo muestra su barra.
- 🪟 **Por encima de las ventanas, sin moverlas.** Cuando aparece no reserva
  espacio, así que las ventanas en mosaico se quedan donde están, incluso
  después de reconectar un monitor.
- 🧩 **Tu barra de siempre.** Widgets, distribución, colores, fuentes, fondo,
  menús, desplegables y bandeja son los de Omarchy. No se copia nada.
- 🎬 **También a pantalla completa.** Aparece sobre una ventana con `Super + F`
  y puedes usarla ahí mismo.
- 🙅 **Respeta a las apps con barra propia.** Si una ventana lleva la etiqueta
  `no-bar-peek`, mientras esté a pantalla completa o maximizada el borde es
  suyo.
- 🎯 **Sin parpadeos.** Ni al entrar rápido, ni al dejar el ratón pegado al
  borde, ni al cerrar un desplegable sobre la barra.
- ⏱️ **Como si viniera de serie.** Espera 120 ms después de que te vayas y se
  esconde en 140 ms con la misma animación que las tarjetas emergentes de
  Omarchy. Si quitas las animaciones con `omarchy toggle animations`, también
  lo respeta.
- 🪶 **Ligera.** Nada de comprobaciones periódicas ni procesos en segundo plano:
  una consulta rápida a `hyprctl` cuando cambian las ventanas, y nada en
  reposo.
- 🔍 **Fácil de revisar.** Una llamada que devuelve su estado en JSON y un
  registro de depuración que activas cuando quieras.
- ✅ **Probada a fondo.** Pruebas unitarias de la lógica y una prueba real que
  mueve un ratón de verdad en cada monitor.

| Sobre ventanas en mosaico | Sobre una ventana a pantalla completa |
|---|---|
| ![La barra apareciendo sobre dos ventanas en mosaico sin moverlas](assets/tiled.gif) | ![La barra apareciendo sobre una ventana a pantalla completa](assets/fullscreen.gif) |

![La barra a la vista sobre un escritorio vacío](assets/peek.jpg)

## Requisitos

| Componente | Versión |
|---|---|
| [Omarchy](https://omarchy.org/) | 4.5 |
| [Hyprland](https://hyprland.org/) | 0.56 o posterior |
| [Quickshell](https://quickshell.org/) | 0.3 |

No necesita nada más. Top Bar Plus se apoya en detalles internos de la barra de
Omarchy 4.5, así que con otras versiones puede que haga falta actualizar el
plugin. De momento solo funciona con la barra arriba.

## Instalación

```sh
omarchy plugin add https://github.com/Kuroge/omarchy-topbar-plus --enable --yes
```

Oculta la barra con **Super + Shift + Espacio**, como siempre, y lleva el ratón
al borde superior de una pantalla para que aparezca. Se queda mientras tengas el
ratón encima o uno de sus desplegables abierto. Con la barra visible todo
funciona como siempre, y que aparezca no cambia tu preferencia de tenerla
oculta.

Para actualizar, o para volver a la barra de serie:

```sh
omarchy plugin update io.github.kuroge.topbar-plus --yes
omarchy bar use omarchy.bar
omarchy plugin remove io.github.kuroge.topbar-plus --yes   # opcional, una vez de vuelta en la barra de serie
```

## Apps con barra propia

Algunas apps a pantalla completa tienen su propia barra, que baja desde el borde
superior; por ejemplo, la barra de sesión de RDPchy, un cliente de escritorio
remoto para Omarchy. RDPchy ya marca así sus ventanas de sesión de serie, así
que no tienes que hacer nada. Eso sí, todavía es privado, así que de momento no
lo encontrarás en GitHub.

Para cualquier otra app, ponle a sus ventanas la etiqueta `no-bar-peek` con una
regla de ventana de Hyprland, por ejemplo en `~/.config/hypr/hyprland.lua`. La
`class` que tienes que poner la ves con `hyprctl clients`:

```lua
o.window("^org\\.example\\.App$", { tag = "+no-bar-peek" })
```

Mientras una ventana etiquetada esté a pantalla completa o maximizada en el
espacio de trabajo activo de una pantalla, la barra de esa pantalla no aparece y
su franja no recoge el ratón: el borde es todo de la app. Si la barra estaba
fuera, se esconde. Cuando la ventana deja la pantalla completa, o si no lleva la
etiqueta, todo funciona como siempre.

## Qué ejecuta

Omarchy avisa de que los plugins se ejecutan sin aislamiento dentro del shell,
así que aquí tienes todo lo que hace Top Bar Plus aparte de su propio QML:

| Orden | Cuándo | Para qué |
|---|---|---|
| `hyprctl clients -j` | Cuando cambian las ventanas: pantalla completa, abrir, cerrar, mover o recargar la configuración | Saber qué ventanas etiquetadas están a pantalla completa |
| `hyprctl eval` con `hl.dsp.cursor.move` | Justo cuando la barra termina de bajar, o al cerrarse un desplegable, si el ratón no se ha movido | Dejar el puntero donde está para que Hyprland se entere de que la barra está debajo |
| `hyprctl cursorpos -j` | Solo con el registro de depuración activo, cuando el ratón sale de la barra | Apuntar dónde está realmente el puntero |

No se conecta a internet, no escribe ficheros y no toca tu configuración.
Mientras la barra está fuera ajusta su margen superior, su capa y su zona de
entrada, y mientras está oculta su modo de exclusión; al terminar lo deja todo
como estaba.

## Diferencias con Top Bar Peek

Top Bar Plus parte de [Top Bar Peek](https://github.com/WhiteHades/omarchy-topbar-peek),
que se escribió para Omarchy 4.0.4. En Omarchy 4.5:

| | Top Bar Peek | Top Bar Plus |
|---|---|---|
| Barra de Omarchy 4.5 | Choca con la posición nativa | Deja la posición nativa en reposo y solo la toma mientras la barra está fuera |
| En reposo | Una capa transparente del tamaño de la pantalla por encima de las ventanas | Nada por encima de las ventanas |
| Sobre una ventana a pantalla completa | La barra no responde al ratón | La barra funciona |
| Entrar rápido, dejar el ratón en el borde, cerrar un desplegable | Puede parpadear | Sin parpadeos |
| Reconectar un monitor | Da un error y empuja las ventanas hacia abajo | Sin problemas |
| Apps con barra propia | — | Etiqueta `no-bar-peek` |
| Estado y registro de depuración | — | `status`, `setDebug` |
| Pruebas | Prueba real | Pruebas unitarias y prueba real por apartados |

## Limitaciones conocidas

- La herencia de QML y la forma de localizar las barras nativas dependen de
  **detalles internos de la barra**, no de una API estable de Omarchy, así que
  alguna actualización de Omarchy puede obligar a actualizar el plugin.
- De momento, solo con la barra arriba. Si la tienes abajo o en un lateral,
  funciona como de serie.
- Hyprland no avisa cuando cambia una etiqueta. Si se la pones a mano a una
  ventana que ya está a pantalla completa, no se tendrá en cuenta hasta el
  siguiente cambio de ventanas: entrar o salir de pantalla completa, o abrir,
  cerrar o mover una ventana. Las etiquetas que pone una regla se aplican nada
  más abrirse la ventana.

## Cómo funciona

<details>
<summary>Para los curiosos</summary>

`Bar.qml` hereda de `qs.plugins.bar.Bar`. Localiza las ventanas de la barra
nativa y, en cada pantalla, añade una franja Wayland de dos píxeles en la capa
superior y un observador pasivo del ratón sobre el elemento que agrupa los
widgets. Así los widgets nativos, incluido el cajón de la bandeja, siguen
recibiendo el ratón como siempre. Igual que la barra nativa, se organiza en
componentes en línea: `PeekController` para cada pantalla, `EdgeTrigger` para la
franja y `LeaveProbe` para el registro de depuración. La lógica que no depende de
la interfaz está en `PeekModel.js`, que también usan las pruebas unitarias.

En Omarchy 4.5 cada barra nativa es una superficie transparente tan alta como su
pantalla que, al ocultarse, se aparca justo por encima, fuera de la vista. En
reposo el plugin no toca esa posición ni esa capa, así que de la barra no queda
nada encima de tus ventanas. Cuando tiene que aparecer, toma el control del
margen superior y de la capa: la coloca justo por encima del borde, la pasa a la
capa superior y la hace bajar. Cuando se ha vuelto a esconder, devuelve el
margen y la capa a la barra nativa. Una barra oculta no reserva espacio, pero la
que se crea al reconectar un monitor (por ejemplo, un OLED que se desconecta del
DisplayPort al despertar) puede quedarse con el modo de exclusión normal, así
que el plugin fuerza `ExclusionMode.Ignore` mientras la barra está oculta.

Mientras hay una ventana a pantalla completa, Omarchy deja la barra sin zona de
entrada para que su franja invisible no se quede con los clics de esa ventana.
Cuando la barra aparece por encima, el plugin le devuelve la entrada a la parte
visible y, cuando se esconde, vuelve a dejarla como la tenía Omarchy.

Hyprland no avisa a una superficie que se ha colocado bajo un ratón quieto hasta
que el ratón se vuelve a mover. Eso provocaría dos rebotes: si sales del borde
antes de que la barra termine de bajar, y si cierras un desplegable, cuya capa
ocupa toda la pantalla y se queda con el ratón mientras se desvanece. Para
evitarlos, la barra se mantiene mientras baja y mientras se desvanece el
desplegable. Si después sigue sin enterarse de que el ratón está encima, el
plugin deja el puntero donde está una sola vez para que Hyprland vuelva a mirar
qué hay debajo.

Para saber qué ventanas etiquetadas están a pantalla completa, el plugin
consulta `hyprctl clients -j` cuando cambian las ventanas, en vez de fiarse de la
lista de ventanas de Quickshell. Esa lista nunca borra una ventana si la
respuesta a una actualización llega después de que se haya cerrado, así que un
programa que sale de pantalla completa justo antes de cerrarse podía quedarse
ahí como si siguiera a pantalla completa hasta reiniciar el shell.

Cuando el ratón entra en la barra por debajo de la franja, la franja deja de
recoger el ratón. Los desplegables mantienen la barra fuera hasta que se cierran,
para que puedas llegar a ellos sin que desaparezca el sitio del que cuelgan.

</details>

## Estado y registro de depuración

```sh
omarchy shell topbar-plus status
omarchy shell topbar-plus setDebug true
journalctl --user --since "-5min" -o short-precise | grep topbar-plus
omarchy shell topbar-plus setDebug false
```

`status` devuelve en JSON el estado de cada pantalla. El registro viene
desactivado y se vuelve a desactivar al reiniciar el shell. Mientras está activo
apunta cuándo y por qué aparece o se esconde la barra, cuándo se retiene, cuándo
toma y devuelve el margen y la capa, el estado de pantalla completa y de
exclusión de la barra nativa, los espacios de trabajo en los que no debe
aparecer, dónde está realmente el ratón cuando la barra cree que se ha ido y las
pantallas que se conectan o desconectan.

## Pruebas y desarrollo

```sh
omarchy plugin validate .
node --test tests/
python check.py
python check.py --only fullscreen,suppressed --repeat 3
python check.py --monitor DP-1
python check.py --reconnect DP-2
python check.py --appearance
```

`node --test tests/` lanza las pruebas unitarias de `PeekModel.js`: qué ventanas
impiden que aparezca la barra y dónde está el ratón. No necesitan sesión gráfica
y tardan milisegundos.

`check.py` es la prueba real. Lánzala desde una sesión de Hyprland, con Top Bar
Plus como barra activa y colocada arriba, y no toques el ratón mientras dure: si
se mueve, la prueba se para. Necesita Python 3, `python-evdev`
(`omarchy pkg add python-evdev`), `foot` y permiso de escritura en `/dev/uinput`
para crear su ratón de prueba; por ejemplo, con
`sudo setfacl -m u:$USER:rw /dev/uinput`, que dura hasta que reinicies. Antes de
empezar comprueba que no falte nada y, si falta algo, te dice cómo arreglarlo.
Mover el puntero desde el compositor no basta para que una superficie note el
movimiento, así que usa eventos de ratón reales.

<details>
<summary>Las pruebas, en el orden en que se lanzan</summary>

Son los nombres que acepta `--only`.

| Prueba | En cada pantalla, con la barra oculta |
|---|---|
| `peek` | Aparecer desde el borde, pasar el ratón por los widgets, posición y escala en la capa superior, volver a entrar justo cuando se iba a esconder, bandeja, esconderse, vuelta a la posición nativa, y ventanas y espacio reservado sin cambios |
| `fast-entry` | Salir del borde antes de que la barra termine de bajar no la esconde |
| `edge-rest` | Dejar el ratón pegado al borde no la esconde |
| `popout-rest` | Cerrar un desplegable sobre la barra no la hace parpadear |
| `fullscreen` | Sobre una ventana `foot` temporal a pantalla completa, la barra responde al ratón al aparecer y devuelve la entrada al esconderse |
| `suppressed` | Sobre una ventana etiquetada a pantalla completa o maximizada, el borde ni hace aparecer la barra ni recoge el ratón |
| `suppressed-peeking` | Si una ventana etiquetada pasa a pantalla completa con la barra fuera, la barra se esconde |
| `suppressed-close` | Salir de pantalla completa y cerrar enseguida una ventana etiquetada, como hace un cliente de escritorio remoto, devuelve el borde, igual que dice Hyprland |
| `clock` | El desplegable del reloj mantiene la barra fuera y la suelta al cerrarse |
| `pinned` | Con la barra visible de siempre, se queda fija y la bandeja funciona |

Si el cajón de la bandeja está vacío, sus pruebas se saltan. Al acabar, la
prueba cierra sus ventanas, devuelve el foco a la tuya, cierra cualquier
desplegable y deja el ratón y la preferencia de barra oculta como estaban; cada
paso de la limpieza se hace aunque falle otro.

`--repeat` repite las pruebas elegidas varias veces, para pillar fallos que solo
salen de vez en cuando. `--monitor` prueba una sola salida, útil con monitores de
distinta escala. `--reconnect` apaga las pantallas 20 segundos, como haría el
gestor de inactividad, y prueba esa salida cuando se ha desconectado y ha vuelto;
falla si no llega a desconectarse. Durante la reconexión mantiene abierta una
ventana etiquetada a pantalla completa y, al final, comprueba que el plugin
coincide con Hyprland. `--appearance` repite la prueba con cada fondo de barra
(`opaque`, `glassy`, `none`), con el fondo de escritorio activado y desactivado,
y luego deja los dos ajustes como estaban. Al cambiar el fondo, Hyprland se
recarga si se activa o desactiva el desenfoque de `glassy`.

</details>

Si trabajas con una copia local, instálala y reinicia el shell, porque la recarga
en caliente de los plugins puede quedarse con QML antiguo en caché:

```sh
rsync -a --delete-excluded --include=manifest.json --include=Bar.qml --include=PeekModel.js \
  --include=LICENSE --exclude='*' ./ ~/.config/omarchy/plugins/io.github.kuroge.topbar-plus/
omarchy restart shell
```

## Créditos

- Autor: **Adrian Garcia Riera** ([Kuroge](https://github.com/Kuroge)).
- Basado en [Omarchy Top Bar Peek](https://github.com/WhiteHades/omarchy-topbar-peek),
  de **WhiteHades**, cuyo historial se conserva en este repositorio.
- [El plugin de ocultación automática de ericvrp](https://github.com/ericvrp/omarchy-bar-autohide),
  de **Eric van Riet Paap**, en el que se inspiraron la franja del borde y el
  observador del ratón originales.
- [Omarchy](https://omarchy.org/), [Hyprland](https://hyprland.org/) y
  [Quickshell](https://quickshell.org/), que hacen el trabajo duro.

## Licencia

Publicado con [licencia MIT](LICENSE), manteniendo los avisos de copyright de los
autores originales.
