# Auditoría inicial — 2026-10-07

## Alcance y conclusión provisional

Lectura estática de los scripts de preparación, instalación, desinstalación,
provisión de clave, compilación, pruebas y CI de la copia local de Hydrogell,
más secciones relevantes del parche y la documentación. Revisión
`fe27b4812d60b4709d3dfb2b72f1e1f2704ede18`.

No es una auditoría completa del controlador ni una certificación de seguridad.
No se ejecutaron scripts comunitarios, compiladores ni comandos de provisión.
No se instalaron paquetes ni se modificaron servicios, PAM o el sensor.
Las comprobaciones del sistema se limitaron a listar el dispositivo USB y las
versiones de los dos paquetes relevantes.

La instalación comunitaria reúne acciones que este proyecto quiere evaluar por
separado. El próximo paso razonable es completar la revisión de fuentes antes
de considerar ejecución sobre hardware.

## Hallazgos reproducibles en el código disponible

Los enlaces siguientes fijan la revisión inspeccionada.

### 1. Biblioteca separada, pero instalación con efectos adicionales

[`scripts/install-system.sh`, líneas 18–41](https://github.com/Hydrogell/goodix-27c6-55a4-fingerprint-linux/blob/fe27b4812d60b4709d3dfb2b72f1e1f2704ede18/scripts/install-system.sh#L18-L41)
copia la biblioteca a `/opt/libfprint-goodix/lib64` y crea
`/etc/systemd/system/fprintd.service.d/10-goodix55a4.conf`, que define
`LD_LIBRARY_PATH` para el servicio. Es una selección de biblioteca para fprintd;
no es aislamiento del dispositivo ni del proceso.

El mismo script detiene fprintd, ejecuta provisión de clave, puede cargar un módulo
SELinux y reinicia el servicio. Además,
[líneas 119–128](https://github.com/Hydrogell/goodix-27c6-55a4-fingerprint-linux/blob/fe27b4812d60b4709d3dfb2b72f1e1f2704ede18/scripts/install-system.sh#L119-L128)
intenta habilitar `with-fingerprint` si existe `authselect`. Esa condición no se
comprobó en esta notebook. El instalador completo excede nuestra etapa inicial.

### 2. La desinstalación no restaura todo el estado anterior

[`scripts/uninstall-system.sh`](https://github.com/Hydrogell/goodix-27c6-55a4-fingerprint-linux/blob/fe27b4812d60b4709d3dfb2b72f1e1f2704ede18/scripts/uninstall-system.sh)
elimina la biblioteca, el drop-in y el módulo SELinux. No restaura la clave del
sensor. También deja las plantillas y la configuración PAM. Por eso no hay
evidencia de una reversión completa al estado de fábrica.

### 3. Provisión automática; implementación de la escritura pendiente

[`scripts/provision_psk.py`, líneas 33–65](https://github.com/Hydrogell/goodix-27c6-55a4-fingerprint-linux/blob/fe27b4812d60b4709d3dfb2b72f1e1f2704ede18/scripts/provision_psk.py#L33-L65)
llama a `init_device(0x55a4)`, luego a `check_psk()` y, si esta devuelve falso,
a `write_psk()`. No solicita confirmación dentro de ese flujo.

Las funciones están en la dependencia todavía no inspeccionada. Los comentarios
afirman que se escribe solo `0xbb010003` y que Windows usa `0xbb010002`; no se ha
verificado el alcance efectivo de las operaciones ni una recuperación de la
clave original. Hay que revisar también los efectos de `init_device()`, no solo
la función cuyo nombre contiene `write`.

[`install-system.sh`, líneas 59–71](https://github.com/Hydrogell/goodix-27c6-55a4-fingerprint-linux/blob/fe27b4812d60b4709d3dfb2b72f1e1f2704ede18/scripts/install-system.sh#L59-L71)
permite continuar si falla la provisión. Un mensaje final de instalación no
demostraría que el sensor quedó utilizable.

### 4. Revisiones Git fijadas, dependencias Python sin fijar

[`install.sh`](https://github.com/Hydrogell/goodix-27c6-55a4-fingerprint-linux/blob/fe27b4812d60b4709d3dfb2b72f1e1f2704ede18/install.sh)
fija los dos repos base mediante SHA completos y comprueba el checkout.
Sin embargo, instala `pyusb`, `crcmod` y `python-periphery` sin versiones ni
hashes de paquetes. [`setup.sh`](https://github.com/Hydrogell/goodix-27c6-55a4-fingerprint-linux/blob/fe27b4812d60b4709d3dfb2b72f1e1f2704ede18/setup.sh)
agrega `numpy` y `opencv-python-headless` de la misma manera.

En `setup.sh` el pin se aplica solo al crear cada clon: un árbol existente no
vuelve a verificarse contra el SHA esperado. También ejecuta `git checkout -- .`
en la copia de libfprint, descartando cambios en archivos rastreados de ese árbol.
No conviene usarlo como entrada para mantener modificaciones propias.

### 5. El parche modifica adquisición, TLS y comparación

[`patches/55a4-driver.patch`](https://github.com/Hydrogell/goodix-27c6-55a4-fingerprint-linux/blob/fe27b4812d60b4709d3dfb2b72f1e1f2704ede18/patches/55a4-driver.patch)
afecta cinco archivos: `goodix.c`, `goodix55x4.c`, `goodix55x4.h`, `goodixtls.c`
y `sigfm.cpp`. Incluye cambios en transferencias y estados, procesamiento de
imágenes y reglas de comparación SIGFM. No alcanza con revisar el ID USB.

Las líneas 1176–1197 seleccionan `PSK:@SECLEVEL=0` y muestran configuración para
TLS 1.2. Las líneas 1198–1290 modifican el ordenamiento de correspondencias y la
comparación angular. Es necesario estudiar sus efectos sobre aceptación y rechazo.

La entrega de una imagen a `fpi_image_device_image_captured` se observa en la
línea 772 del parche. Esto respalda que esta implementación procesa imágenes en
el host. No prueba por sí solo todas las capacidades posibles del silicio.

### 6. El test de rechazo confunde fallos con rechazos válidos

[`scripts/fp-stress.sh`, líneas 70–83](https://github.com/Hydrogell/goodix-27c6-55a4-fingerprint-linux/blob/fe27b4812d60b4709d3dfb2b72f1e1f2704ede18/scripts/fp-stress.sh#L70-L83)
clasifica como `nomatch` cualquier salida sin `verify-match`, sin distinguir
timeout, error de comunicación o falta de dispositivo. Si se esperaba un rechazo,
ese resultado incrementa el contador de rechazos correctos.

La comprobación previa de dedos registrados ayuda, pero no elimina fallos durante
la sesión. Nuestras pruebas deberán contar los errores como inconclusos y exigir
un resultado explícito de no coincidencia para contabilizar rechazo.

### 7. La definición de CI no prueba el reconocimiento

El [workflow revisado](https://github.com/Hydrogell/goodix-27c6-55a4-fingerprint-linux/blob/fe27b4812d60b4709d3dfb2b72f1e1f2704ede18/.github/workflows/ci.yml)
define análisis de shell, sintaxis Python, aplicación del parche y compilación
en Fedora y Ubuntu, además de un control de archivos capturados. No define pruebas
del hardware ni de falsos positivos. No se consultaron resultados de ejecuciones
remotas; se inspeccionó únicamente la definición.

## Afirmaciones todavía pendientes de corroboración

| Afirmación | Evidencia disponible | Falta verificar |
| --- | --- | --- |
| PSK de 32 bytes cero | Documentación y comentarios de Hydrogell | Callback TLS y blob en las dependencias fijadas |
| Escritura persistente solo en `0xbb010003` | Comentarios y documentación del protocolo | Implementación transitiva completa y efectos del firmware |
| Convivencia con Windows | Relato del autor con pruebas limitadas | Evidencia independiente y recuperación; no inferirla solo por slots distintos |
| Plantillas bajo `/var/lib/fprint` | Documentación y script comunitario | Código/configuración del fprintd usado, formato y permisos efectivos |
| Registro y verificación funcionales | Resultados publicados por el autor | Pruebas locales reproducibles, separando errores de decisiones biométricas |
| Ausencia de soporte oficial | Consulta previa informada | Lista y código oficiales actuales |

Ninguno de estos puntos se probó con huellas en esta notebook.
