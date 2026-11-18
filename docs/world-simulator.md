# NixLMs — Simulador de mundo

O `WorldSimulator` permite testar hipóteses sobre os fatos registrados no
`WorldModel` sem alterar a memória persistente.

## Exemplo

```python
result = ai.simulator.simulate_fact(
    "NixLMs", "runs_on", "GPU", confidence=0.6, source="what-if"
)
print(result["new_conflicts"])
```

## Garantias

- Simulações são determinísticas para o mesmo estado e as mesmas alterações.
- Os fatos são copiados antes de qualquer hipótese.
- Nenhuma alteração é gravada no banco/arquivo do WorldModel.
- Nenhuma ferramenta externa, comando ou ação do sistema operacional é executada.
- Conflitos são reportados; o simulador não escolhe automaticamente qual fato é verdadeiro.
- Cada simulação aceita no máximo 20 alterações.

O resultado é uma previsão simbólica baseada apenas nos fatos fornecidos. Não é
um modelo físico completo nem uma garantia de que o cenário ocorrerá.
