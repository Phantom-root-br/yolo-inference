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

Para recriar apenas o vídeo compatível com navegador e o painel, sem rodar YOLO novamente:

```bash
./scripts/run_video_poc.sh report
```

O runner:

1. usa `/root/yolo_venv/bin/python` por padrão;
2. nos modos `test` e `full`, executa `scripts/detect_people.py`;
3. preserva o MP4 anotado gerado pelo OpenCV, incluindo os bounding boxes;
4. transcodifica esse MP4 para H.264/yuv420p com `scripts/transcode_web_video.py`;
5. usa `+faststart` para facilitar reprodução progressiva no navegador;
6. mostra o progresso no terminal e grava a mesma saída com `tee`;
7. salva o log em `logs/video_poc_<modo>_<timestamp>.log`;
8. gera `output/video_report.html` apontando para o vídeo H.264;
9. usa `harpia-copylog` ao final, quando o helper estiver disponível.

O modo `report` pula a inferência e usa o resultado completo já existente:

```text
output/yolo11n_people.mp4
        ↓ transcode H.264
output/yolo11n_people_web.mp4
        ↓
output/video_report.html
```

A transcodificação não executa YOLO e não redesenha detecções. Os bounding boxes já
presentes no vídeo anotado são preservados durante a conversão de codec.

## Dependência do vídeo web

A conversão usa `imageio-ffmpeg`, registrado em `requirements.txt`. No ambiente HARPia:

```bash
/root/yolo_venv/bin/python -m pip install imageio-ffmpeg
```

Não é necessário instalar FFmpeg pelo sistema nem alterar ROS 2, PX4 ou Gazebo.

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

- vídeo anotado em H.264, compatível com navegadores modernos;
- bounding boxes e labels `person` gravados pelo detector;
- FPS da fonte e FPS de processamento;
- tempo médio por frame;
- total de detecções de `person`;
- confiança média;
- frames de evidência;
- benchmark YOLO11n × YOLO11s;
- trecho final do log da execução.

O painel é totalmente local e não usa CDN ou dependência web externa.

Para servir o painel localmente:

```bash
/root/yolo_venv/bin/python -m http.server 8000 --bind 0.0.0.0
```

Abra no navegador gráfico:

```text
http://localhost:8000/output/video_report.html
```

## O que é versionado

O painel, os vídeos e os logs são artefatos locais e ficam fora do Git.

Continuam versionados apenas os artefatos pequenos necessários para auditoria:

- métricas JSON;
- `results/comparison.csv`;
- metadados da fonte;
- frames de evidência.

Isso mantém o repositório leve sem perder reprodutibilidade.
