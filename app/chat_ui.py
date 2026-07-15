"""
🧲 Professor de Física IA — Interface Web (Gradio)

Interface de chat combinando RAG (LlamaIndex + ChromaDB) com modelo
fine-tuned servido via Ollama. Duas abas: Chat e Configurações.

Uso:
    python -m app.chat_ui
    # ou
    gradio app/chat_ui.py
"""

import logging
import json
from pathlib import Path
from typing import Generator

import gradio as gr
import requests

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("chat_ui")

# ── Constantes ───────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "physics-teacher"
FALLBACK_MODEL = "qwen2.5:3b"

SYSTEM_PROMPT = (
    "Você é um professor de Física experiente e didático. "
    "Explique conceitos de forma clara, use exemplos práticos do dia a dia, "
    "e quando gerar questões de prova, siga o formato e nível de dificuldade "
    "típicos de provas de Ensino Médio e Ensino Superior brasileiro."
)

EXAMPLE_QUESTIONS = [
    "Explique a Terceira Lei de Newton com exemplos do cotidiano.",
    "O que é o efeito fotoelétrico e qual a sua importância histórica?",
    "Como funciona um capacitor de placas paralelas?",
    "Gere 3 questões de prova sobre cinemática (MRU e MRUV).",
    "Qual a diferença entre calor e temperatura?",
    "Explique o princípio de Arquimedes e dê um exemplo prático.",
    "O que são ondas eletromagnéticas? Dê exemplos do espectro.",
    "Resolva: Um corpo de 2kg é lançado verticalmente para cima com v=20m/s. Qual a altura máxima?",
]

# ── CSS customizado para tema premium ────────────────────────────────────────
CUSTOM_CSS = """
/* Container principal */
.gradio-container {
    max-width: 900px !important;
    margin: auto !important;
    font-family: 'Inter', 'Segoe UI', sans-serif !important;
}

/* Cabeçalho */
.header-title {
    text-align: center;
    font-size: 2.2em;
    font-weight: 700;
    margin-bottom: 0.1em;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}

.header-subtitle {
    text-align: center;
    font-size: 1.05em;
    opacity: 0.7;
    margin-bottom: 1em;
}

/* Chatbot */
.chatbot-container .message {
    border-radius: 12px !important;
    padding: 12px 16px !important;
}

/* Accordion de contexto RAG */
.context-accordion {
    margin-top: 8px;
    border-radius: 8px !important;
}

/* Botão de enviar */
.send-btn {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
    border: none !important;
    color: white !important;
    font-weight: 600 !important;
    border-radius: 8px !important;
}

/* Exemplos */
.examples-row button {
    border-radius: 8px !important;
    font-size: 0.9em !important;
}

/* Tabs */
.tab-nav button {
    font-weight: 600 !important;
    font-size: 1em !important;
}

/* Footer */
.footer-text {
    text-align: center;
    font-size: 0.85em;
    opacity: 0.5;
    margin-top: 1em;
}
"""


# ── Funções auxiliares ───────────────────────────────────────────────────────

def check_ollama_available() -> bool:
    """Verifica se o servidor Ollama está rodando."""
    try:
        resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=3)
        return resp.status_code == 200
    except requests.ConnectionError:
        logger.warning("Ollama não está acessível em %s", OLLAMA_BASE_URL)
        return False


def list_available_models() -> list[str]:
    """Lista modelos disponíveis no Ollama."""
    try:
        resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            models = [m["name"] for m in data.get("models", [])]
            logger.info("Modelos disponíveis: %s", models)
            return models if models else [FALLBACK_MODEL]
    except Exception as e:
        logger.error("Erro ao listar modelos: %s", e)
    return [FALLBACK_MODEL]


def get_default_base_model(available: list[str]) -> str:
    """Seleciona o modelo base padrão: prioriza qwen2.5:3b, senão o que estiver disponível."""
    for candidate in [FALLBACK_MODEL, DEFAULT_MODEL]:
        for model in available:
            if candidate in model:
                return model
    return available[0] if available else FALLBACK_MODEL


