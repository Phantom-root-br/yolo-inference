# Visual e logs da POC de vídeo

Esta camada é operacional e não altera o detector. Ela serve para executar a POC com
rastreamento de logs e gerar um painel HTML local a partir dos artefatos já produzidos.

## Fluxo recomendado

No container HARPia:

```bash
cd /root/harpia_ws/src/yolo-inference
```

Para um teste curto de 60 frames:

```bash
./scripts/run_video_poc.sh test
```

Para a execução completa:

```bash
./scripts/run_video_poc.sh full
```

O runner:

1. usa `/root/yolo_venv/bin/python` por padrão;
2. executa `scripts/detect_people.py`;
3. mostra o progresso no terminal e grava a mesma saída com `tee`;
4. salva o log em `logs/video_poc_<modo>_<timestamp>.log`;
5. gera `output/video_report.html`;
6. usa `harpia-copylog` ao final, quando o helper estiver disponível.

É possível trocar o Python sem editar o script:

```bash
HARPIA_PYTHON=/caminho/para/python ./scripts/run_video_poc.sh test
```

E também trocar o vídeo de entrada:

```bash
HARPIA_YOLO_INPUT=/caminho/video.mp4 ./scripts/run_video_poc.sh test
```

## Acompanhar o log em outro terminal

Enquanto o detector estiver rodando:

```bash
cd /root/harpia_ws/src/yolo-inference
./scripts/watch_video_log.sh
```

O watcher procura o `video_poc_*.log` mais recente e executa `tail -f`.

`Ctrl+C` encerra apenas o acompanhamento do log quando o detector está rodando em
outro terminal.

## Painel visual

Após uma execução bem-sucedida:

```text
output/video_report.html
```

O painel reúne:

- vídeo anotado, quando o MP4 local estiver presente;
- FPS da fonte e FPS de processamento;
- tempo médio por frame;
- total de detecções de `person`;
- confiança média;
- frames de evidência;
- benchmark YOLO11n × YOLO11s;
- trecho final do log da execução.

O painel é totalmente local e não usa JavaScript, CDN ou dependência web externa.

Se quiser regenerá-lo sem executar o YOLO novamente:

```bash
/root/yolo_venv/bin/python scripts/video_report.py \
  --metrics results/yolo11n_metrics.json \
  --comparison results/comparison.csv \
  --source results/video_source.json \
  --video output/yolo11n_people.mp4 \
  --output output/video_report.html
```

Para incluir um log existente:

```bash
/root/yolo_venv/bin/python scripts/video_report.py \
  --metrics results/yolo11n_metrics.json \
  --comparison results/comparison.csv \
  --source results/video_source.json \
  --video output/yolo11n_people.mp4 \
  --log logs/video_poc_full_YYYYMMDD-HHMMSS.log \
  --output output/video_report.html
```

## O que é versionado

O painel, os vídeos e os logs são artefatos locais e ficam fora do Git.

Continuam versionados apenas os artefatos pequenos necessários para auditoria:

- métricas JSON;
- `results/comparison.csv`;
- metadados da fonte;
- frames de evidência.

Isso mantém o repositório leve sem perder reprodutibilidade.
