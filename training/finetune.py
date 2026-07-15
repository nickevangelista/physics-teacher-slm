#!/usr/bin/env python3
"""
finetune.py — Fine-tuning QLoRA do Physics Teacher SLM usando Unsloth.

Treina um modelo Qwen 2.5 3B Instruct com QLoRA em dados de Física,
otimizado para RTX 3050 (4GB VRAM).

Pipeline:
  1. Carrega modelo base em 4-bit via Unsloth
  2. Aplica adaptadores LoRA (r=8, alpha=16)
  3. Carrega dataset ShareGPT/ChatML de data/physics_dataset.jsonl
  4. Treina com gradient checkpointing e acumulação de gradientes
  5. Salva adaptadores LoRA em models/physics_model_lora/
  6. Exporta GGUF Q4_K_M para models/physics_model_gguf/

Uso:
    python training/finetune.py
    python training/finetune.py --epochs 3 --lr 2e-4 --batch-size 1
    python training/finetune.py --skip-gguf   # Pula exportação GGUF
    python training/finetune.py --resume       # Retoma de checkpoint
"""

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

# ─── Configuração Crítica de VRAM ───────────────────────────────────────────
# Deve ser definido ANTES de importar torch/cuda
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Raiz do projeto
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Caminhos padrão
DATASET_PATH = PROJECT_ROOT / "data" / "physics_dataset.jsonl"
LORA_OUTPUT_DIR = PROJECT_ROOT / "models" / "physics_model_lora"
GGUF_OUTPUT_DIR = PROJECT_ROOT / "models" / "physics_model_gguf"
LOGS_DIR = PROJECT_ROOT / "training" / "logs"

# Modelo base
MODEL_NAME = "unsloth/Qwen2.5-3B-Instruct-bnb-4bit"
MODEL_NAME_FALLBACK = "Qwen/Qwen2.5-3B-Instruct"

# ─── Configurações padrão para RTX 3050 4GB VRAM ───────────────────────────
DEFAULT_CONFIG = {
    "max_seq_length": 1024,
    "load_in_4bit": True,
    "dtype": None,  # Auto-detect (será float16 para RTX 3050)
    # LoRA
    "lora_r": 8,
    "lora_alpha": 16,
    "lora_dropout": 0.0,
    "target_modules": [
        "q_proj", "k_proj", "v_proj", "o_proj",
        "gate_proj", "up_proj", "down_proj",
    ],
    # Treinamento
    "epochs": 3,
    "learning_rate": 2e-4,
    "per_device_train_batch_size": 1,
    "gradient_accumulation_steps": 4,
    "warmup_steps": 10,
    "weight_decay": 0.01,
    "max_grad_norm": 1.0,
    "optim": "adamw_8bit",
    "lr_scheduler_type": "cosine",
    "seed": 42,
    "logging_steps": 5,
    "save_steps": 50,
    "fp16": False,
    "bf16": True,
}

# System prompt padrão (deve ser o mesmo usado na preparação do dataset)
SYSTEM_PROMPT = (
    "Você é um professor de Física experiente e didático. "
    "Responda de forma clara, precisa e acessível, usando exemplos "
    "práticos quando possível. Inclua equações relevantes e explique "
    "cada passo do raciocínio."
)


def verificar_cuda():
    """Verifica disponibilidade de CUDA e mostra informações da GPU."""
    try:
        import torch
    except ImportError:
        logger.error("PyTorch não encontrado. Instale com: pip install torch")
        sys.exit(1)

    if not torch.cuda.is_available():
        logger.error(
            "CUDA não disponível! Verifique:\n"
            "  1. Drivers NVIDIA instalados (nvidia-smi)\n"
            "  2. PyTorch com suporte CUDA (pip install torch --index-url ...)\n"
            "  3. WSL: CUDA toolkit configurado corretamente"
        )
        sys.exit(1)

    gpu_name = torch.cuda.get_device_name(0)
    vram_total = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
    vram_livre = torch.cuda.mem_get_info()[0] / (1024 ** 3)

    logger.info(f"🖥️  GPU: {gpu_name}")
    logger.info(f"   VRAM Total:  {vram_total:.1f} GB")
    logger.info(f"   VRAM Livre:  {vram_livre:.1f} GB")

    if vram_total < 3.5:
        logger.warning(
            "⚠ VRAM muito baixa! O treinamento pode falhar. "
            "Considere fechar outros programas que usam GPU."
        )

    # Verifica suporte bf16
    capability = torch.cuda.get_device_capability(0)
    if capability[0] < 8:
        logger.info(f"   Compute Cap: {capability[0]}.{capability[1]} — usando fp16 (bf16 não suportado)")
    else:
        logger.info(f"   Compute Cap: {capability[0]}.{capability[1]} — bf16 disponível")

    return {
        "gpu_name": gpu_name,
        "vram_total": vram_total,
        "vram_livre": vram_livre,
        "compute_capability": capability,
    }