def get_default_tuned_model(available: list[str]) -> str:
    """Seleciona o modelo customizado padrão: prioriza physics-teacher, senão fallback."""
    for candidate in [DEFAULT_MODEL, "physics-teacher-q8", FALLBACK_MODEL]:
        for model in available:
            if candidate in model:
                return model
    return available[0] if available else FALLBACK_MODEL


def try_load_rag_engine():
    """
    Tenta carregar o query engine do módulo RAG.
    Retorna None se o índice não existir ou houver erro.
    """
    try:
        from rag.query_engine import get_query_engine  # noqa: F811
        engine = get_query_engine()
        logger.info("✅ RAG query engine carregado com sucesso.")
        return engine
    except ImportError:
        logger.info("Módulo RAG não encontrado — usando Ollama direto.")
    except FileNotFoundError:
        logger.info("Índice RAG não encontrado — usando Ollama direto.")
    except Exception as e:
        logger.warning("Erro ao carregar RAG: %s — usando Ollama direto.", e)
    return None


def query_ollama_stream(
    messages: list[dict],
    model: str,
    temperature: float = 0.7,
    top_k: int = 40,
) -> Generator[str, None, None]:
    """
    Envia mensagens para o Ollama e retorna resposta em streaming.
    Cada yield é um token parcial.
    """
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "options": {
            "temperature": temperature,
            "top_k": top_k,
            "num_ctx": 2048,
        },
    }

    try:
        with requests.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json=payload,
            stream=True,
            timeout=120,
        ) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines(decode_unicode=True):
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                    token = chunk.get("message", {}).get("content", "")
                    if token:
                        yield token
                    if chunk.get("done", False):
                        return
                except json.JSONDecodeError:
                    continue
    except requests.ConnectionError:
        yield "❌ Erro: Ollama não está rodando. Inicie com `ollama serve`."
    except requests.Timeout:
        yield "❌ Erro: Timeout na resposta do Ollama."
    except Exception as e:
        yield f"❌ Erro inesperado: {e}"


def query_with_rag(
    user_message: str,
    rag_engine,
    model: str,
    temperature: float,
    top_k: int,
) -> tuple[Generator[str, None, None], str]:
    """
    Consulta o RAG e usa o contexto recuperado para gerar resposta.
    Retorna (generator de tokens, contexto formatado).
    """
    context_text = ""

    try:
        # Busca documentos relevantes via RAG
        response = rag_engine.query(user_message)
        source_nodes = getattr(response, "source_nodes", [])

        if source_nodes:
            # Formata o contexto recuperado
            context_parts = []
            for i, node in enumerate(source_nodes, 1):
                score = getattr(node, "score", None)
                text = node.get_text() if hasattr(node, "get_text") else str(node)
                score_str = f" (relevância: {score:.2f})" if score else ""
                context_parts.append(f"**Trecho {i}{score_str}:**\n{text[:500]}")

            context_text = "\n\n---\n\n".join(context_parts)

            # Monta prompt enriquecido com contexto
            augmented_message = (
                f"Use o seguinte contexto dos materiais de Física para "
                f"responder à pergunta do aluno:\n\n"
                f"--- CONTEXTO ---\n{context_text}\n--- FIM DO CONTEXTO ---\n\n"
                f"Pergunta: {user_message}"
            )
        else:
            augmented_message = user_message
            context_text = "_Nenhum documento relevante encontrado no índice._"

    except Exception as e:
        logger.error("Erro na consulta RAG: %s", e)
        augmented_message = user_message
        context_text = f"_Erro ao consultar RAG: {e}_"

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": augmented_message},
    ]

    return query_ollama_stream(messages, model, temperature, top_k), context_text


# ── Estado global ────────────────────────────────────────────────────────────
rag_engine = try_load_rag_engine()


# ── Função principal de chat ─────────────────────────────────────────────────

