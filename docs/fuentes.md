# Fuentes y revisiones

Fecha del inventario: 2026-10-07. Solo se inspeccionó la copia local existente
de Hydrogell. No se descargaron los otros repos ni se actualizaron las fuentes.

| Proyecto | Revisión | Estado |
| --- | --- | --- |
| [Hydrogell/goodix-27c6-55a4-fingerprint-linux](https://github.com/Hydrogell/goodix-27c6-55a4-fingerprint-linux) | `fe27b4812d60b4709d3dfb2b72f1e1f2704ede18` | Copia local inspeccionada; árbol limpio según Git |
| [TheWeirdDev/libfprint](https://github.com/TheWeirdDev/libfprint/tree/55b4-experimental) | `d1ca62a801aa565e67d1a2a47aaa7a33232b7990` | Referencia fijada en los scripts de Hydrogell; código base no inspeccionado |
| [goodix-fp-linux-dev/goodix-fp-dump](https://github.com/goodix-fp-linux-dev/goodix-fp-dump) | `cc43bb3b3154a0bccc0412ae024013c7e1923139` | Referencia fijada en los scripts de Hydrogell; código no inspeccionado |
| [GuNanOvO/goodix-55x4-linux](https://github.com/GuNanOvO/goodix-55x4-linux) | Pendiente | Alternativa informada; no auditada |
| [libfprint oficial](https://gitlab.freedesktop.org/libfprint/libfprint) | Pendiente | Falta seleccionar una base actual para comparar |

El parche local `patches/55a4-driver.patch` tiene 1290 líneas y SHA-256:

```text
73720a4418ed7ceb640011f51d4f2bac206118bc480ab6f1784f6618b479ef15
```

El hash identifica el contenido revisado; no demuestra autoría ni seguridad.
Las estrellas, actividad y resultados publicados tampoco sustituyen una revisión
del código o pruebas independientes. No se verificaron sus valores actuales.

El archivo `LICENSE` de la copia de Hydrogell contiene LGPL 2.1. Esto no completa
la revisión de licencias de sus dependencias, archivos individuales o futuros
componentes derivados.
