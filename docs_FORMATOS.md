# Formatos de reporte por época (referencia técnica)

Los cuadres de ventas diarios cambiaron de formato ~5 veces desde 2019. El
parser (`src/extract.py`) **no** depende del nombre de archivo (hay erratas,
copias, "(2)", "- COPIA", `.xls`/`.ods`/`.pdf` mezclados); detecta el producto y
la fecha por el **contenido** y ancla la venta en etiquetas estables.

| Época | GLP (archivo / formato) | GNV/GNL (archivo / formato) | Dónde está la venta |
|---|---|---|---|
| **2019** | `ORIGINAL GLP.xls`, `DD-MM-YY.xls` — libro mensual, 1 hoja por día (`Hoja1 (N)`) | — (GNV inicia 2023) | Bloque `RESUMEN VENTAS` → fila `TOTAL` (galones, monto) |
| **2020–2022** | `GLP <MES>.xls` — libro mensual, hojas `Día N` | — | `RESUMEN VENTAS` → `TOTAL GLP` (galones, monto); `Precio:` |
| **2023** | `GLP <MES>.xls` / `PLANILLA GLP <MES>` (a veces `.ods`) — hojas `Día (N)` | `GNV <MES>.xls` / `PLANILLA GNV <MES>` — hojas `Día (N)` | GLP: `TOTAL GLP`; GNV: `TOTAL GNL` (m³, monto) |
| **2024** | `PLANILLA <MES> GLP A11.xls` — hojas `Día_N` + hoja `Resumen`/lubricantes, `Tasa Dólar` | `PLANILLA <MES> GNV.xls`/`.ods` | igual; más tipos de pago (Tarjeta Martí, Tickets) |
| **2025–2026** | **PDF diario** `D-M-YY.pdf` (sistema `cuadrestg.marti.do`) | `CUADRE GNV <MES> AAAA.ods` — hojas `Día (N)`, fechas como serial de Excel | GLP PDF: pág.1 `Venta Total`/`Precio`, pág.7 `VENTAS BRUTAS`/`NETAS` (gls + RD$), pág.6 mezcla de pago. GNV: `TOTAL GNL` |

## Reglas de extracción

- **Producto**: contiene `TOTAL GNL` / `METROS CUBICOS` / `TROPIGAS NATURAL` → GNV;
  si no, `TOTAL GLP` / `INVENTARIO GLP` / `Producto principal GLP` → GLP.
- **Fecha**: celda `Fecha:` (datetime, serial de Excel, o texto D/M/AA) — en PDF,
  `Hora de finalización`. Nunca se confía en la carpeta (llegan tarde, hay copias,
  varios PDF por día).
- **Venta**: volumen y monto = los dos números a la derecha de la fila TOTAL del
  bloque `RESUMEN VENTAS` (o `VENTAS BRUTAS` en PDF).
- **Unidades**: GLP en galones; GNV en metros cúbicos (m³). Monto siempre en RD$.

## Cosas raras que el sistema maneja

- Hojas de días futuros vacías (volumen 0) → se descartan.
- Reinicios/errores de medidor (p. ej. `-57,977`) → quedan en campos de control,
  no contaminan la venta; se marcan en `anomalies.csv`.
- Cada libro mensual repite los días previos (acumulativo) → se deduplica por
  `(producto, fecha)` conservando la versión más reciente/corregida.
- Archivos de otro mes dentro de una carpeta (p. ej. `MAYO 2024 GLP.xls` dentro
  de `2024-06/`) → fechas fuera de ventana se excluyen como "fantasmas".
- Lagunas conocidas: sin nov–dic 2019, gran parte de 2022, meses futuros vacíos.
