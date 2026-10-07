# Goodix 55a4 en Linux

Investigación y desarrollo paso a paso para usar el lector **Goodix USB
`27c6:55a4`** de una **Lenovo ThinkPad E14 Gen 2** en Linux.

Primero vamos a auditar el trabajo comunitario, entender el protocolo y medir
el comportamiento. Con esa evidencia decidiremos si mantener un parche sobre
libfprint o desarrollar los componentes que falten.

**Estado: auditoría inicial. Todavía no hay un controlador propio ni una
instalación probada en esta notebook.** Este repositorio empieza con documentación
original; no contiene copias de los controladores ni ejecuta instaladores.

## Punto de partida

| Elemento | Estado al 2026-10-07 | Evidencia |
| --- | --- | --- |
| Notebook | ThinkPad E14 Gen 2, modelo `20TBS10100` | Informado por el propietario |
| Sistema | Omarchy, basado en Arch Linux | Informado por el propietario |
| Sensor USB | `27c6:55a4` | Reconfirmado con `lsusb -d 27c6:55a4` |
| libfprint | `libfprint-git 1:1.94.100.r10.g6f9479c-1` | Reconfirmado con `pacman -Q` |
| fprintd | `1.94.5-2` | Reconfirmado con `pacman -Q` |
| Detección por fprintd | `No devices available` | Resultado previo informado; no repetido en esta etapa |
| Soporte oficial | No figuraba al consultarlo previamente | Pendiente de consultar nuevamente |

Que USB detecte el dispositivo no demuestra que libfprint pueda inicializarlo.
La primera meta es lograr detección, lectura, registro y verificación, incluyendo
rechazo de dedos diferentes al registrado.

## Recorrido

1. [Auditoría inicial de la copia comunitaria](docs/auditoria-inicial.md):
   evidencia, hallazgos y preguntas abiertas.
2. [Fuentes y revisiones](docs/fuentes.md): qué código está disponible y qué falta revisar.
3. [Plan por etapas](docs/plan.md): próximos pasos y criterios de prueba.

Antes de descargar más fuentes, instalar dependencias o escribir en el sensor,
se explicará la operación concreta, su propósito y sus efectos al propietario.
La autorización de una etapa no autoriza automáticamente la siguiente.

PAM, desbloqueo y sudo quedan para después de verificar el reconocimiento.
Passkeys y autorización de firmas requieren integraciones adicionales. fprintd
no las habilita por sí solo; las firmas de commits seguirían usando claves SSH
o GPG y una eventual integración biométrica autorizaría su uso.

## Datos de las pruebas

Este repo es público. Se publicarán código, metodología y resultados agregados
revisados. Las imágenes de huellas, plantillas, capturas USB y volcados del sensor
se mantendrán fuera del historial. `.gitignore` ayuda a evitar inclusiones
accidentales, pero no reemplaza revisar lo que se va a subir.

## Procedencia

El punto de partida es el trabajo de
[Hydrogell](https://github.com/Hydrogell/goodix-27c6-55a4-fingerprint-linux),
basado en [TheWeirdDev/libfprint](https://github.com/TheWeirdDev/libfprint/tree/55b4-experimental)
y [goodix-fp-dump](https://github.com/goodix-fp-linux-dev/goodix-fp-dump).
También se evaluará [GuNanOvO/goodix-55x4-linux](https://github.com/GuNanOvO/goodix-55x4-linux).
El proyecto oficial es [libfprint](https://gitlab.freedesktop.org/libfprint/libfprint).

Todavía no se incorporó código de terceros. Antes de hacerlo se revisarán las
licencias de cada componente y se conservarán sus atribuciones.