def carregar_dataset(caminho: Path, max_seq_length: int = 1024) -> list[dict]:
    """
    Carrega o dataset JSONL em formato ShareGPT/ChatML.

    Valida cada exemplo e filtra os inválidos.
    Alerta sobre exemplos que podem exceder max_seq_length.

    Returns:
        Lista de dicionários no formato ShareGPT
    """
    if not caminho.exists():
        logger.error(f"Dataset não encontrado: {caminho}")
        logger.info("Execute primeiro: python training/prepare_dataset.py --modo auto")
        sys.exit(1)

    exemplos = []
    invalidos = 0

    with open(caminho, "r", encoding="utf-8") as f:
        for num_linha, linha in enumerate(f, 1):
            linha = linha.strip()
            if not linha:
                continue

            try:
                dado = json.loads(linha)
            except json.JSONDecodeError:
                logger.warning(f"Linha {num_linha}: JSON inválido, pulando.")
                invalidos += 1
                continue

            # Valida estrutura ShareGPT
            convs = dado.get("conversations", [])
            if not convs:
                logger.warning(f"Linha {num_linha}: sem 'conversations', pulando.")
                invalidos += 1
                continue

            # Verifica se tem pelo menos user + assistant
            roles = [c.get("role") for c in convs]
            if "user" not in roles or "assistant" not in roles:
                logger.warning(f"Linha {num_linha}: falta 'user' ou 'assistant', pulando.")
                invalidos += 1
                continue

            exemplos.append(dado)

    logger.info(f"📊 Dataset carregado: {len(exemplos)} exemplos válidos")
    if invalidos:
        logger.warning(f"   {invalidos} exemplos inválidos ignorados")

    if len(exemplos) < 50:
        logger.warning(
            f"⚠ Apenas {len(exemplos)} exemplos! Recomendado: 200-400. "
            "Gere mais com: python training/prepare_dataset.py --modo auto"
        )

    return exemplos


def formatar_dataset_para_treino(exemplos: list[dict], tokenizer) -> list[str]:
    """
    Formata os exemplos usando o chat template do tokenizer.

    Usa tokenizer.apply_chat_template() para garantir formatação
    correta no formato ChatML esperado pelo Qwen.

    Returns:
        Lista de strings formatadas prontas para tokenização
    """
    textos_formatados = []
    erros = 0

    for i, exemplo in enumerate(exemplos):
        convs = exemplo["conversations"]

        # Converte para o formato esperado pelo tokenizer
        mensagens = []
        for conv in convs:
            mensagens.append({
                "role": conv["role"],
                "content": conv["content"],
            })

        try:
            texto = tokenizer.apply_chat_template(
                mensagens,
                tokenize=False,
                add_generation_prompt=False,
            )
            textos_formatados.append(texto)
        except Exception as e:
            logger.warning(f"Exemplo {i + 1}: erro na formatação — {e}")
            erros += 1

    if erros:
        logger.warning(f"   {erros} exemplos com erro de formatação")

    logger.info(f"✅ {len(textos_formatados)} exemplos formatados com chat template")

    # Mostra exemplo formatado para verificação
    if textos_formatados:
        logger.info("\n📋 Exemplo de formatação (primeiro exemplo):")
        preview = textos_formatados[0][:500]
        for linha in preview.split("\n"):
            logger.info(f"   {linha}")
        if len(textos_formatados[0]) > 500:
            logger.info("   ...")

    return textos_formatados


