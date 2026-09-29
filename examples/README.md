# Exemplos

Este diretório documenta exemplos de uso sem versionar imagens ou pesos grandes.

## Exemplo mínimo

```bash
python inference.py minha_imagem.jpg
```

## Com JSON

```bash
python inference.py minha_imagem.jpg \
  --json-output resultado.json
```

## Com parâmetros explícitos

```bash
python inference.py minha_imagem.jpg \
  --model yolo11n.pt \
  --device cpu \
  --imgsz 640 \
  --conf 0.25 \
  --output resultado.jpg \
  --json-output resultado.json
```

## GPU

Em uma máquina configurada com CUDA e PyTorch compatível:

```bash
python inference.py minha_imagem.jpg --device 0
```

A disponibilidade de GPU depende da instalação local do PyTorch.
