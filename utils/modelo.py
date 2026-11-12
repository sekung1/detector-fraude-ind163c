"""Carga del modelo entrenado y de su metadata (umbral, variables, categorías y métricas)."""
import json
from functools import lru_cache
from pathlib import Path

import joblib

CARPETA_MODELOS = Path(__file__).resolve().parent.parent / "models"

# Nombres legibles para el formulario. Solo se muestran las variables que usa el modelo.
ETIQUETAS = {
    "CODIGO_POSTAL": "Código postal",
    "ESTADO_REGION": "Estado / región",
    "DOMINIO_CORREO": "Dominio de correo",
    "HORA_TRANSACCION_1": "Hora de la transacción (0–23)",
    "INDICADOR_BINARIO_VIS_1": "Indicador VIS 1",
    "INDICADOR_BINARIO_VIS_2": "Indicador VIS 2",
    "INDICADOR_BINARIO_XRN_1": "Indicador XRN 1",
    "INDICADOR_BINARIO_XRN_2": "Indicador XRN 2",
    "INDICADOR_BINARIO_XRN_3": "Indicador XRN 3",
    "INDICADOR_BINARIO_XRN_4": "Indicador XRN 4",
    "CONTEO_XRN_5": "Conteo XRN 5",
    "NIVEL_ORDINAL_VAR_1": "Nivel ordinal VAR 1",
    "INDICADOR_BINARIO_VAR_2": "Indicador VAR 2",
    "MEDIDA_CONTINUA_VAR_3": "Medida continua VAR 3",
    "NIVEL_DISCRETO_VAR_4": "Nivel discreto VAR 4",
    "CONTEO_VAR_5": "Conteo VAR 5",
    "MONTO_TRANSACCION": "Monto de la transacción",
}


@lru_cache(maxsize=1)
def cargar_modelo():
    return joblib.load(CARPETA_MODELOS / "modelo_fraude.pkl")


@lru_cache(maxsize=1)
def cargar_metadata():
    with open(CARPETA_MODELOS / "metadata.json", encoding="utf-8") as fh:
        return json.load(fh)


def variables_modelo():
    meta = cargar_metadata()
    return meta["variables_numericas"] + meta["variables_categoricas"]


def etiqueta(variable):
    return ETIQUETAS.get(variable, variable.replace("_", " ").title())
