Coloca en esta carpeta los archivos PDF que consultará el chatbot RAG.

La primera consulta carga los PDF, los divide en fragmentos y crea la base vectorial
persistente en la carpeta `chroma/`. Si cambias los documentos después de indexarlos,
detén la aplicación, elimina `chroma/` y vuelve a iniciarla para reconstruir el índice.