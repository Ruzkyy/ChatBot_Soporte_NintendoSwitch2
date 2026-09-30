import os
import re
import unicodedata
from functools import lru_cache
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
DOCUMENTS_DIR = PROJECT_DIR / "documents"
CHROMA_DIR = PROJECT_DIR / "chroma"
COLLECTION_NAME = "documentos_rag"
NO_ANSWER = "No encontré información sobre esto en la base de conocimientos."
SPANISH_STOP_WORDS = {
    "a", "al", "algo", "como", "con", "de", "del", "el", "en", "es",
    "esta", "este", "la", "las", "lo", "los", "me", "mi", "o", "para",
    "por", "que", "se", "si", "su", "un", "una", "y",
}

SYSTEM_PROMPT = """Eres un asistente que responde preguntas sobre los documentos proporcionados.
Responde en el mismo idioma de la pregunta y usando únicamente la información del contexto.
Contesta directamente lo que el usuario quiere saber: explica o resume las instrucciones
relevantes en vez de limitarte a enumerar los títulos de las secciones. Si pregunta qué
debe hacer, presenta las acciones concretas indicadas en los documentos. Enumera títulos
solo cuando el usuario pida identificar o listar secciones. Añade al final una referencia
breve al documento y la página que respaldan la respuesta. No afirmes que la respuesta es
exhaustiva si el contexto recuperado no permite comprobarlo. Si el contexto no contiene
la respuesta, responde exactamente: "{no_answer}"

Contexto:
{context}

Pregunta: {question}

Respuesta:"""


class RAGError(RuntimeError):
    """Error de configuración o de disponibilidad esperable del sistema RAG."""


@lru_cache(maxsize=1)
def _get_embeddings():
    try:
        from langchain_huggingface import HuggingFaceEmbeddings
    except ImportError as error:
        raise RAGError("Faltan dependencias RAG. Instálalas con: pip install -r requirements.txt") from error

    return HuggingFaceEmbeddings(
        model_name=os.getenv(
            "EMBEDDING_MODEL",
            "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        ),
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )


@lru_cache(maxsize=1)
def _get_vector_store():
    pdf_files = sorted(
        path for path in DOCUMENTS_DIR.iterdir()
        if path.is_file() and path.suffix.lower() == ".pdf"
    ) if DOCUMENTS_DIR.exists() else []
    if not pdf_files:
        raise RAGError(
            "No hay documentos PDF en la carpeta 'documents'. Coloca allí al menos un PDF y reinicia la aplicación."
        )

    try:
        from langchain_chroma import Chroma
        from langchain_community.document_loaders import PyPDFLoader
        from langchain_text_splitters import RecursiveCharacterTextSplitter
    except ImportError as error:
        raise RAGError("Faltan dependencias RAG. Instálalas con: pip install -r requirements.txt") from error

    vector_store = Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=_get_embeddings(),
        persist_directory=str(CHROMA_DIR),
        collection_metadata={"hnsw:space": "cosine"},
    )
    if vector_store._collection.count() > 0:
        return vector_store

    documents = []
    for pdf_path in pdf_files:
        documents.extend(PyPDFLoader(str(pdf_path)).load())

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
        separators=["\n\n", "\n", ".", " "],
    )
    chunks = splitter.split_documents(documents)
    chunks = [chunk for chunk in chunks if chunk.page_content.strip()]
    if not chunks:
        raise RAGError("No se pudo extraer texto de los PDF. Verifica que contengan texto seleccionable.")

    vector_store.add_documents(chunks)
    return vector_store


def _get_llm():
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        raise RAGError("Falta GROQ_API_KEY. Configúrala en el archivo .env antes de preguntar.")

    try:
        from langchain_groq import ChatGroq
    except ImportError as error:
        raise RAGError("Faltan dependencias RAG. Instálalas con: pip install -r requirements.txt") from error

    return ChatGroq(
        model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
        temperature=0.0,
        api_key=api_key,
    )


def _camera_source_filter(question: str) -> dict | None:
    normalized_question = question.casefold().replace("á", "a")
    camera_terms = ("camara", "camera", "webcam")
    if not any(term in normalized_question for term in camera_terms):
        return None

    camera_pdf = DOCUMENTS_DIR / "NSwitch2_Information_Camera_EUR.pdf"
    if camera_pdf.exists():
        return {"source": str(camera_pdf)}
    return None


def _camera_context(question: str, documents: list) -> list:
    def words(text: str) -> set[str]:
        normalized = unicodedata.normalize("NFKD", text.casefold())
        normalized = "".join(char for char in normalized if not unicodedata.combining(char))
        return set(re.findall(r"[a-z0-9]+", normalized))

    question_terms = words(question) - SPANISH_STOP_WORDS
    ranked_documents = sorted(
        enumerate(documents),
        key=lambda item: (
            -len(question_terms & words(item[1].page_content)),
            item[0],
        ),
    )
    return [document for _, document in ranked_documents[:8]]


def _small_talk_response(question: str) -> str | None:
    normalized = unicodedata.normalize("NFKD", question.casefold())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    normalized = " ".join(re.findall(r"[a-z0-9]+", normalized))

    if normalized in {"hola", "buenas", "hey", "hi", "buenos dias", "buenas tardes", "buenas noches"}:
        return "¡Hola! ¿En qué puedo ayudarte? Puedes preguntarme sobre la cámara, los controles u otros manuales de Nintendo Switch 2."
    if normalized in {"gracias", "muchas gracias", "te agradezco"}:
        return "¡Con gusto! ¿Tienes otra pregunta sobre los manuales?"
    if normalized in {"adios", "hasta luego", "nos vemos", "chao"}:
        return "¡Hasta luego! Aquí estaré si necesitas consultar algo de los manuales."
    return None


def rag_pipeline(question: str, k: int = 5) -> str:
    """Recupera fragmentos de los PDF y genera una respuesta basada en su contexto."""
    small_talk_response = _small_talk_response(question)
    if small_talk_response:
        return small_talk_response

    llm = _get_llm()
    vector_store = _get_vector_store()
    source_filter = _camera_source_filter(question)
    search_kwargs = {"k": 100 if source_filter else k}
    if source_filter:
        search_kwargs["filter"] = source_filter
    documents = vector_store.similarity_search(question, **search_kwargs)
    if source_filter:
        documents = _camera_context(question, documents)

    context_parts = []
    for document in documents:
        source = Path(document.metadata.get("source", "documento")).name
        page = document.metadata.get("page")
        page_label = f"{int(page) + 1}" if isinstance(page, int) else "?"
        context_parts.append(
            f"[Fuente: {source} - Pág. {page_label}]\n{document.page_content}"
        )

    context = "\n\n---\n\n".join(context_parts)
    prompt = SYSTEM_PROMPT.format(
        no_answer=NO_ANSWER,
        context=context,
        question=question,
    )
    result = llm.invoke(prompt)
    return str(result.content)