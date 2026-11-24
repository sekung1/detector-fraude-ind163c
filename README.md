# Detector de Fraude en Transacciones Digitales

Proyecto Semestral de **IND163C – Análisis de Negocios** (USM, 2026-02).
Es una aplicación web en Flask que usa un modelo de clasificación para estimar el riesgo de que una transacción digital sea fraudulenta, **antes de autorizar el pago**.

**Aplicación publicada:** https://detector-fraude-ind163c.onrender.com
**Repositorio:** https://github.com/sekung1/detector-fraude-ind163c

> En el plan gratuito de Render la aplicación se suspende tras 15 minutos sin uso; la primera visita después puede tardar ~1 minuto en cargar.

## Objetivo y problema de negocio

Una entidad financiera o procesador de pagos quiere identificar transacciones fraudulentas antes de autorizarlas. Busca reducir las pérdidas por fraude **sin bloquear innecesariamente operaciones legítimas**.

El problema es de **clasificación binaria**: dada una transacción, predecir si es `FRAUD` o `LEGIT`.

## Dataset

- **Datos:** Dataset 1, *Detección de Fraude en Transacciones Digitales*. Son 10.000 transacciones con 19 variables anonimizadas (geográficas, correo, horas, indicadores binarios, conteos, montos) y la variable objetivo `TIPO_TRANSACCION`.
- **Desbalance:** solo el **2,08%** de las transacciones son fraude.
- **Limpieza:**
  - Se eliminaron 89 filas duplicadas.
  - Se eliminaron 2 variables redundantes, cada una con correlación > 0,99 con otra.
- **Partición:** Train/Test 80/20, estratificada, con semilla 2026.

## Hallazgo principal y variables utilizadas

El análisis (pruebas Chi-cuadrado / Mann-Whitney y comparación de conjuntos de variables con validación cruzada) mostró dos cosas:

- **El riesgo de fraude depende de la región de origen.** Algunas regiones tienen tasas de 15% a 42%, frente a un promedio de 2,1%.
- **Las variables transaccionales no tienen poder predictivo.** Un modelo entrenado solo con ellas obtiene un ROC-AUC de 0,50, equivalente al azar.

Por eso el modelo final usa **solo `ESTADO_REGION`**, que fue el conjunto con mejor AUC y menor variabilidad.

## Modelo seleccionado

Se evaluaron 4 modelos con `GridSearchCV` (validación cruzada de 5 folds dentro de train y métrica ROC-AUC):

| Modelo | AUC validación cruzada | ROC-AUC test |
|---|---|---|
| **Regresión Logística** | **0,726** | 0,816 |
| Árbol de Decisión (CART) | 0,721 | 0,810 |
| Random Forest | 0,726 | 0,803 |
| Gradient Boosting | 0,723 | 0,818 |

**Modelo final: Regresión Logística.** Los cuatro modelos rinden prácticamente igual, así que se eligió el más simple e interpretable.

- **Hiperparámetros:** `C = 0.1`, `penalty = 'l2'`, `class_weight = 'balanced'`, `solver = 'liblinear'`.
- **Preprocesamiento:** `OneHotEncoder(min_frequency=10, handle_unknown='infrequent_if_exist')` dentro de un `Pipeline`.
- **Umbral de decisión:** **0,74**. Es el que maximiza el F-Score en la validación cruzada de train.

| Métrica (umbral 0,74) | K-Fold K=5 (train) | Test |
|---|---|---|
| Sensitivity | 40,6% ± 10,6 | 48,8% |
| Precision | 19,4% ± 5,2 | 22,2% |
| Specificity | 96,4% ± 0,6 | 96,4% |
| F-Score | 26,1% ± 6,7 | 30,5% |
| ROC-AUC | 72,6% ± 6,4 | 81,6% |

**Sobre el puntaje de riesgo:** el modelo se entrenó con clases balanceadas, así que su salida es un **puntaje de riesgo (0–100)** que ordena las transacciones según su riesgo. **No es una probabilidad calibrada.**

**Limitaciones:**
- El modelo no distingue entre transacciones de una misma región.
- Las regiones no vistas (o con menos de 10 casos) se tratan como "infrecuentes". Ese grupo tiene una tasa de fraude alta, por lo que reciben un puntaje alto.

## Funcionalidades de la aplicación

| Ruta | Descripción |
|---|---|
| `/` | Formulario para evaluar una transacción: veredicto, puntaje de riesgo, nivel de riesgo y tasa histórica de la región. |
| `/lote` | Carga de un archivo `.csv` o `.xlsx` (hasta 5.000 filas) y descarga de los resultados. Hay un archivo de ejemplo disponible. |
| `/modelo` | Métricas del modelo, comparación de candidatos y regiones de mayor riesgo. |
| `/api/predecir` | API JSON. Ejemplo: `POST {"ESTADO_REGION": "AR"}`. |
| `/health` | Verificación de estado, usada por Render. |

**Validación de entradas:**
- Campos obligatorios.
- Categorías no vistas: se aceptan con una advertencia.
- Tipo y tamaño de archivo (máximo 5 MB).
- Columnas faltantes.
- Errores 404, 413 y 500 con páginas propias.

## Estructura del proyecto

```
fraude-app/
├── app.py                 # Aplicación Flask (rutas)
├── requirements.txt       # Dependencias con versiones fijadas (iguales a las del entrenamiento)
├── .python-version        # Versión de Python para Render (3.12)
├── models/
│   ├── modelo_fraude.pkl  # Pipeline completo (preprocesamiento + modelo), exportado con joblib
│   └── metadata.json      # Umbral, variables, categorías, métricas y tasas históricas
├── utils/
│   ├── modelo.py          # Carga del modelo y de la metadata
│   ├── validacion.py      # Validación del formulario y de archivos por lote
│   └── prediccion.py      # Generación de predicciones y nivel de riesgo
├── templates/             # Plantillas Jinja: base, index, resultado, lote, modelo, error
├── static/                # CSS, JavaScript e ícono
└── data/
    └── ejemplo_lote.csv   # Archivo de ejemplo para la evaluación por lote
```

El modelo se entrena y exporta en el notebook del proyecto (`Proyecto_Deteccion_Fraude.ipynb`, entregado aparte).

## Ejecución local

Se necesita Python 3.12.

```bash
python3 -m venv .venv
source .venv/bin/activate          # En Windows: .venv\Scripts\activate
pip install -r requirements.txt
flask --app app run
```

Luego se abre http://127.0.0.1:5000 en el navegador.

## Despliegue en la nube (modalidad seleccionada)

La aplicación se despliega como **Web Service en Render**, conectada a este repositorio de GitHub:

| Parámetro | Valor |
|---|---|
| Runtime | Python 3 (versión tomada de `.python-version`) |
| Branch | `main` |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `gunicorn app:app` |
| Health Check Path | `/health` |

El repositorio no contiene contraseñas, tokens ni credenciales.

## Integrantes

Grupo N.º 1

| Integrante | Rol USM |
|---|---|
| Martín López | 202241516-9 |
| Constanza Donoso | 202260554-5 |
| Nicolás Araya | 202260596-0 |
| Antonio Quinteros | 202204576-0 |
