from flask import Flask, jsonify, render_template, request
from dotenv import load_dotenv

from rag import RAGError, rag_pipeline

app = Flask(__name__)
load_dotenv()

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "El cuerpo debe ser un objeto JSON con el campo 'message'."}), 400

    question = data.get("message")
    if not isinstance(question, str) or not question.strip():
        return jsonify({"error": "El campo 'message' es obligatorio y debe ser texto."}), 400

    question = question.strip()
    try:
        response = rag_pipeline(question)
    except RAGError as error:
        return jsonify({"error": str(error)}), 503
    except Exception:
        app.logger.exception("Error al procesar la pregunta mediante RAG")
        return jsonify({"error": "No fue posible procesar la pregunta. Revisa la configuración y los registros del servidor."}), 500

    return jsonify({"question": question, "response": response})

if __name__ == "__main__":
    app.run(debug=True)