def treinar(args):
    """
    Executa o pipeline completo de fine-tuning QLoRA.

    Etapas:
    1. Verifica GPU e CUDA
    2. Carrega modelo base com Unsloth (4-bit)
    3. Aplica adaptadores LoRA
    4. Carrega e formata dataset
    5. Treina com SFTTrainer do TRL
    6. Salva adaptadores LoRA
    7. (Opcional) Exporta GGUF
    """
    inicio_total = time.time()

    # ─── 1. Verificação de GPU ──────────────────────────────────────────
    logger.info("=" * 60)
    logger.info("🔬 Physics Teacher SLM — Fine-tuning QLoRA")
    logger.info("=" * 60)

    gpu_info = verificar_cuda()

    # ─── 2. Carrega modelo base ─────────────────────────────────────────
    logger.info("\n📥 Carregando modelo base...")
    logger.info(f"   Modelo: {MODEL_NAME}")
    logger.info(f"   Quantização: 4-bit (load_in_4bit=True)")
    logger.info(f"   Max seq length: {args.max_seq_length}")

    try:
        from unsloth import FastLanguageModel
    except ImportError:
        logger.error(
            "Unsloth não encontrado! Instale com:\n"
            "  pip install unsloth\n"
            "Ou veja: https://github.com/unslothai/unsloth"
        )
        sys.exit(1)

    try:
        model, tokenizer = FastLanguageModel.from_pretrained(
            model_name=MODEL_NAME,
            max_seq_length=args.max_seq_length,
            load_in_4bit=DEFAULT_CONFIG["load_in_4bit"],
            dtype=DEFAULT_CONFIG["dtype"],
        )
    except Exception as e:
        logger.warning(f"Falha ao carregar '{MODEL_NAME}': {e}")
        logger.info(f"Tentando modelo alternativo: {MODEL_NAME_FALLBACK}")
        try:
            model, tokenizer = FastLanguageModel.from_pretrained(
                model_name=MODEL_NAME_FALLBACK,
                max_seq_length=args.max_seq_length,
                load_in_4bit=DEFAULT_CONFIG["load_in_4bit"],
                dtype=DEFAULT_CONFIG["dtype"],
            )
        except Exception as e2:
            logger.error(f"Falha ao carregar modelo: {e2}")
            sys.exit(1)

    logger.info("✅ Modelo base carregado!")

    # ─── 3. Aplica LoRA ─────────────────────────────────────────────────
    logger.info("\n🔧 Aplicando adaptadores LoRA...")
    logger.info(f"   r={args.lora_r}, alpha={args.lora_alpha}")
    logger.info(f"   Módulos: {DEFAULT_CONFIG['target_modules']}")

    model = FastLanguageModel.get_peft_model(
        model,
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=DEFAULT_CONFIG["lora_dropout"],
        target_modules=DEFAULT_CONFIG["target_modules"],
        bias="none",
        use_gradient_checkpointing="unsloth",  # Economiza ~60% VRAM
        random_state=DEFAULT_CONFIG["seed"],
    )

    # Mostra contagem de parâmetros
    total_params = sum(p.numel() for p in model.parameters())
    treinaveis = sum(p.numel() for p in model.parameters() if p.requires_grad)
    logger.info(f"   Parâmetros totais:     {total_params:,}")
    logger.info(f"   Parâmetros treináveis: {treinaveis:,} ({treinaveis/total_params*100:.2f}%)")

    # ─── 4. Carrega e formata dataset ───────────────────────────────────
    logger.info(f"\n📚 Carregando dataset de '{args.dataset}'...")
    exemplos = carregar_dataset(Path(args.dataset), args.max_seq_length)
    textos_formatados = formatar_dataset_para_treino(exemplos, tokenizer)

    if not textos_formatados:
        logger.error("Nenhum exemplo formatado! Verifique o dataset.")
        sys.exit(1)

    # Cria dataset do HuggingFace
    from datasets import Dataset

    dataset = Dataset.from_dict({"text": textos_formatados})
    logger.info(f"✅ Dataset: {len(dataset)} exemplos")

    # Split treino/validação (90/10) se houver exemplos suficientes
    if len(dataset) >= 20:
        split = dataset.train_test_split(test_size=0.1, seed=DEFAULT_CONFIG["seed"])
        train_dataset = split["train"]
        eval_dataset = split["test"]
        logger.info(f"   Treino:    {len(train_dataset)} exemplos")
        logger.info(f"   Validação: {len(eval_dataset)} exemplos")
    else:
        train_dataset = dataset
        eval_dataset = None
        logger.info("   ⚠ Poucos exemplos — sem split de validação")

    # ─── 5. Configuração do treinamento ─────────────────────────────────
    logger.info("\n⚙️  Configurando treinamento...")

    from trl import SFTTrainer
    from transformers import TrainingArguments

    # Diretório de logs e checkpoints
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    run_name = f"physics-slm-{time.strftime('%Y%m%d-%H%M%S')}"

    training_args = TrainingArguments(
        output_dir=str(LORA_OUTPUT_DIR / "checkpoints"),
        run_name=run_name,
        # Épocas e batch
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.gradient_accumulation_steps,
        # Otimizador
        learning_rate=args.learning_rate,
        optim=DEFAULT_CONFIG["optim"],
        lr_scheduler_type=DEFAULT_CONFIG["lr_scheduler_type"],
        warmup_steps=DEFAULT_CONFIG["warmup_steps"],
        weight_decay=DEFAULT_CONFIG["weight_decay"],
        max_grad_norm=DEFAULT_CONFIG["max_grad_norm"],
        # Precisão — RTX 3050: fp16 SIM, bf16 NÃO
        fp16=DEFAULT_CONFIG["fp16"],
        bf16=DEFAULT_CONFIG["bf16"],
        # Logging
        logging_dir=str(LOGS_DIR / run_name),
        logging_steps=DEFAULT_CONFIG["logging_steps"],
        logging_first_step=True,
        report_to="none",  # Sem wandb/tensorboard por padrão
        # Salvamento
        save_steps=DEFAULT_CONFIG["save_steps"],
        save_total_limit=2,
        # Validação
        eval_strategy="steps" if eval_dataset else "no",
        eval_steps=50 if eval_dataset else None,
        # Memória
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        # Reprodutibilidade
        seed=DEFAULT_CONFIG["seed"],
        data_seed=DEFAULT_CONFIG["seed"],
        # Misc
        dataloader_pin_memory=False,  # Economiza RAM
        remove_unused_columns=True,
    )

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        args=training_args,
        dataset_text_field="text",
        max_seq_length=args.max_seq_length,
        packing=False,  # Sem packing para manter contexto por exemplo
    )

    # Mostra configuração
    logger.info(f"   Épocas:              {args.epochs}")
    logger.info(f"   Batch size:          {args.batch_size}")
    logger.info(f"   Grad accumulation:   {args.gradient_accumulation_steps}")
    logger.info(f"   Effective batch:     {args.batch_size * args.gradient_accumulation_steps}")
    logger.info(f"   Learning rate:       {args.learning_rate}")
    logger.info(f"   Otimizador:          {DEFAULT_CONFIG['optim']}")
    logger.info(f"   Precisão:            fp16={DEFAULT_CONFIG['fp16']}, bf16={DEFAULT_CONFIG['bf16']}")
    logger.info(f"   Grad checkpointing:  unsloth")
    logger.info(f"   Max seq length:      {args.max_seq_length}")

    # Estimativa de passos totais
    total_steps = (len(train_dataset) // (args.batch_size * args.gradient_accumulation_steps)) * args.epochs
    logger.info(f"   Passos totais (est): {total_steps}")

    # ─── 6. Treinamento ────────────────────────────────────────────────
    logger.info("\n🚀 Iniciando treinamento...")
    logger.info("   (Ctrl+C para interromper — o progresso será salvo)\n")

    try:
        # Verifica se há checkpoint para retomar
        checkpoint = None
        if args.resume:
            checkpoints_dir = LORA_OUTPUT_DIR / "checkpoints"
            if checkpoints_dir.exists():
                cps = sorted(checkpoints_dir.glob("checkpoint-*"))
                if cps:
                    checkpoint = str(cps[-1])
                    logger.info(f"   📂 Retomando de: {checkpoint}")

        resultado = trainer.train(resume_from_checkpoint=checkpoint)

        # Métricas de treinamento
        logger.info("\n📊 MÉTRICAS DE TREINAMENTO")
        logger.info("=" * 40)
        metricas = resultado.metrics
        for chave, valor in metricas.items():
            if isinstance(valor, float):
                logger.info(f"   {chave}: {valor:.4f}")
            else:
                logger.info(f"   {chave}: {valor}")

    except KeyboardInterrupt:
        logger.info("\n⚠ Treinamento interrompido pelo usuário.")
        logger.info("   Salvando estado atual...")
    except Exception as e:
        logger.error(f"\n❌ Erro durante treinamento: {e}")
        import traceback
        traceback.print_exc()
        logger.info("   Tentando salvar o modelo parcial...")

    # ─── 7. Salva adaptadores LoRA ──────────────────────────────────────
    logger.info(f"\n💾 Salvando adaptadores LoRA em '{LORA_OUTPUT_DIR}'...")

    LORA_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(LORA_OUTPUT_DIR))
    tokenizer.save_pretrained(str(LORA_OUTPUT_DIR))
    logger.info("✅ LoRA salvo!")

    # Salva informações do treinamento
    info_treino = {
        "modelo_base": MODEL_NAME,
        "data_treino": time.strftime("%Y-%m-%d %H:%M:%S"),
        "gpu": gpu_info["gpu_name"],
        "config": {
            "epochs": args.epochs,
            "learning_rate": args.learning_rate,
            "batch_size": args.batch_size,
            "gradient_accumulation_steps": args.gradient_accumulation_steps,
            "lora_r": args.lora_r,
            "lora_alpha": args.lora_alpha,
            "max_seq_length": args.max_seq_length,
            "fp16": DEFAULT_CONFIG["fp16"],
            "optim": DEFAULT_CONFIG["optim"],
        },
        "dataset": {
            "total_exemplos": len(exemplos),
            "treino": len(train_dataset),
            "validacao": len(eval_dataset) if eval_dataset else 0,
        },
    }
    info_path = LORA_OUTPUT_DIR / "training_info.json"
    with open(info_path, "w", encoding="utf-8") as f:
        json.dump(info_treino, f, ensure_ascii=False, indent=2)
    logger.info(f"   Info salva em: {info_path}")

    # ─── 8. Exporta GGUF (opcional) ─────────────────────────────────────
    if not args.skip_gguf:
        logger.info(f"\n📦 Exportando GGUF Q4_K_M para '{GGUF_OUTPUT_DIR}'...")

        GGUF_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        try:
            model.save_pretrained_gguf(
                str(GGUF_OUTPUT_DIR),
                tokenizer,
                quantization_method="q4_k_m",
            )
            logger.info("✅ GGUF exportado!")

            # Mostra tamanho do arquivo GGUF
            for gguf_file in GGUF_OUTPUT_DIR.glob("*.gguf"):
                tamanho_mb = gguf_file.stat().st_size / (1024 * 1024)
                logger.info(f"   {gguf_file.name}: {tamanho_mb:.1f} MB")

        except Exception as e:
            logger.error(f"❌ Erro ao exportar GGUF: {e}")
            logger.info(
                "   Você pode exportar manualmente depois com:\n"
                "   python -c \"from unsloth import FastLanguageModel; "
                f"m,t = FastLanguageModel.from_pretrained('{LORA_OUTPUT_DIR}'); "
                f"m.save_pretrained_gguf('{GGUF_OUTPUT_DIR}', t, quantization_method='q4_k_m')\""
            )
    else:
        logger.info("\n⏭ Exportação GGUF pulada (--skip-gguf)")

    # ─── Resumo final ───────────────────────────────────────────────────
    tempo_total = time.time() - inicio_total

    logger.info("\n" + "=" * 60)
    logger.info("🏁 FINE-TUNING CONCLUÍDO!")
    logger.info("=" * 60)
    logger.info(f"   Tempo total:      {tempo_total / 60:.1f} minutos")
    logger.info(f"   LoRA salvo em:    {LORA_OUTPUT_DIR}")
    if not args.skip_gguf:
        logger.info(f"   GGUF salvo em:    {GGUF_OUTPUT_DIR}")
    logger.info(f"   Logs em:          {LOGS_DIR}")
    logger.info("")
    logger.info("   Próximos passos:")
    logger.info("   1. Teste o modelo: python app/main.py")
    logger.info("   2. Importe no Ollama:")
    logger.info(f"      ollama create physics-teacher -f {GGUF_OUTPUT_DIR}/Modelfile")
    logger.info("=" * 60)


