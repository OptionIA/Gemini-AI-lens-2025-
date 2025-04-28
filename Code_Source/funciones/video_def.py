import cv2
import PIL.Image
import io
import base64
import asyncio

def get_frame(cap):
    """
    get frame
    """
    ret, frame = cap.read()
    if not ret:
        return None
        
    img = PIL.Image.fromarray(frame)
##    img.thumbnail([1024, 1024])  # Redimensionar manteniendo la proporción
    
    image_io = io.BytesIO()
    img.save(image_io, format="jpeg")
    image_io.seek(0)
    
    mime_type = "image/jpeg"
    image_bytes = image_io.read()
    
    return {
        "mime_type": mime_type,
        "data": base64.b64encode(image_bytes).decode()
    }

async def setup_video_capture():
    """
    Inicializa la captura de video
    
    Returns:
        cv2.VideoCapture: Instancia de VideoCapture inicializada
    """
    return await asyncio.to_thread(cv2.VideoCapture, 0)

async def capture_frames(cap, out_queue):
    """
    Captura frames continuamente y los envía a la cola de salida
    
    Args:
        cap: Instancia de cv2.VideoCapture
        out_queue: Cola asíncrona para enviar los frames procesados
    """
    try:
        while True:
            frame = await asyncio.to_thread(get_frame, cap)
            if frame is None:
                break
                
            await out_queue.put(frame)
    finally:
        cap.release()

def release_capture(cap):
    """
    Libera los recursos de la captura de video
    
    Args:
        cap: Instancia de cv2.VideoCapture a liberar
    """
    if cap is not None:
        cap.release()