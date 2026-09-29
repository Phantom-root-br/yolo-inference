# Contribuindo

## Fluxo recomendado

1. crie uma branch a partir de `main`;
2. faça uma alteração pequena e verificável;
3. rode lint e testes;
4. abra um Pull Request.

Exemplo:

```bash
git checkout -b feat/minha-alteracao
python -m pip install -r requirements-dev.txt
ruff check .
pytest
```

## Convenção de branches

```text
feat/...
fix/...
docs/...
chore/...
```

## Commits

Prefira mensagens curtas e descritivas:

```text
feat: add json inference output
fix: validate confidence range
docs: document HARPia setup
```

## Escopo

Evite misturar no mesmo PR:

- mudanças de inferência;
- alterações ROS 2;
- mudanças PX4;
- datasets;
- pesos treinados.

Isso mantém as revisões simples e reproduzíveis.
