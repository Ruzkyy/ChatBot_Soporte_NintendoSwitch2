# Chatbot RAG de manuales Nintendo Switch 2

Aplicación web desarrollada con Flask que responde preguntas sobre manuales oficiales de accesorios de Nintendo Switch 2. Utiliza recuperación aumentada por generación (RAG): busca fragmentos pertinentes en los documentos PDF y entrega ese contexto a un modelo de lenguaje de Groq para redactar una respuesta con referencia al manual y la página.

El chat también responde saludos, agradecimientos y despedidas comunes sin consultar los documentos.

## Contenido del proyecto

```text
.
├── app.py                 # Aplicación Flask y endpoint POST /chat
├── rag.py                 # Carga, fragmentación, búsqueda y generación RAG
├── requirements.txt       # Dependencias Python
├── .env.example           # Plantilla de variables de entorno
├── .gitignore             # Excluye secretos y archivos generados
├── documents/             # Manuales PDF consultados por el chatbot
├── templates/
│   └── index.html          # Interfaz web del chat
└── chroma/                # Índice vectorial creado al ejecutar (no se versiona)
```

Los PDF actuales en `documents/` son manuales de información importante, adaptador de corriente, cámara, funda y protector de pantalla, base, mandos Joy-Con 2, empuñadura de carga, volante, mando Pro y mando de Nintendo GameCube.

## Tecnologías

- **Python y Flask** para el servidor web y la API.
- **LangChain** para carga de PDF, división del texto, integración del vector store y conexión con Groq.
- **PyPDF** para extraer el texto de los manuales.
- **Sentence Transformers** con `paraphrase-multilingual-MiniLM-L12-v2` para generar embeddings localmente en CPU. La primera ejecución descarga el modelo y requiere conexión a Internet.
- **ChromaDB** para guardar los embeddings y recuperar fragmentos por similitud semántica.
- **Groq** con el modelo configurado en `GROQ_MODEL` para generar la respuesta. Se necesita una API key.

## Requisitos previos

