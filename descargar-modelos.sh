#!/bin/sh
set -eu

destino=${1:-modelos}
mkdir -p "$destino"
temporal=$(mktemp "$destino/.modelo.XXXXXX")
trap 'rm -f "$temporal"' EXIT
trap 'exit 1' HUP INT TERM

descargar() {
  archivo=$1
  url=$2
  comprobador=$3
  suma=$4
  ruta="$destino/$archivo"
  if [ -f "$ruta" ] && printf '%s  %s\n' "$suma" "$ruta" | "$comprobador" -c --status; then
    printf '%s ya verificado\n' "$archivo"
    return
  fi
  curl -fLsS --retry 2 --connect-timeout 15 --max-time 180 "$url" -o "$temporal"
  printf '%s  %s\n' "$suma" "$temporal" | "$comprobador" -c --status
  chmod 644 "$temporal"
  mv "$temporal" "$ruta"
  printf '%s descargado y verificado\n' "$archivo"
}

zoo=https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models
descargar yunet.onnx "$zoo/face_detection_yunet/face_detection_yunet_2023mar.onnx" sha256sum 8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4
descargar sface.onnx "$zoo/face_recognition_sface/face_recognition_sface_2021dec.onnx" sha256sum 0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79
descargar anti-spoof-mn3.onnx "https://storage.openvinotoolkit.org/repositories/open_model_zoo/public/2022.1/anti-spoof-mn3/anti-spoof-mn3.onnx" sha384sum 6de4534964b723397b3e8c995cadcf43bc007cc2f9930b95ae25f76adccece5d1d4d058d0b15117b9e4a9f758424f92a
