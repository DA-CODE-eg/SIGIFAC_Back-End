# Motor facial de Sertiva para Railway

Descomprime el ZIP y sube su contenido a un repositorio de GitHub independiente. Deja el Dockerfile en la raíz.

1. En Railway crea un servicio desde GitHub Repository y usa la raíz del repositorio.
2. En Variables configura FACIAL_SERVICIO_TOKEN con un secreto aleatorio de al menos 32 caracteres. Para una prueba inicial usa FACIAL_COINCIDENCIA_MIN=0.65 y FACIAL_VIDA_MIN=0.90.
3. Genera un dominio HTTPS en Networking con puerto de destino 8081. La ruta /health requiere el encabezado X-Facial-Token.
4. En el backend de Sertiva usa ese dominio en FACIAL_SERVICIO_URL y el mismo FACIAL_SERVICIO_TOKEN. Configura FACIAL_CLAVE_HEX de forma separada y usa FACIAL_HABILITADO=true primero en pruebas.

El Dockerfile descarga y verifica los modelos durante la compilación. Prueba el flujo con cámara real y calibra los umbrales antes de usarlo en producción.
