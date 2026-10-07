# Plan por etapas

Cada etapa termina con evidencia revisable y una explicación del siguiente paso.
No se ejecutará el instalador comunitario como atajo para reunirlas.

## 0. Punto de partida — realizado

- Registrar hardware y versiones, distinguiendo datos informados y comprobados.
- Identificar la revisión local y el hash del parche.
- Publicar la revisión preliminar y las preguntas abiertas.

## 1. Completar auditoría de fuentes — propuesta, aún no ejecutada

Primero revisar el resto del parche local. Luego proponer la descarga de los
dos repos que requiere, bajo `work/`, a estos commits exactos:

- TheWeirdDev/libfprint: `d1ca62a801aa565e67d1a2a47aaa7a33232b7990`.
- goodix-fp-linux-dev/goodix-fp-dump: `cc43bb3b3154a0bccc0412ae024013c7e1923139`.

La descarga propuesta solo guardaría fuentes; no ejecutaría setup, pip, Meson,
Python del proyecto ni operaciones sobre el USB. Antes de hacerla se explicarán
los comandos y se acordará ese alcance con el propietario.

Con las fuentes disponibles:

- Seguir `init_device → check_psk → write_psk` hasta los mensajes USB; inventariar
  escrituras de claves, firmware, configuración y cualquier otro estado persistente.
- Revisar encuadre, longitudes, checksums, timeouts, cancelación y memoria en C/C++.
- Revisar PSK, negociación TLS, adquisición de imágenes y comparación SIGFM.
- Revisar dependencias de compilación/ejecución, licencias y divergencias del upstream.
- Comparar la alternativa de GuNanOvO mediante una propuesta de consulta separada.

Salida: mapa de operaciones y riesgos concretos, dependencias reproducibles y
decisión fundamentada sobre qué componentes conservar. No elegir todavía entre
fork propio y reimplementación sin ese análisis.

## 2. Compilación local

Preparar una compilación sin privilegios y sin instalar en el sistema. Identificar
antes las dependencias que falten y explicar cualquier instalación propuesta.
Comprobar aplicación del parche, construcción y compatibilidad con fprintd.
Compilar código no demuestra que sus operaciones sobre hardware sean seguras.

## 3. Primer acceso al sensor

Explicar previamente la secuencia exacta y qué cambia. Revisar incluso la ruta de
inicialización: un programa llamado «lectura» puede enviar comandos de configuración.
Si necesita provisión persistente, detenerse antes de ella para presentar slot,
payload, condiciones previas, límites de recuperación y evidencia disponible.
No prometer reversibilidad sin demostrarla.

Objetivo: enumeración por el controlador y adquisición controlada. Las imágenes
quedan en almacenamiento local privado y fuera de Git.

## 4. Registro y verificación sin integrar PAM

Definir antes de empezar una matriz de ensayos con plantilla objetivo fija:

| Caso | Resultado esperado |
| --- | --- |
| Dedo registrado, distintas colocaciones | Coincidencia explícita |
| Otros dedos no registrados contra esa plantilla | No coincidencia explícita |
| Ningún dedo | Espera o timeout; nunca aceptación |
| Cancelación o fallo de comunicación | Error distinguible; prueba inconclusa |
| Reinicio de sesión/dispositivo, según operaciones ya autorizadas | Comportamiento repetible |

Como exploración inicial, proponer 20 intentos válidos del dedo registrado y 20
por cada uno de al menos dos dedos diferentes. Registrar condiciones, intentos
válidos, aceptaciones, rechazos, reintentos y fallos por separado. Congelar los
parámetros durante la serie; si cambian, iniciar una serie nueva.

Un falso positivo detiene el avance hacia autenticación. Cero falsos positivos
en una muestra pequeña no certifica una tasa de error baja ni resistencia a
suplantación. Publicar resultados agregados con sus denominadores, sin imágenes,
plantillas ni capturas USB. Los logs completos se revisan antes de compartirlos.

## 5. Integraciones posteriores

Solo después de evaluar los resultados se propone instalación mantenible e
integración con desbloqueo o sudo, con cambios y recuperación documentados.
Passkeys y autorización de claves SSH/GPG se investigan como proyectos separados.
