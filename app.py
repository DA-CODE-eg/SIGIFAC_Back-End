"""Verificador local, sin llamadas a proveedores de biometría."""
import base64
import binascii
import hmac
import os
import threading

os.environ.setdefault("OPENCV_IO_MAX_IMAGE_PIXELS", "409600")
import cv2
import numpy as np
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field, StrictStr

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
secret = os.environ["FACIAL_SERVICIO_TOKEN"]
if len(secret) < 32:
    raise ValueError("FACIAL_SERVICIO_TOKEN debe tener al menos 32 caracteres")
coincidencia_min = float(os.environ["FACIAL_COINCIDENCIA_MIN"])
vida_min = float(os.environ["FACIAL_VIDA_MIN"])
if not (0 < coincidencia_min < 1 and 0 < vida_min < 1):
    raise ValueError("Configura umbrales validados")
detector = cv2.FaceDetectorYN.create(os.getenv("FACIAL_YUNET", "/modelos/yunet.onnx"), "", (640, 480), 0.85)
reconocedor = cv2.FaceRecognizerSF.create(os.getenv("FACIAL_SFACE", "/modelos/sface.onnx"), "")
pad = cv2.dnn.readNetFromONNX(os.getenv("FACIAL_PAD", "/modelos/anti-spoof-mn3.onnx"))
mutex = threading.Lock()


class Referencia(BaseModel):
    imagen: StrictStr = Field(max_length=180_000)


class Verificacion(BaseModel):
    referencia: list[float] | None = Field(default=None, min_length=128, max_length=128)
    capturas: list[StrictStr] = Field(min_length=1, max_length=3)
    direccion: str


def autenticar(token):
    if not token or not hmac.compare_digest(token, secret):
        raise HTTPException(401)


def rostro(captura):
    if len(captura) > 180_000 or not captura.startswith("data:image/jpeg;base64,"):
        raise HTTPException(422, "Imagen inválida")
    try:
        datos = base64.b64decode(captura.split(",", 1)[1], validate=True)
        imagen = cv2.imdecode(np.frombuffer(datos, dtype=np.uint8), cv2.IMREAD_COLOR)
    except (cv2.error, ValueError, binascii.Error):
        raise HTTPException(422, "Imagen inválida")
    if imagen is None:
        raise HTTPException(422, "Imagen inválida")
    alto, ancho = imagen.shape[:2]
    if alto > 640 or ancho > 640 or min(alto, ancho) < 160:
        raise HTTPException(422, "Dimensiones inválidas")
    detector.setInputSize((ancho, alto))
    _, caras = detector.detect(imagen)
    if caras is None or len(caras) != 1 or min(caras[0][2:4]) < 75:
        raise HTTPException(422, "Se requiere un rostro visible")
    cara = caras[0]
    vector = reconocedor.feature(reconocedor.alignCrop(imagen, cara)).flatten()
    if not np.isfinite(vector).all() or not np.linalg.norm(vector):
        raise HTTPException(422, "Rostro inválido")
    ojos = sorted([cara[4], cara[6]])
    pose = (cara[8] - np.mean(ojos)) / max(ojos[1] - ojos[0], 1)
    return imagen, cara, vector, pose


def vida(imagen, cara):
    x, y, w, h = cara[:4]
    x1, y1 = max(0, int(x)), max(0, int(y))
    x2, y2 = min(imagen.shape[1], int(x+w)), min(imagen.shape[0], int(y+h))
    if x2 <= x1 or y2 <= y1:
        return 0.0
    rgb = cv2.cvtColor(cv2.resize(imagen[y1:y2, x1:x2], (128, 128)), cv2.COLOR_BGR2RGB).astype(np.float32)
    rgb = (rgb - np.array([151.2405, 119.5950, 107.8395], np.float32)) / np.array([63.0105, 56.4570, 55.0035], np.float32)
    pad.setInput(np.ascontiguousarray(rgb.transpose(2, 0, 1)[None]))
    salida = pad.forward().flatten()
    if len(salida) != 2 or not np.isfinite(salida).all() or not np.isclose(salida.sum(), 1, atol=0.02):
        return 0.0
    return float(salida[0])


@app.get("/health")
def health(x_facial_token: str = Header(default="")):
    autenticar(x_facial_token)
    return {"listo": True, "version": "yunet-sface-mn3-v1", "capturaSinReferencia": True, "capturaUnica": True}


@app.post("/referencia")
def referencia(datos: Referencia, x_facial_token: str = Header(default="")):
    autenticar(x_facial_token)
    with mutex:
        _, _, vector, pose = rostro(datos.imagen)
        if abs(pose) > 0.16:
            raise HTTPException(422, "La foto de referencia debe ser frontal")
    return {"vector": vector.tolist()}


@app.post("/verificar")
def verificar(datos: Verificacion, x_facial_token: str = Header(default="")):
    autenticar(x_facial_token)
    if datos.referencia is None and len(datos.capturas) == 1:
        with mutex:
            imagen, cara, _, pose = rostro(datos.capturas[0])
            aprobada = abs(pose) <= 0.16 and vida(imagen, cara) >= vida_min
        return {"aprobada": aprobada, "version": "yunet-mn3-captura-v1"}
    if len(datos.capturas) != 3 or datos.direccion not in ("IZQUIERDA", "DERECHA") or len(set(datos.capturas)) != 3:
        return {"aprobada": False}
    referencia = np.array(datos.referencia, dtype=np.float32) if datos.referencia is not None else None
    if referencia is not None and (not np.isfinite(referencia).all() or not np.linalg.norm(referencia)):
        return {"aprobada": False}
    with mutex:
        medidas = [rostro(captura) for captura in datos.capturas]
        if referencia is None:
            referencia = medidas[0][2]
        poses = [medida[3] for medida in medidas]
        sentido = 1 if datos.direccion == "IZQUIERDA" else -1
        movimiento = abs(poses[0]) <= 0.16 and abs(poses[2]) <= 0.16 and sentido * (poses[1] - poses[0]) >= 0.14
        if not movimiento:
            return {"aprobada": False}
        for imagen, cara, vector, _ in medidas:
            similitud = float(np.dot(vector, referencia) / (np.linalg.norm(vector) * np.linalg.norm(referencia)))
            if not np.isfinite(similitud) or similitud < coincidencia_min or vida(imagen, cara) < vida_min:
                return {"aprobada": False}
    return {"aprobada": True, "version": "yunet-sface-mn3-v1"}
