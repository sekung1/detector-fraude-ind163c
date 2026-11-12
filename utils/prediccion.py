"""Generación de predicciones con el pipeline exportado desde el notebook."""
from .modelo import cargar_metadata, cargar_modelo


PUNTAJE_RIESGO_MEDIO = 0.5  # El modelo usa class_weight='balanced': 0,5 equivale a un riesgo igual al promedio.


def nivel_riesgo(puntaje, umbral):
    """alto: supera el umbral (se marca como fraude); medio: riesgo sobre el promedio; bajo: el resto."""
    if puntaje >= umbral:
        return "alto"
    if puntaje >= PUNTAJE_RIESGO_MEDIO:
        return "medio"
    return "bajo"


def predecir(df_modelo):
    """Devuelve, por fila, el puntaje de riesgo (salida de predict_proba), la decisión y el nivel de riesgo.

    Como el modelo se entrenó con clases balanceadas, el puntaje ordena el riesgo pero no es una
    probabilidad calibrada; por eso en la interfaz se muestra como "puntaje de riesgo".
    """
    modelo = cargar_modelo()
    umbral = cargar_metadata()["umbral"]
    puntajes = modelo.predict_proba(df_modelo)[:, 1]
    return [
        {
            "puntaje": float(p),
            "es_fraude": bool(p >= umbral),
            "decision": "FRAUD" if p >= umbral else "LEGIT",
            "riesgo": nivel_riesgo(float(p), umbral),
        }
        for p in puntajes
    ]


def contexto_historico(fila):
    """Tasa de fraude histórica (train) de la región y del código postal de la transacción."""
    meta = cargar_metadata()
    contexto = {"tasa_global": meta["tasa_fraude_global"]}
    region = fila.get("ESTADO_REGION")
    postal = fila.get("CODIGO_POSTAL")
    if region is not None:
        contexto["region"] = {"valor": region, **meta["tasas_region"].get(str(region), {})}
    if postal is not None:
        contexto["postal"] = {"valor": postal, **meta["tasas_postal"].get(str(postal), {})}
    return contexto
