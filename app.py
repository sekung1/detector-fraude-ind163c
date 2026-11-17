"""Aplicación web Flask para detectar transacciones fraudulentas con el modelo del proyecto IND163C."""
import base64
import logging
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_file

from utils.modelo import cargar_metadata, cargar_modelo, etiqueta, variables_modelo
from utils.prediccion import contexto_historico, predecir
from utils.validacion import MAX_FILAS_LOTE, ErrorValidacion, campos_formulario, leer_lote, validar_formulario

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5 MB por archivo
logging.basicConfig(level=logging.INFO)
RUTA_EJEMPLO = Path(__file__).resolve().parent / "data" / "ejemplo_lote.csv"

# Cargamos el modelo al iniciar para detectar errores de despliegue de inmediato.
cargar_modelo()
cargar_metadata()


@app.context_processor
def variables_globales():
    return {"meta": cargar_metadata(), "etiqueta": etiqueta}


@app.route("/")
def inicio():
    campos, region_derivada = campos_formulario()
    return render_template("index.html", campos=campos, region_derivada=region_derivada, valores={})


@app.route("/predecir", methods=["POST"])
def predecir_transaccion():
    campos, region_derivada = campos_formulario()
    try:
        df, advertencias = validar_formulario(request.form)
    except ErrorValidacion as e:
        return render_template(
            "index.html", campos=campos, region_derivada=region_derivada, valores=request.form, error=str(e)
        ), 400
    resultado = predecir(df)[0]
    fila = df.iloc[0].to_dict()
    return render_template(
        "resultado.html",
        resultado=resultado,
        entrada=fila,
        contexto=contexto_historico(fila),
        advertencias=advertencias,
    )


@app.route("/lote", methods=["GET", "POST"])
def lote():
    if request.method == "GET":
        return render_template("lote.html", max_filas=MAX_FILAS_LOTE, columnas=_columnas_lote())
    archivo = request.files.get("archivo")
    if archivo is None or not archivo.filename:
        return render_template("lote.html", max_filas=MAX_FILAS_LOTE, columnas=_columnas_lote(), error="Selecciona un archivo."), 400
    try:
        original, df_modelo, advertencias = leer_lote(archivo)
    except ErrorValidacion as e:
        return render_template("lote.html", max_filas=MAX_FILAS_LOTE, columnas=_columnas_lote(), error=str(e)), 400

    resultados = predecir(df_modelo)
    # Las columnas del resultado van primero para que se vean sin desplazar la tabla.
    columnas_resultado = ["PUNTAJE_RIESGO", "PREDICCION", "RIESGO"]
    salida = original.drop(columns=columnas_resultado, errors="ignore")
    salida.insert(0, "RIESGO", [r["riesgo"] for r in resultados])
    salida.insert(0, "PREDICCION", [r["decision"] for r in resultados])
    salida.insert(0, "PUNTAJE_RIESGO", [round(r["puntaje"] * 100, 1) for r in resultados])
    # El CSV se entrega dentro de la misma página (data URI) para no guardar datos en el servidor.
    csv_b64 = base64.b64encode(salida.to_csv(index=False).encode("utf-8-sig")).decode("ascii")

    resumen = {
        "total": len(salida),
        "fraudes": int(sum(r["es_fraude"] for r in resultados)),
        "riesgo_medio": int(sum(r["riesgo"] == "medio" for r in resultados)),
    }
    ordenado = salida.sort_values("PUNTAJE_RIESGO", ascending=False)
    return render_template(
        "lote.html",
        max_filas=MAX_FILAS_LOTE,
        columnas=_columnas_lote(),
        resumen=resumen,
        tabla=ordenado.head(200).to_dict(orient="records"),
        cabeceras=list(ordenado.columns),
        advertencias=advertencias,
        csv_b64=csv_b64,
    )


@app.route("/lote/ejemplo")
def ejemplo_lote():
    return send_file(RUTA_EJEMPLO, mimetype="text/csv", as_attachment=True, download_name="ejemplo_lote.csv")


@app.route("/modelo")
def modelo():
    return render_template("modelo.html")


@app.route("/api/predecir", methods=["POST"])
def api_predecir():
    datos = request.get_json(silent=True) or {}
    try:
        df, advertencias = validar_formulario({k: str(v) for k, v in datos.items()})
    except ErrorValidacion as e:
        return jsonify({"error": str(e)}), 400
    resultado = predecir(df)[0]
    return jsonify({**resultado, "umbral": cargar_metadata()["umbral"], "advertencias": advertencias})


@app.route("/health")
def health():
    return {"estado": "ok", "modelo": cargar_metadata()["modelo"]}


@app.errorhandler(404)
def no_encontrado(_):
    return render_template("error.html", titulo="Página no encontrada", mensaje="La dirección no existe."), 404


@app.errorhandler(413)
def archivo_grande(_):
    return render_template("error.html", titulo="Archivo demasiado grande", mensaje="El archivo supera los 5 MB."), 413


@app.errorhandler(500)
def error_interno(e):
    app.logger.exception(e)
    return render_template("error.html", titulo="Error interno", mensaje="Ocurrió un error inesperado. Intenta nuevamente."), 500


def _columnas_lote():
    variables = variables_modelo()
    if "CODIGO_POSTAL" in variables and "ESTADO_REGION" in variables:
        return [v for v in variables if v != "ESTADO_REGION"]
    return variables


if __name__ == "__main__":
    app.run(debug=True)
