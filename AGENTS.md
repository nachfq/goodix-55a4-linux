# Instrucciones de trabajo

Este proyecto investiga Goodix USB 27c6:55a4 en una ThinkPad E14 Gen 2.
El propietario quiere aprender paso a paso. Explicar cada avance en español.

- Antes de descargar fuentes adicionales, instalar paquetes o realizar cambios
  persistentes en el sensor, explicar las operaciones concretas y acordar el alcance
  con el propietario. No inferir autorización de una etapa futura por haber
  autorizado una anterior. Respetar autorizaciones explícitas de la conversación.
- La etapa actual es auditoría. No ejecutar instaladores comunitarios ni utilidades
  de provisión. No tocar PAM, sudo, bloqueo o servicios como parte de esta etapa.
- Distinguir observación local, afirmación de terceros e hipótesis. Vincular cada
  hallazgo a un commit y archivo; no presentar una lectura parcial como auditoría completa.
- No publicar imágenes de huellas, plantillas, dumps, capturas USB, secretos ni
  logs sin revisar. Usar rutas locales ignoradas para datos experimentales.
- Conservar atribuciones y revisar licencias antes de incorporar código ajeno.
- Separar descarga, compilación, acceso USB, provisión e instalación en pasos
  revisables. Registrar errores y timeouts como pruebas inconclusas, no como
  rechazos biométricos correctos.
- Leer README.md y docs/ antes de proponer cambios. Mantener la documentación
  coherente con el estado real, sin marcar pruebas futuras como realizadas.