def main():
    """Ponto de entrada principal com argparse."""
    parser = argparse.ArgumentParser(
        description="Fine-tuning QLoRA para Physics Teacher SLM (RTX 3050 4GB VRAM).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Exemplos:\n"
            "  python training/finetune.py\n"
            "  python training/finetune.py --epochs 5 --lr 1e-4\n"
            "  python training/finetune.py --skip-gguf\n"
            "  python training/finetune.py --resume\n"
            "\n"
            "Configuração para RTX 3050 (4GB VRAM):\n"
            "  - load_in_4bit=True, fp16=True (NÃO bf16)\n"
            "  - batch_size=1, gradient_accumulation=4\n"
            "  - gradient_checkpointing='unsloth'\n"
            "  - optim='adamw_8bit'\n"
        ),
    )

    # Hiperparâmetros de treinamento
    parser.add_argument(
        "--epochs", type=int, default=DEFAULT_CONFIG["epochs"],
        help=f"Número de épocas (padrão: {DEFAULT_CONFIG['epochs']})",
    )
    parser.add_argument(
        "--lr", "--learning-rate", type=float, default=DEFAULT_CONFIG["learning_rate"],
        dest="learning_rate",
        help=f"Taxa de aprendizagem (padrão: {DEFAULT_CONFIG['learning_rate']})",
    )
    parser.add_argument(
        "--batch-size", type=int, default=DEFAULT_CONFIG["per_device_train_batch_size"],
        dest="batch_size",
        help=f"Batch size por GPU (padrão: {DEFAULT_CONFIG['per_device_train_batch_size']})",
    )
    parser.add_argument(
        "--gradient-accumulation-steps", type=int,
        default=DEFAULT_CONFIG["gradient_accumulation_steps"],
        help=f"Passos de acumulação de gradiente (padrão: {DEFAULT_CONFIG['gradient_accumulation_steps']})",
    )
    parser.add_argument(
        "--max-seq-length", type=int, default=DEFAULT_CONFIG["max_seq_length"],
        help=f"Comprimento máximo de sequência (padrão: {DEFAULT_CONFIG['max_seq_length']})",
    )

    # LoRA
    parser.add_argument(
        "--lora-r", type=int, default=DEFAULT_CONFIG["lora_r"],
        help=f"Rank do LoRA (padrão: {DEFAULT_CONFIG['lora_r']})",
    )
    parser.add_argument(
        "--lora-alpha", type=int, default=DEFAULT_CONFIG["lora_alpha"],
        help=f"Alpha do LoRA (padrão: {DEFAULT_CONFIG['lora_alpha']})",
    )

    # Dataset
    parser.add_argument(
        "--dataset", type=str, default=str(DATASET_PATH),
        help=f"Caminho do dataset JSONL (padrão: {DATASET_PATH})",
    )

    # Controle
    parser.add_argument(
        "--skip-gguf", action="store_true",
        help="Pula a exportação GGUF",
    )
    parser.add_argument(
        "--resume", action="store_true",
        help="Retoma treinamento do último checkpoint",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Mostra informações detalhadas de debug",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Validação de batch_size para VRAM limitada
    if args.batch_size > 1:
        logger.warning(
            f"⚠ batch_size={args.batch_size} pode causar OOM em 4GB VRAM. "
            "Recomendado: batch_size=1 com gradient_accumulation_steps=4"
        )

    treinar(args)


if __name__ == "__main__":
    main()