def chat_respond_side_by_side(
    message: str,
    history_base: list[dict],
    history_tuned: list[dict],
    model_base: str,
    model_tuned: str,
    use_rag: bool,
    temperature: float,
    top_k: int,
) -> Generator[tuple[list[dict], list[dict], str], None, None]:
    """
    Processa mensagem do usuário e retorna resposta em streaming para ambos os chatbots.
    Integra RAG no modelo tuned quando ativado.
    """
    if not message or not message.strip():
        yield history_base, history_tuned, ""
        return

    if not check_ollama_available():
        error_msg = "❌ **Ollama não está rodando.**\n\nInicie o servidor com:\n```bash\nollama serve\n```"
        history_base.append({"role": "user", "content": message})
        history_base.append({"role": "assistant", "content": error_msg})
        history_tuned.append({"role": "user", "content": message})
        history_tuned.append({"role": "assistant", "content": error_msg})
        yield history_base, history_tuned, ""
        return

    # Adiciona mensagem do usuário ao histórico de ambos
    history_base.append({"role": "user", "content": message})
    history_tuned.append({"role": "user", "content": message})

    context_display = ""

    # Configura streams
    # 1. Base Model
    messages_base = [{"role": "system", "content": "Você é um assistente de IA útil e geral."}]
    # Limita histórico base para não estourar contexto
    messages_base.extend(history_base[-10:])
    stream_gen_base = query_ollama_stream(messages_base, model_base, temperature, top_k)

    # 2. Tuned Model (com RAG opcional)
    if use_rag and rag_engine is not None:
        stream_gen_tuned, context_display = query_with_rag(
            message, rag_engine, model_tuned, temperature, top_k
        )
    else:
        messages_tuned = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages_tuned.extend(history_tuned[-10:])
        stream_gen_tuned = query_ollama_stream(messages_tuned, model_tuned, temperature, top_k)
        context_display = "_RAG está desativado._" if not use_rag else "_Índice RAG não carregado._"

    # Inicializa respostas do assistente nos históricos
    history_base.append({"role": "assistant", "content": ""})
    history_tuned.append({"role": "assistant", "content": ""})

    base_text = ""
    tuned_text = ""
    base_done = False
    tuned_done = False

    # Consome os streams em paralelo/intercalados para visualização side-by-side
    while not (base_done and tuned_done):
        if not base_done:
            try:
                token = next(stream_gen_base)
                base_text += token
                history_base[-1]["content"] = base_text
            except StopIteration:
                base_done = True
        if not tuned_done:
            try:
                token = next(stream_gen_tuned)
                tuned_text += token
                history_tuned[-1]["content"] = tuned_text
            except StopIteration:
                tuned_done = True
        yield history_base, history_tuned, context_display


# ── Construção da UI ─────────────────────────────────────────────────────────

