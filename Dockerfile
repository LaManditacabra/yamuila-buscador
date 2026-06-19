# Usar la imagen oficial de Playwright para Python que ya incluye todos los navegadores y sus dependencias
FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

# Establecer directorio de trabajo
WORKDIR /app

# Copiar e instalar dependencias de Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código del proyecto
COPY . .

# Exponer el puerto en el que corre FastAPI
EXPOSE 8000

# Comando para iniciar la aplicación
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
