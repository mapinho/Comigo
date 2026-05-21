# Relatório de Análise Técnica: Impacto de Vendas e Otimização Logística
**Caso de Estudo:** Armazém MINEIROS e Desvio de Fluxo para PALMEIRAS

## 1. Objetivo
Este documento detalha o comportamento do motor de otimização do Sistema de Transbordo ao introduzir volumes de "Vendas Diretas" nos armazéns, explicando por que rotas mais caras podem ser priorizadas em cenários de escassez regional.

---

## 2. Cenário Analisado
Comparação entre o cenário **Planejado (Baseline)** e o cenário **Vendas (Simulação)** para o fluxo de saída do armazém de **MINEIROS**:

*   **Destino A (Preferencial):** COMPL. INDUSTRIAL | Distância: 195km | Custo: R$ 100,00
*   **Destino B (Alternativo):** PALMEIRAS | Distância: 365km | Custo: R$ 170,00

### Resultados Observados
| Indicador | Planejado (Sem Vendas) | Cenário Vendas |
| :--- | :--- | :--- |
| **Destino de MINEIROS** | 100% para COMPL. INDUSTRIAL | Misto (Complexo + Palmeiras) |
| **Volume para Palmeiras** | 0 Ton | ~9.283 Ton |
| **Frequência de Desvio** | Nunca | 22 dias de operação |

---

## 3. Diagnóstico: Por que o sistema escolheu a rota mais cara?

A matemática do otimizador não visa apenas o "menor frete", mas sim a **"Eficiência Operacional Total"**. Ao inserir volumes de vendas nos armazéns próximos à unidade de **PALMEIRAS**, o sistema detectou as seguintes condições:

### A. Prevenção de Parada de Fábrica (Vácuo de Demanda)
O sistema possui uma regra de segurança com peso de **1.000.000** para garantir que nenhuma fábrica fique sem soja para esmagar.
*   No cenário de Vendas, os armazéns que tradicionalmente abastecem Palmeiras ficaram com estoque reduzido.
*   O sistema identificou que, em determinados dias, a soja regional não seria suficiente para manter o esmagamento de Palmeiras.
*   **Decisão do Otimizador:** Recrutar o estoque de MINEIROS (mesmo com frete R$ 70,00 mais caro) para evitar o prejuízo milionário de uma parada de fábrica por falta de matéria-prima.

### B. O Princípio da Garantia de Fluxo
Enquanto o **Complexo Industrial** estava operando com estoque saudável ou até mesmo no limite de sua capacidade de recepção, a unidade de **Palmeiras** estava em estado **Crítico** (estoque próximo de zero).
*   O sistema prefere pagar um frete mais alto para garantir que a unidade "desabastecida" receba carga, mantendo o equilíbrio do sistema logístico.

---

## 4. Conclusão
O comportamento observado no cenário de Vendas é **correto e esperado**. Ele demonstra que o sistema é capaz de:
1.  **Antecipar crises de abastecimento:** Identificar onde a soja vai faltar devido a saídas comerciais (vendas).
2.  **Priorizar a Indústria:** Sacrificar o custo de frete pontual para garantir a continuidade do esmagamento.
3.  **Gestão Dinâmica:** Reconfigurar as rotas automaticamente assim que o balanço de massa regional muda.

**Recomendação para a Equipe de Logística:**
Este desvio de Mineiros para Palmeiras serve como um **alerta antecipado**. Ele indica que, se as vendas planejadas se concretizarem, a frota regional de Palmeiras precisará de suporte de unidades mais distantes para manter o ritmo de esmagamento total.

---
**Gerado automaticamente pelo Sistema de Planejamento de Transbordo - Comigo**
*Data do Relatório: 20 de maio de 2026*