def build_ui() -> gr.Blocks:
    """Constrói e retorna a interface Gradio."""

    available_models = list_available_models()
    default_base_model = get_default_base_model(available_models)
    default_tuned_model = get_default_tuned_model(available_models)
    rag_status = "🟢 RAG ativo" if rag_engine else "🟡 RAG inativo (sem índice)"

    with gr.Blocks(
        title="🧲 Professor de Física IA",
        theme=gr.themes.Soft(
            primary_hue="indigo",
            secondary_hue="purple",
            neutral_hue="slate",
        ),
        css=CUSTOM_CSS,
    ) as app:

        # ── Cabeçalho ───────────────────────────────────────────────────
        gr.HTML(
            """
            <div>
                <p class="header-title">🧲 Professor de Física IA</p>
                <p class="header-subtitle">
                    Assistente inteligente para estudo de Física — 
                    Powered by Qwen 2.5 + RAG Local
                </p>
            </div>
            """
        )

        with gr.Tabs() as tabs:
            # ── Aba Chat ─────────────────────────────────────────────────
            with gr.TabItem("💬 Chat", id="chat"):

                # Status do RAG
                gr.Markdown(
                    f"<center>{rag_status}</center>",
                    elem_classes=["footer-text"],
                )

                # Área de chat side-by-side
                with gr.Row():
                    chatbot_base = gr.Chatbot(
                        label="Modelo Base",
                        height=480,
                        avatar_images=(None, "🤖"),
                        elem_classes=["chatbot-container"],
                        placeholder=(
                            "Olá! Sou o Modelo Base. 🤖\n\n"
                            "Respondo a perguntas de Física de forma geral."
                        ),
                    )
                    chatbot_tuned = gr.Chatbot(
                        label="Professor de Física (Fine-tuned)",
                        height=480,
                        avatar_images=(None, "🧲"),
                        elem_classes=["chatbot-container"],
                        placeholder=(
                            "Olá! Sou o seu Professor de Física IA. 🧲\n\n"
                            "Explico conceitos no estilo do professor, usando a notação correta e buscando referências nos slides."
                        ),
                    )

                # Accordion para contexto RAG recuperado
                with gr.Accordion(
                    "📚 Contexto Recuperado (RAG)",
                    open=False,
                    visible=rag_engine is not None,
                    elem_classes=["context-accordion"],
                ) as rag_accordion:
                    rag_context_display = gr.Markdown(
                        value="_Envie uma pergunta para ver o contexto._"
                    )

                # Checkbox para toggling RAG
                use_rag_checkbox = gr.Checkbox(
                    label="Ativar RAG (Busca de contexto nos slides do professor)" if rag_engine else "Ativar RAG (Desativado — Índice não encontrado em data/chroma_db/)",
                    value=rag_engine is not None,
                    interactive=rag_engine is not None,
                )

                # Área de input
                with gr.Row():
                    msg_input = gr.Textbox(
                        placeholder="Digite sua pergunta de Física...",
                        label="Mensagem",
                        show_label=False,
                        scale=8,
                        container=False,
                        autofocus=True,
                    )
                    send_btn = gr.Button(
                        "Enviar ➤",
                        variant="primary",
                        scale=1,
                        elem_classes=["send-btn"],
                    )

                with gr.Row():
                    clear_btn = gr.Button("🗑️ Limpar conversa", size="sm")
                    retry_btn = gr.Button("🔄 Regenerar última", size="sm")

                # Exemplos de perguntas
                gr.Examples(
                    examples=EXAMPLE_QUESTIONS,
                    inputs=msg_input,
                    label="💡 Perguntas de exemplo",
                    examples_per_page=4,
                )

            # ── Aba Configurações ────────────────────────────────────────
            with gr.TabItem("⚙️ Configurações", id="settings"):
                gr.Markdown("### Parâmetros do Modelo")

                with gr.Group():
                    model_base_dropdown = gr.Dropdown(
                        choices=available_models,
                        value=default_base_model,
                        label="🤖 Modelo Base (Esquerda)",
                        info="Selecione o modelo Ollama de base",
                        interactive=True,
                    )
                    model_tuned_dropdown = gr.Dropdown(
                        choices=available_models,
                        value=default_tuned_model,
                        label="🧲 Modelo Professor de Física (Direita)",
                        info="Selecione o modelo Ollama fine-tuned",
                        interactive=True,
                    )

                    refresh_models_btn = gr.Button(
                        "🔄 Atualizar lista de modelos", size="sm"
                    )

                with gr.Group():
                    temperature_slider = gr.Slider(
                        minimum=0.0,
                        maximum=1.5,
                        value=0.7,
                        step=0.05,
                        label="🌡️ Temperatura",
                        info=(
                            "Controla a criatividade das respostas. "
                            "Menor = mais focado, Maior = mais criativo."
                        ),
                    )

                    top_k_slider = gr.Slider(
                        minimum=1,
                        maximum=100,
                        value=40,
                        step=1,
                        label="🎯 Top-K",
                        info=(
                            "Número de tokens candidatos em cada passo. "
                            "Menor = mais determinístico."
                        ),
                    )

                gr.Markdown("### Status do Sistema")

                with gr.Group():
                    ollama_status = gr.Markdown(
                        value=(
                            f"- **Ollama:** {'🟢 Online' if check_ollama_available() else '🔴 Offline'}\n"
                            f"- **RAG:** {rag_status}\n"
                            f"- **Modelo base padrão:** `{default_base_model}`\n"
                            f"- **Modelo customizado padrão:** `{default_tuned_model}`\n"
                            f"- **Modelos disponíveis:** {len(available_models)}"
                        )
                    )

                gr.Markdown(
                    "### Sobre\n\n"
                    "Este projeto usa **Qwen 2.5 3B** fine-tuned com **QLoRA** "
                    "via Unsloth, combinado com **RAG** (LlamaIndex + ChromaDB) "
                    "para responder perguntas de Física com contexto de materiais "
                    "didáticos.\n\n"
                    "Todo o processamento acontece localmente na sua máquina. 🔒"
                )

        # ── Rodapé ───────────────────────────────────────────────────────
        gr.HTML(
            '<p class="footer-text">'
            "Physics Teacher SLM • Qwen 2.5 3B + RAG • "
            "Rodando 100% local 🔒"
            "</p>"
        )

        # ── Event handlers ───────────────────────────────────────────────

        # Enviar mensagem (botão ou Enter)
        submit_args = dict(
            fn=chat_respond_side_by_side,
            inputs=[
                msg_input,
                chatbot_base,
                chatbot_tuned,
                model_base_dropdown,
                model_tuned_dropdown,
                use_rag_checkbox,
                temperature_slider,
                top_k_slider,
            ],
            outputs=[chatbot_base, chatbot_tuned, rag_context_display],
        )

        msg_input.submit(**submit_args, show_progress="minimal").then(
            fn=lambda: "", outputs=msg_input  # Limpa input após envio
        )

        send_btn.click(**submit_args, show_progress="minimal").then(
            fn=lambda: "", outputs=msg_input
        )

        # Limpar conversa
        clear_btn.click(
            fn=lambda: ([], [], "_Envie uma pergunta para ver o contexto._"),
            outputs=[chatbot_base, chatbot_tuned, rag_context_display],
        )

        # Regenerar última resposta
        def retry_last_side_by_side(
            history_base,
            history_tuned,
            model_base,
            model_tuned,
            use_rag,
            temperature,
            top_k,
        ):
            """Remove a última resposta de ambos os chatbots e regenera."""
            if len(history_base) < 2 or len(history_tuned) < 2:
                yield history_base, history_tuned, ""
                return

            # Pega a última mensagem do usuário (deve ser igual para ambos)
            last_user_msg = history_base[-2]["content"]
            # Remove a última troca (user + assistant) de ambos
            history_base = history_base[:-2]
            history_tuned = history_tuned[:-2]

            # Regenera
            yield from chat_respond_side_by_side(
                last_user_msg,
                history_base,
                history_tuned,
                model_base,
                model_tuned,
                use_rag,
                temperature,
                top_k,
            )

        retry_btn.click(
            fn=retry_last_side_by_side,
            inputs=[
                chatbot_base,
                chatbot_tuned,
                model_base_dropdown,
                model_tuned_dropdown,
                use_rag_checkbox,
                temperature_slider,
                top_k_slider,
            ],
            outputs=[chatbot_base, chatbot_tuned, rag_context_display],
            show_progress="minimal",
        )

        # Atualizar lista de modelos
        def refresh_models():
            models = list_available_models()
            default_base = get_default_base_model(models)
            default_tuned = get_default_tuned_model(models)
            return (
                gr.Dropdown(choices=models, value=default_base),
                gr.Dropdown(choices=models, value=default_tuned),
            )

        refresh_models_btn.click(
            fn=refresh_models,
            outputs=[model_base_dropdown, model_tuned_dropdown],
        )

    return app


# ── Entrypoint ───────────────────────────────────────────────────────────────

def main():
    """Inicia o servidor Gradio."""
    logger.info("Iniciando Professor de Física IA...")

    if not check_ollama_available():
        logger.warning(
            "⚠️  Ollama não detectado em %s — inicie com 'ollama serve'",
            OLLAMA_BASE_URL,
        )

    app = build_ui()
    app.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_error=True,
        favicon_path=None,
    )


if __name__ == "__main__":
    main()
