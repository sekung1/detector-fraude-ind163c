"""Validación de entradas del formulario y de archivos por lote antes de predecir."""
import io

import pandas as pd

from .modelo import cargar_metadata, etiqueta, variables_modelo

MAX_FILAS_LOTE = 5000
EXTENSIONES_LOTE = {".csv", ".xlsx"}


class ErrorValidacion(Exception):
    """Error de entrada que se muestra al usuario."""


def _es_binaria(meta, col):
    return meta.get("rangos", {}).get(col) == [0.0, 1.0]


def campos_formulario():
    """Describe los campos que el formulario debe mostrar, según las variables del modelo."""
    meta = cargar_metadata()
    variables = variables_modelo()
    region_derivada = "CODIGO_POSTAL" in variables and "ESTADO_REGION" in variables
    campos = []
    for col in variables:
        if col == "ESTADO_REGION" and region_derivada:
            continue  # se deduce del código postal
        campo = {"nombre": col, "etiqueta": etiqueta(col)}
        if col in meta["variables_categoricas"]:
            opciones = meta["categorias"].get(col, [])
            if col == "DOMINIO_CORREO":
                campo.update(tipo="texto", sugerencias=opciones[:300])
            else:
                campo.update(tipo="select", opciones=_ordenar(opciones))
        elif _es_binaria(meta, col):
            campo.update(tipo="select", opciones=["0", "1"])
        else:
            minimo, maximo = meta.get("rangos", {}).get(col, [None, None])
            campo.update(tipo="numero", min=minimo, max=maximo)
        campos.append(campo)
    return campos, region_derivada


def _ordenar(valores):
    try:
        return sorted(valores, key=lambda v: float(v))
    except ValueError:
        return sorted(valores)


def validar_formulario(form):
    """Convierte el formulario en un DataFrame de una fila. Devuelve (df, advertencias)."""
    meta = cargar_metadata()
    variables = variables_modelo()
    fila, advertencias, errores = {}, [], []

    for col in variables:
        if col == "ESTADO_REGION" and "CODIGO_POSTAL" in variables:
            continue
        valor = (form.get(col) or "").strip()
        if not valor:
            errores.append(f"Falta completar «{etiqueta(col)}».")
            continue
        if col in meta["variables_categoricas"]:
            valor = valor.upper()
            if valor not in meta["categorias"].get(col, []):
                advertencias.append(
                    f"«{valor}» no aparece en los datos de entrenamiento para {etiqueta(col)}; "
                    "el modelo la trata como una categoría infrecuente."
                )
            fila[col] = valor
        else:
            try:
                numero = float(valor.replace(",", "."))
            except ValueError:
                errores.append(f"«{etiqueta(col)}» debe ser un número.")
                continue
            minimo, maximo = meta.get("rangos", {}).get(col, [None, None])
            if _es_binaria(meta, col) and numero not in (0.0, 1.0):
                errores.append(f"«{etiqueta(col)}» solo puede ser 0 o 1.")
                continue
            if minimo is not None and not (minimo <= numero <= maximo):
                advertencias.append(
                    f"{etiqueta(col)} = {numero:g} está fuera del rango visto en entrenamiento "
                    f"({minimo:g} a {maximo:g}); la predicción puede ser menos confiable."
                )
            fila[col] = numero

    if errores:
        raise ErrorValidacion(" ".join(errores))

    _completar_region(fila, variables, meta, advertencias)
    return pd.DataFrame([fila])[variables], advertencias


def _completar_region(fila, variables, meta, advertencias):
    if "CODIGO_POSTAL" in variables and "ESTADO_REGION" in variables:
        postal = str(fila["CODIGO_POSTAL"])
        region = meta["postal_a_region"].get(postal)
        if region is None:
            region = "DESCONOCIDA"
            advertencias.append("El código postal no tiene una región asociada en los datos de entrenamiento.")
        fila["ESTADO_REGION"] = region


def leer_lote(archivo):
    """Lee un CSV o Excel subido por el usuario y devuelve (df_original, df_modelo, advertencias)."""
    nombre = (archivo.filename or "").lower()
    extension = nombre[nombre.rfind("."):] if "." in nombre else ""
    if extension not in EXTENSIONES_LOTE:
        raise ErrorValidacion("El archivo debe ser .csv o .xlsx.")
    contenido = archivo.read()
    if not contenido:
        raise ErrorValidacion("El archivo está vacío.")
    try:
        if extension == ".csv":
            df = pd.read_csv(io.BytesIO(contenido), sep=None, engine="python", dtype=str)
        else:
            df = pd.read_excel(io.BytesIO(contenido), dtype=str)
    except Exception:
        raise ErrorValidacion("No se pudo leer el archivo. Revisa que sea un CSV o Excel válido.")

    if df.empty:
        raise ErrorValidacion("El archivo no tiene filas.")
    if len(df) > MAX_FILAS_LOTE:
        raise ErrorValidacion(f"El archivo tiene {len(df)} filas; el máximo es {MAX_FILAS_LOTE}.")

    df.columns = [str(c).strip().upper() for c in df.columns]
    meta = cargar_metadata()
    variables = variables_modelo()
    advertencias = []

    requeridas = [c for c in variables if not (c == "ESTADO_REGION" and "CODIGO_POSTAL" in variables)]
    faltantes = [c for c in requeridas if c not in df.columns]
    if faltantes:
        raise ErrorValidacion("Faltan columnas en el archivo: " + ", ".join(faltantes) + ".")

    modelo_df = pd.DataFrame(index=df.index)
    for col in requeridas:
        serie = df[col].fillna("").astype(str).str.strip()
        if col in meta["variables_categoricas"]:
            serie = serie.str.upper().str.replace(r"\.0$", "", regex=True)
            vacias = (serie == "").sum()
            if vacias:
                raise ErrorValidacion(f"La columna {col} tiene {vacias} celda(s) vacía(s).")
            nuevas = (~serie.isin(meta["categorias"].get(col, []))).sum()
            if nuevas:
                advertencias.append(f"{nuevas} fila(s) con {col} no vista en entrenamiento (se tratan como infrecuentes).")
            modelo_df[col] = serie
        else:
            numeros = pd.to_numeric(serie.str.replace(",", ".", regex=False), errors="coerce")
            malas = numeros.isna().sum()
            if malas:
                raise ErrorValidacion(f"La columna {col} tiene {malas} valor(es) vacío(s) o no numérico(s).")
            modelo_df[col] = numeros

    if "CODIGO_POSTAL" in variables and "ESTADO_REGION" in variables:
        if "ESTADO_REGION" in df.columns:
            modelo_df["ESTADO_REGION"] = df["ESTADO_REGION"].fillna("").astype(str).str.strip().str.upper()
        else:
            modelo_df["ESTADO_REGION"] = modelo_df["CODIGO_POSTAL"].map(meta["postal_a_region"]).fillna("DESCONOCIDA")
            advertencias.append("La región se dedujo a partir del código postal.")

    return df, modelo_df[variables], advertencias