- Python 3.10 o posterior. El proyecto se desarrolló y probó con Python 3.13.
- Git, si se va a clonar el repositorio.
- Conexión a Internet durante la instalación, la descarga inicial del modelo de embeddings y las consultas a Groq.
- Una API key de Groq. Se puede crear en [Groq Console](https://console.groq.com/).
- Archivos PDF con texto seleccionable dentro de `documents/`. Los manuales escaneados como imágenes pueden requerir OCR, que esta aplicación no incorpora.

## Instalación en Windows

Abre PowerShell en la carpeta del proyecto. Si todavía no has clonado el repositorio, primero clónalo y entra en él:

```powershell
git clone <URL_DEL_REPOSITORIO>
cd <CARPETA_DEL_REPOSITORIO>
```

Crea y activa un entorno virtual:

```powershell
py -m venv venv
.\venv\Scripts\Activate.ps1
```

Si PowerShell impide activar el entorno por la política de ejecución, permite scripts para la sesión actual y vuelve a activarlo:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\venv\Scripts\Activate.ps1
```

Instala las dependencias:

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Instalación en macOS o Linux

Desde la carpeta del repositorio:

```bash
git clone <URL_DEL_REPOSITORIO>
cd <CARPETA_DEL_REPOSITORIO>
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Configurar Groq

1. Copia `.env.example` a un archivo llamado `.env` en la raíz del proyecto.

   En PowerShell:

   ```powershell
   Copy-Item .env.example .env
   ```

   En macOS/Linux:

   ```bash
   cp .env.example .env
   ```

2. Abre `.env` y reemplaza el valor de ejemplo por tu clave:

   ```dotenv
   GROQ_API_KEY=tu_clave_real_de_groq
   GROQ_MODEL=openai/gpt-oss-120b
   EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
   ```

No compartas ni subas `.env` a GitHub. Está excluido mediante `.gitignore`; publica únicamente `.env.example`, que no contiene secretos. Si una clave real se publica por accidente, revócala desde Groq Console y crea otra.

## Ejecutar la aplicación

Activa el entorno virtual si aún no está activo y, desde la raíz del repositorio, ejecuta:

```bash
python app.py
```

Abre [http://127.0.0.1:5000](http://127.0.0.1:5000) en el navegador. Para detener el servidor, pulsa `Ctrl+C` en la terminal.

La primera pregunta que consulte los manuales carga los PDF, los divide en fragmentos de 500 caracteres con 50 caracteres de solapamiento, genera los embeddings y crea el índice local `chroma/`. La primera ejecución también puede descargar el modelo multilingüe, de varios cientos de MB. Las siguientes consultas reutilizan el índice persistente.

## Cómo funciona el RAG

1. El usuario escribe un mensaje en la interfaz de `templates/index.html`.
2. La interfaz envía el mensaje como JSON a `POST /chat`.
3. `app.py` valida la entrada y llama a `rag_pipeline()` en `rag.py`.
4. Si el mensaje es un saludo o una cortesía sencilla, el backend responde directamente.
5. En una pregunta sobre documentos, Sentence Transformers convierte la pregunta en un embedding y ChromaDB busca fragmentos similares.
6. Si la pregunta menciona la cámara, se limita la búsqueda al manual de cámara y se seleccionan fragmentos por coincidencia con los términos para reducir el contexto enviado al LLM.
7. El backend construye el contexto con el texto, el nombre del PDF y la página, y lo envía junto con la pregunta a Groq.
8. Flask devuelve la respuesta como JSON y la interfaz la muestra en el chat.

El modelo debe responder según el contexto recuperado; por eso una respuesta puede no ser exhaustiva si la búsqueda no recupera todos los pasajes relacionados. La aplicación no conserva el historial de mensajes como contexto entre solicitudes.

## Probar la API

El endpoint recibe `POST /chat` con `Content-Type: application/json`:

```json
{
  "message": "¿Cómo conecto la cámara a la consola?"
}
```

La respuesta tiene esta forma:

```json
{
  "question": "¿Cómo conecto la cámara a la consola?",
  "response": "Conecta la cámara mediante el cable USB-C incluido. (Fuente: NSwitch2_Information_Camera_EUR.pdf, pág. 1)"
}
```

El texto exacto depende de los fragmentos recuperados y de la respuesta generada por Groq.

Ejemplo con `curl`:

```bash
curl -X POST http://127.0.0.1:5000/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"¿Cómo conecto la cámara a la consola?"}'
```

Ejemplo en PowerShell:

```powershell
$body = @{ message = "¿Cómo conecto la cámara a la consola?" } | ConvertTo-Json
Invoke-RestMethod -Uri http://127.0.0.1:5000/chat -Method Post -ContentType "application/json" -Body $body
```

Si se omite `message`, está vacío o el cuerpo no es un objeto JSON, el endpoint devuelve HTTP 400. Los errores de configuración o disponibilidad RAG devuelven HTTP 503; otros errores de ejecución devuelven HTTP 500.

## Añadir o actualizar documentos

Coloca los PDF en `documents/`. El loader procesa todos los archivos con extensión `.pdf` que estén directamente dentro de esa carpeta.

Chroma guarda el índice localmente y el código actual lo reutiliza si la colección ya tiene contenido. Después de agregar, quitar o reemplazar manuales, detén Flask y elimina la carpeta generada `chroma/`; al iniciar y consultar de nuevo se creará el índice con los documentos actuales.

En PowerShell:

```powershell
Remove-Item -Recurse -Force .\chroma
```

En macOS/Linux:

```bash
rm -rf chroma
```

No elimines `.env`: contiene la configuración local de la API key.

## Solución de problemas

- **Falta `GROQ_API_KEY`:** verifica que `.env` esté en la raíz y tenga la clave válida, sin comillas ni texto de ejemplo; reinicia Flask tras modificarlo.
- **No hay documentos PDF:** confirma que los PDF estén en `documents/`, no en una subcarpeta.
- **No encuentra información de un documento recién agregado:** detén Flask, borra `chroma/` y vuelve a ejecutar una consulta para reindexar.
- **Respuesta HTTP 500 o error de Groq:** revisa la terminal donde se ejecuta Flask. Puede haber un problema de conexión, credenciales, modelo seleccionado o límite de solicitudes/tokens de Groq.
- **Error por contexto demasiado grande:** formula una pregunta concreta. El contexto se restringe especialmente para consultas sobre la cámara, pero los límites del proveedor y del modelo pueden cambiar.
- **Aviso de enlaces simbólicos de Hugging Face en Windows:** normalmente es una advertencia, no un error; el modelo puede descargarse igualmente, aunque el caché use más espacio.
- **El puerto 5000 está ocupado:** detén la otra aplicación que lo usa o cambia el puerto en la llamada `app.run()` al final de `app.py`.

## Seguridad y despliegue

`python app.py` inicia el servidor de desarrollo de Flask, adecuado para ejecutar y probar el proyecto localmente. No debe utilizarse como servidor de producción. Mantén la API key en `.env` y no la incluyas en capturas, mensajes ni repositorios públicos.

### Desplegar en Render

El repositorio incluye `render.yaml`. Al crear un Blueprint en Render y conectar este repositorio, Render instalará las dependencias con `pip install -r requirements.txt` y arrancará Flask con Gunicorn en el puerto que Render asigne.

Configura `GROQ_API_KEY` en el panel del servicio de Render como variable secreta. No la escribas en `render.yaml` ni la subas al repositorio. `GROQ_MODEL` y `EMBEDDING_MODEL` ya tienen valores predeterminados en la configuración del Blueprint y se pueden cambiar desde el panel si es necesario.

Si configuras el servicio manualmente en lugar de usar el Blueprint:

- **Runtime:** Python 3
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `gunicorn app:app --bind 0.0.0.0:$PORT --timeout 180`
- **Environment Variable:** `GROQ_API_KEY`, con la clave creada en Groq Console

Los PDF deben estar incluidos en el repositorio dentro de `documents/` para que Render los pueda indexar. Render puede eliminar archivos generados locales al reiniciar o volver a desplegar; en ese caso la aplicación volverá a crear `chroma/` al procesar una consulta, por lo que necesitará descargar otra vez el modelo de embeddings. El servidor de desarrollo `python app.py` se reserva para uso local.